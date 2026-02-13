import numpy as np
import json
from utils.help import dax2dact, dact2dax, dax2intent
from collections import defaultdict

from backend.constants import PROJECT_DIR
from backend.components.state import DialogueState
from backend.components.engineer import PromptEngineer
from backend.modules.flow import flow_selection
from backend.modules.experts.for_nlu import *
from backend.prompts.for_nlu import *
from backend.utilities.nlu_helpers import *
from backend.utilities.search import extract_partial

class NatLangUnderstanding(object):

  def __init__(self, args, external_api, internal_api, storage):
    self.verbose = args.verbose
    self.debug_mode = args.debug
    self.threshold = args.threshold
    self.allow_alchemy = args.allow_dev_mode
    self.reset_flags()
    intent_data, dact_data = self._preprocess_seed()

    self.regex = RegularExpressionParser(args.threshold, args.verbose)
    self.embed = EmbeddingRetriever(args, intent_data, storage)
    self.logreg = LogisticRegression(args, internal_api)
    self.peft = FineTunedLearner(args, internal_api)
    self.icl = InContextLearner(args, external_api)

  def _preprocess_seed(self):
    seed_data = json.load(open(os.path.join(PROJECT_DIR, 'database', 'storage', 'seed_data.json'), 'r'))
    intent_data, dact_data, flow_data = seed_data['Intents'], seed_data['Dacts'], seed_data['Flows']
    self.dax2flow = {flow['dax']: flow for flow in flow_data}          # flow has name, dax, and operations as keys
    self.flow2dax = {flow['name']: flow['dax'] for flow in flow_data}  # holds full flow name
    return intent_data, dact_data

  def activate_command(self, regex_intent, regex_dax, context):
    # for advanced developer control, not part of normal flow
    if regex_intent == 'unknown':
      regex_intent = dax2intent(regex_dax)

    command_type, command_string = self.regex.command
    if command_type in ['sql', 'python']:
      self.shortcut = True

    context.recent[-1].add_revision(command_string)
    self.command = command_type, command_string
    self.regex.command = "", ""
    return (regex_intent, regex_dax, "", []), 1.0

  def initial_prediction(self, context, prior_state):
    # first pass of intent/dact/dax prediction
    regex_intent, regex_dax, regex_score = self.regex(context, prior_state.get_dialog_act())
    if regex_score == 1.0:
      return self.activate_command(regex_intent, regex_dax, context)
    elif regex_score > 0.9:
      grouped_predictions = regex_intent, regex_dax, regex_intent, regex_dax
      return grouped_predictions, regex_score

    dact_string = prior_state.get_dialog_act('string')
    prior_dialog_act = dact_string if dact_string else ''

    icl_intent, icl_dax, _ = self.icl(context, "", prior_state.intent, prior_dialog_act)
    grouped_pred = (icl_intent, icl_dax, 'placeholder', '000')
    return grouped_pred, 0.9

  def make_predictions(self, context, prior_state):
    """ returns a predicted dialogue_acts in dax format """
    predictions, score = self.initial_prediction(context, prior_state)
    pred_intent, pred_dax, _, _ = predictions
    return pred_intent, pred_dax, score

  def validate_state(self, state, world, context):
    state = self.fix_tables(state, world, context)
    dax = state.get_dialog_act()

    # make sure all table-column combos are unique
    state = ensure_unique_tab_cols(state)
    # check that all columns within a dialogue_state are valid
    problem_cols = []
    for entity in state.entities:
      if not isinstance(entity['col'], str):
        state.ambiguity.declare('partial')
        continue
      if entity['col'] == '*':
        continue
      if dax in ['005', '05C', '0BD']:
        continue  # by definition, the new column to insert is missng from current columns
      if entity['col'] not in world.valid_columns[entity['tab']]:
        problem_cols.append((entity['col'], entity['tab']))

    # attempt to repair problematic columns
    attempts = 3
    while len(problem_cols) > 0 and attempts > 0:
      problem, p_table = problem_cols.pop(0)
      print(f"  Problem column: {problem} in {p_table}")
      match, m_col, m_table = self.icl.find_related_columns(problem, p_table, world.valid_columns)
      print(f"  Fixed column: {m_col} in {m_table}")

      # solid match, came make a direct swap
      if match == 'no':
        state.ambiguity.declare('partial', values=[problem])
      elif m_table in world.valid_tables and m_col in world.valid_columns[m_table]:
        corrected = []
        for entity in state.entities:
          if entity['tab'] == p_table and entity['col'] == problem:
            corrected.append({'tab': m_table, 'col': m_col, 'ver': entity['ver']})
          else:
            corrected.append(entity)
        state.entities = corrected
        if match == 'maybe':
          state.ambiguity.declare('confirmation', slot='source', values=[m_col])
      else:
        problem_cols.append((m_col, m_table))
      attempts -= 1

    # check if a different flow is more appropriate
    if state.ambiguity.present() and state.has_active_flow():
      state = self.check_for_fallback(state, world)

    # set the current tab and the turn_id
    if state.current_tab not in world.valid_tables:
      prior_state = world.current_state()
      state.current_tab = prior_state.current_tab
    state.turn_id = context.recent[-1].turn_id
    return state

  def fix_tables(self, state, world, context):
    # check that all tables within a dialogue_state are valid
    if len(state.entities) == 0 or state.entities[0]['tab'] == 'all':
      if state.current_tab in world.valid_tables:
        pred_table = state.current_tab
      else:
        pred_table = self.icl.predict_table(state, world, context)
      state.entities = [{'tab': pred_table, 'col': '*', 'ver': False}]
      state.current_tab = pred_table

    table_fixes = {}
    has_problem = False
    for entity in state.entities:
      if entity['tab'] not in world.valid_tables:
        problem_tab = entity['tab']
        fixed_table = table_fixes.get(problem_tab, '')

        if not fixed_table:
          # just check casing first, since these are basic errors
          if problem_tab.lower() in world.valid_tables:
            table_fixes[problem_tab] = problem_tab.lower()
          elif problem_tab.upper() in world.valid_tables:
            table_fixes[problem_tab] = problem_tab.upper()
          elif problem_tab.title() in world.valid_tables:
            table_fixes[problem_tab] = problem_tab.title()
          else:  # attempt to find the nearest valid table
            nearest_tab = find_nearest_lexical(problem_tab, world.valid_tables)
            if nearest_tab is None:
              state.ambiguity.declare('partial')
            else:
              state.ambiguity.declare('confirmation', slot='table', values=[nearest_tab])
              table_fixes[problem_tab] = nearest_tab
        has_problem = True

    if has_problem:
      validated = []
      for entity in state.entities:
        if entity['tab'] in world.valid_tables:
          validated.append(entity)
        elif entity['tab'] in table_fixes:
          entity['tab'] = table_fixes[entity['tab']]
          validated.append(entity)
      state.entities = validated
    return state

  def finalize_state(self, state, last_state):
    # Run at the end to finalize the dialogue state, also reset the NLU for next turn
    if self.score < 0:
      state.ambiguity.declare('general')

    if self.shortcut:  # this is a special command, so don't need to check for ambiguity
      state.ambiguity.resolve()

    if state.ambiguity.present():
      level = state.ambiguity.lowest_level()
      # if there is deep confusion, fallback to prior states to prevent damage from cascading
      if level in ['general', 'partial']:
        state = use_validated_entities(state, last_state)
      state.thought = f"There is some {level} ambiguity I need to clarify with the user."
      active_flow = state.get_flow(allow_interject=False)
      if active_flow:
        active_flow.is_uncertain = True

    self.reset_flags()
    if self.verbose:
      print(f"  Dialogue state:\n{state}")
      print(f"* Thought: {state.thought}")
    return state

  def reset_flags(self):
    self.shortcut = False
    self.active_flow = None
    self.labels = {'intent': '' , 'dax': '', 'entities': [], 'score': 0}
    self.score = 0.5
    self.command = '', ''

  def predict(self, context, world, gold_dax=''):
    """
    Input: context (w/ dialogue history), world (w/ prior states)
    Output: prediction - intents, dacts, core, ops
            score - the confidence of the prediction (float)
    """
    prior_state = world.current_state()
    if self.golden_victory(gold_dax):
      pred_intent, pred_dax, score = dax2intent(gold_dax), gold_dax, 0.99
      pred_dax = self.preliminary_review(context, pred_dax, prior_state)
    else:
      pred_intent, pred_dax, score = self.make_predictions(context, prior_state)
      pred_dax = self.preliminary_review(context, pred_dax, prior_state)

      matching_intent = dax2intent(pred_dax)
      if pred_intent != matching_intent:
        pred_intent = matching_intent
        print(f"  Made a repair to change intent to {pred_intent} so it aligns with the dax")
      print(f"  Predicted dact: {dax2dact(pred_dax)} {{" + pred_dax + "}")

    self.labels.update({'intent': pred_intent, 'dax': pred_dax, 'score': score})
    if pred_dax in self.dax2flow:
      self.active_flow = self.construct_flow(prior_state, pred_dax, world.valid_columns)
    return pred_dax

  def preliminary_review(self, context, pred_dax, prior_state):
    """ Review the predicted dialog act and make any necessary adjustments """
    if prior_state.has_plan:
      self.accept_plan_proposal(context, pred_dax, prior_state)
    # Perform sanity check for certain complex dialog acts
    if pred_dax.startswith('46'):
      pred_dax = self.resolve_single_issue(pred_dax, prior_state)
    # Abort immediately if the predicted dialog act is unsupported
    if pred_dax in ['248', '268', '023', '038', '23D', '136', '13A', '068', '06F', '368',
                    '056', '456', '46D', '468', '008', '009', '00D']:
      pred_dax = 'FFF'
    return pred_dax

  def accept_plan_proposal(self, context, pred_dax, prior_state):
    # Check whether the user has accepted the agent's proposal
    pred_flow_name = self.dax2flow[pred_dax]['name']
    previous_flow = prior_state.get_flow()
    full_flow_name = previous_flow.name(full=True)

    if full_flow_name.startswith('Detect'):
      # the proposal is a multi-step plan so accepting is a binary decision
      if previous_flow.name() == 'insight':
        if prior_state.has_plan:
          prompt = plan_approval_prompt.format(history=context.compile_history())
          prediction = PromptEngineer.apply_guardrails(self.icl.api.execute(prompt), 'json')
          previous_flow.slots['plan'].approved = prediction['approval']
      elif full_flow_name != pred_flow_name:
        # proposal is a set of options, so accepting means selecting one of the options
        previous_flow.slots['proposal'].add_one(extract_partial(pred_flow_name))

  def resolve_single_issue(self, pred_dax, prior_state):
    # Force the agent to resolve one issue at a time
    predicted_flow = self.dax2flow[pred_dax]['name']
    previous_flow = prior_state.get_flow(return_name=True)

    if previous_flow.startswith('Detect') and previous_flow != predicted_flow:
      pred_dax = self.flow2dax[previous_flow]
    return pred_dax

  def golden_victory(self, gold_dax):
    success = False
    if len(gold_dax) == 3 and self.allow_alchemy:
      try:
        gold_intent = dax2intent(gold_dax)
        success = True
      except(ValueError):
        success = False
    return success

  def construct_flow(self, state, dax, valid_col_dict):
    previous_flow = state.get_flow()
    curr_flow_name = self.dax2flow[dax]['name']
    prev_flow_name = state.get_flow(return_name=True)

    if previous_flow and previous_flow.interjected and previous_flow.parent_type == 'Detect':
      if dax.startswith('46') or 'E' in dax:
        previous_flow.interjected = False  # The user has accepted the interjection
      else:
        issue_flow = state.flow_stack.pop()
        state.has_issues = False
        underlying_flow = state.get_flow()
        if underlying_flow and underlying_flow.completed:
          state.flow_stack.pop()

    if (curr_flow_name == prev_flow_name) and not previous_flow.completed:
      active_flow = previous_flow     # predicted the same flow, so just continue with the current one
    elif curr_flow_name.startswith('Internal'):
      active_flow = None              # captures {9DF} scenarios
    else:
      active_flow = flow_selection[dax](valid_col_dict)
    return active_flow

  def check_for_fallback(self, state, world):
    current_flow = state.get_flow(allow_interject=False)
    if current_flow.fall_back:
      # create a new flow to replace the current one
      new_dax = current_flow.fall_back
      old_flow = state.flow_stack.pop()
      state.store_dacts(dax=new_dax)
      new_flow = flow_selection[new_dax](world.valid_columns)

      # transfer any entities from the old flow to the new one
      if old_flow.slots[old_flow.entity_slot].filled:
        for entity in old_flow.slots[old_flow.entity_slot].values:
          ent_slot = new_flow.entity_slot
          new_flow.slots[ent_slot].add_one(**entity)

      state.flow_stack.append(new_flow)
      state.ambiguity.resolve()
    return state

  def stream_of_thought(self, context, world):
    prior_state = world.current_state()
    prior_entities = compile_state_entities(prior_state, world)
    valid_col_dict = self.prepare_valid_columns(world)
    valid_tabs = ', '.join(world.valid_tables)
    valid_cols = PromptEngineer.column_rep(valid_col_dict, with_break=True)
    self.labels['table_info'] = valid_cols, valid_tabs, prior_state.current_tab, prior_entities

    if self.active_flow.parent_type == 'Detect' or self.labels['dax'] in ['001', '014', '14C']:
      convo_history = context.compile_history(look_back=3)
    elif self.labels['dax'] == '58A':
      self.labels['preview'] = derived_tab_preview(world)
      convo_history = context.compile_history(look_back=3)
    else:
      convo_history = context.compile_history()
    return self.icl.stream_entity_prediction(self.labels, convo_history)

  def prepare_valid_columns(self, world):
    if self.labels['dax'] == '06E':
      # attach a position number to each column
      valid_col_dict = defaultdict(list)
      for tab_name, column_names in world.valid_columns.items():
        for idx, col_name in enumerate(column_names):
          modified_name = f"{col_name} ({idx + 1})"
          valid_col_dict[tab_name].append(modified_name)
    elif self.labels['dax'] == '057':
      # attach the datatypes to each column
      valid_col_dict = defaultdict(list)
      for tab_name, column_names in world.valid_columns.items():
        tab_schema = world.metadata['schema'][tab_name]
        for col_name in column_names:
          column_info = tab_schema.get_type_info(col_name)
          modified_name = f"{col_name} ({column_info['type']})"
          valid_col_dict[tab_name].append(modified_name)
    else:
      valid_col_dict = world.valid_columns

    return valid_col_dict

  def build_from_previous(self, context, last_state, world, pred_dax, intent=''):
    if world.are_valid_entities(last_state.entities):
      entity_copy = last_state.entities.copy()
    else:
      entity_copy = [{'tab': last_state.current_tab, 'col': '*', 'ver': False}]

    command_type, current_thought = '', ''
    if intent == 'command':
      command_type, current_thought = self.command
    elif pred_dax.endswith('E'):      # confirm
      if last_state.has_issues:
        current_thought = "The user wants to take a look at the potential issues, so I will display them."
      elif last_state.has_staging:
        current_thought = "I should go ahead with inserting a few columns to move the task forward."
      else:
        current_thought = "The user is satisfied with the results, that's wonderful!"
    elif pred_dax.endswith('F'):    # deny
      if last_state.has_issues:
        current_thought = "The user doesn't think these are real issues, so I will ignore them."
      elif last_state.has_staging:
        current_thought = "The user doesn't want me to insert new columns, we should move in a different direction."
      else:
        current_thought = "The user is not happy with the results. I should consider apologizing."

    dialogue_state = DialogueState(entity_copy, dax=pred_dax, thought=current_thought)
    dialogue_state = transfer_state_metadata(dialogue_state, last_state, context)
    dialogue_state.command_type = command_type
    return dialogue_state

  def build_from_predictions(self, last_state, context, valid_col_dict, labels):
    if len(labels['entities']) == 0:
      labels['entities'] = last_state.entities.copy()
    dialogue_state = DialogueState(**labels)
    dialogue_state = transfer_state_metadata(dialogue_state, last_state, context)
    return dialogue_state

  def build_from_current(self, curr_state, last_state, context, world):
    # store other relevant information
    command_type, command_string = self.command
    if command_type == 'flow_thought':
      curr_state.thought = command_string
    curr_state = transfer_state_metadata(curr_state, last_state, context)

    curr_flow = self.active_flow
    if curr_flow.is_uncertain:
      level = 'partial' if len(self.labels['entities']) > 0 else 'general'
      curr_state.ambiguity.declare(level)
    if curr_flow.is_newborn:
      curr_state.flow_stack.append(curr_flow)
    if curr_state.natural_birth and context.num_utterances > 16:
      curr_state = self.agent_initiated_issues(context, curr_state, world)
      curr_flow.is_newborn = False
    return curr_state

  def agent_initiated_issues(self, context, state, world):
    """ Either add or remove issue flows that are initiated by the agent """
    preference = context.preferences.get_pref('caution')

    if state.get_dialog_act() in ['001', '002', '003'] and preference in ['warning', 'alert']:
      if state.has_issues and state.has_active_flow(1) and state.flow_stack[-2].interjected:
        # we already found issues, but user ignored it by asking a new question
        state = user_ignored_issues(state)
      else:
        # we pro-actively consider interjecting a Detect Flow
        state = interject_issue_flow(preference, state, world)
    return state

  def contemplate(self, flow, state, context, world, spreadsheet):
    # fills slot values based on thinking deeper, often involves calculating confidence to verify entities
    if flow.entity_slot == 'source' and flow.slots[flow.entity_slot].filled:
      entity = flow.slots[flow.entity_slot].values[0]
      tab_name, col_name = entity['tab'], entity['col']
    else:
      return state

    dax, prompt, valid_col_dict = state.get_dialog_act(), '', world.valid_columns
    valid_col_str = PromptEngineer.column_rep(valid_col_dict, with_break=True)
    convo_history = context.compile_history(look_back=3)
    col_info = world.metadata['schema'][tab_name].get_type_info(col_name)
    col_info.update(entity)

    if dax in ['001', '01A', '003']:
      prompt = compile_operations_prompt(convo_history, flow, state)
    elif dax == '014':
      prompt = describe_facts_prompt.format(columns=valid_col_str, history=convo_history)
    elif dax == '002' and not flow.slots['metric'].is_initialized():
      prompt = metric_name_prompt.format(history=convo_history, columns=valid_col_str)
    elif dax == '02D' and not flow.slots['metric'].is_initialized():
      prompt = segment_metric_prompt.format(history=convo_history)
    elif dax == '05C' and flow.name() == 'merge':
      valid_cols = ', '.join(valid_col_dict[tab_name]) + f' in {tab_name} table'
      source_str = PromptEngineer.array_to_nl([ent['col'] for ent in flow.slots['source'].values], connector='and')
      prompt = merge_col_confidence.format(history=convo_history, columns=valid_cols, entities=source_str)
    elif dax == '5CD' and not flow.slots['delimiter'].filled:
      prompt = compile_delimiter_prompt(col_info, flow, spreadsheet, convo_history)
    elif dax == '057':
      prompt = move_element_prompt.format(table=tab_name, columns=valid_col_str, history=convo_history)

    if len(prompt) > 0:
      raw_output = self.icl.api.execute(prompt)
      prediction = PromptEngineer.apply_guardrails(raw_output, 'json')
      flow.fill_slot_values(state.current_tab, prediction)
    return state

  def track_state(self, context, world):
    pred_intent, pred_dax = self.labels['intent'], self.labels['dax']
    last_state = world.current_state()

    if self.shortcut:
      dialogue_state = self.build_from_previous(context, last_state, world, pred_dax, 'command')

    elif dax2dact(pred_dax) == 'agent + multiple + deny':
      dialogue_state = last_state
      dialogue_state.store_dacts(dax='9DF')
      dialogue_state.intent = 'Internal'
      dialogue_state.ambiguity.declare('general')

    elif pred_intent == 'Converse':
      if pred_dax in ['00A', '00B', '00C']:
        dialogue_state = self.build_from_predictions(last_state, context, world.valid_columns, self.labels)
      else:   # {004} for FAQs / {00E} for confirmation / {008} for user preferences
        dialogue_state = self.build_from_previous(context, last_state, world, pred_dax, 'Converse')

    elif self.active_flow:
      self.labels['entities'].extend(self.active_flow.entity_values())
      curr_state = DialogueState.from_dict(self.labels, last_state.current_tab)
      # add extra information to the dialogue state, including the flow itself
      dialogue_state = self.build_from_current(curr_state, last_state, context, world)
    else:
      dialogue_state = self.build_from_previous(context, last_state, world, pred_dax, pred_intent)
      dialogue_state.ambiguity.declare('general')

    dialogue_state = self.validate_state(dialogue_state, world, context)
    return dialogue_state, last_state
