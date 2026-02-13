import re
import random

from backend.components.engineer import PromptEngineer
from backend.prompts.general import (intent_phrases, dax_phrases, general_ambiguity_prompt, other_ambiguity_prompt,
                                    measure_clarification_prompt, segment_clarification_prompt)
from backend.utilities.templates import insert_clarification, update_clarification, delete_clarification

class Ambiguity(object):
  def __init__(self):
    self.uncertainty = {
      'general': False,       # G: No clue what is going on, high uncertainty in intent or dact
      'partial': False,       # P: you know the dact, but not the grounding details (ie. tabs and cols)
      'specific': False,      # S: The flow has a missing slot to fill (eg. target, metric, category, etc.)
      'confirmation': False   # C: You have a candidate slot-value (ie. removal column), but want to confirm
    }
    self.observation = ""     # the text of the clarification question we want to ask
    self._unknown = {}        # keys for [flow, slot, values] are added when associated features are non-empty
    self.needs_generation = False     # use templates by default when asking for clarification

  def __str__(self):
    string_rep = ""
    for level, value in self.uncertainty.items():
      string_rep += f"{level.title()}: {value}\n"
    return string_rep

  def lowest_level(self, reverse=False):
    levels = ['general', 'partial', 'specific', 'confirmation']
    if reverse:
      levels.reverse()

    for level in levels:
      if self.uncertainty[level]:
        return level
    return 'none'

  def present(self):
    # Determine if we have encountered any uncertainty so far
    return any(list(self.uncertainty.values()))

  def random_clarification(self):
    # We don't even know the intent, or we have serious doubts about its accuracy, so we ask a generic question
    generic_clarification = [
      "I didn't quite get what you said, can you rephrase that?",
      "Can you please clarify what you mean?",
      "I did not understand what you just said. Please provide more information."
      "What exactly are you requesting? I'm not sure I understand.",
      "I'm not sure what you mean, can you please elaborate?",
    ]
    return random.choice(generic_clarification)

  def drop_ambiguous_entities(self, state):
    for entity in state.entities:
      if entity.get('rel', '') == 'ambiguous':
        state.entities.remove(entity)

    active_flow = state.get_flow(allow_interject=False)
    if active_flow:
      ent_slot = active_flow.entity_slot
      active_flow.slots[ent_slot].drop_ambiguous()

  def ask(self, api, context, state):
    if len(self.observation) > 3:   # not empty string or 'N/A'
      clarification_question = self.observation
    elif self.needs_generation:
      clarification_question = self.generate_clarification(api, context, state)
    else:
      level = self.lowest_level(reverse=True)
      match level:
        case 'general': clarification_question = self.general_ask(state)
        case 'partial': clarification_question = self.partial_ask(state)
        case 'specific': clarification_question = self.specific_ask(state)
        case 'confirmation': clarification_question = self.confirmation_ask(state)
        case 'none': clarification_question = ''

      if len(clarification_question) == 0:
        clarification_question = self.random_clarification()

    self.drop_ambiguous_entities(state)
    return clarification_question

  def general_ask(self, state):
    intent_phrase = intent_phrases.get(state.intent, '')
    dax_phrase = dax_phrases.get(state.get_dialog_act(), '')  # setting dax to {9DF} effectively keeps it empty
    clarification = ''

    if len(state.errors) > 0:
      error_message =  PromptEngineer.array_to_nl([error['error'] for error in state.errors])
      clarification = "I hit an error with " + error_message
      clarification += f" when I tried to {intent_phrase}." if intent_phrase else "."
      clarification += " Can you please rephrase your request?"

    elif intent_phrase:
      if dax_phrase:
        clarification = f"Are you trying to {dax_phrase}? If not, could you please clarify what you want?"
      else:
        clarification = f"It seems you want to {intent_phrase}, but I got a bit lost. Can you please be more specific?"
    return clarification

  def partial_ask(self, state):
    if 'flow' in self._unknown:
      flow_name = self._unknown['flow']
      flow = state.get_flow(flow_type=flow_name)

      current_dax = state.get_dialog_act('hex')
      match current_dax:
        case '002': clarification = 'What are the correct columns I should be using to calculate the metric?'
        case '005': clarification = insert_clarification(flow)
        case '006': clarification = update_clarification(flow)
        case '007': clarification = delete_clarification(flow)
        case _: clarification = 'What are the correct tables and columns I should be focusing on?'

    elif len(state.entities) == 0:
      match state.intent:
        case 'Analyze': content = "trying to query"
        case 'Detect': content = "trying to understand"
        case 'Visualize', 'Transform', 'Clean': content = f"trying to {state.intent.lower()}"
        case _: content = "referring to"
      clarification = f"Just to be clear, what table are you {content}?"

    # this means we don't actually know the column name
    elif len(state.entities) == 1:
      tab_name = state.entities[0]['tab']
      col_name = state.entities[0]['col']
      if any([entity['col'] == '*' for entity in state.entities]):
        clarification = f"Is there a particular column in the {tab_name} table that you have in mind?"
      else:
        clarification = f"Are you referring to {col_name} in the {tab_name} table?"
    else:  # multiple entities
      tab_name = state.entities[0]['tab']
      col_names = PromptEngineer.array_to_nl([entity['col'] for entity in state.entities[:4]], 'or')
      if any([entity['col'] == '*' for entity in state.entities]):
        clarification = f"You're talking about the {tab_name} table right? Any specific columns?"
      else:
        clarification = f"Are you referring to the {col_names} columns in the {tab_name} table?"
    return clarification

  def specific_ask(self, state):
    """
    The slot should be written to represent a subject, such as:
      * the aggregation function
      * how to group the data
      * the relationship between variables
      * what you want to name the metric
    Rather than just a single verb or token.
    """
    if 'flow' in self._unknown:
      flow_name = self._unknown['flow']
      flow = state.get_flow(flow_type=flow_name)
    elif state.has_active_flow():
      flow = state.get_flow(allow_interject=False)

    suffixes = ["Sorry", "Just to be clear", "Apologies"]
    suffix = random.choice(suffixes)
    requests = ['please clarify', 'provide more details about', 'elaborate more on']
    request = random.choice(requests)

    slot_detail = "what to do"  # set the default
    if 'slot' in self._unknown.keys():
      slot_detail = self._unknown['slot']

    if flow:
      goal_message = self.write_the_goal(flow)
      clarification = f"{suffix}, {goal_message}, could you {request} {slot_detail}?"
    else:
      clarification = f"Hmm, I'm not sure what you want me to do. Can you please rephrase your request?"
    return clarification

  def write_the_goal(self, flow):
    phrases = ["I'm a bit confused about how to", "I'm having some trouble", "I'm having issues with"]
    # generate a random value from 0 to 1
    probability = random.random()

    if probability < 0.33:
      goal_message = f"{phrases[0]} {flow.goal}"
    else:
      goal_tokens = flow.goal.split()
      # convert to present participle
      if goal_tokens[0].endswith('e'):
        goal_tokens[0] = goal_tokens[0][:-1] + 'ing'
      else:
        goal_tokens[0] += 'ing'

      if probability < 0.66:
        phrase = phrases[1]
      else:
        phrase = phrases[2]
      goal_message = f"{phrase} {' '.join(goal_tokens)}"
    return goal_message

  def confirmation_ask(self, state):
    if 'flow' in self._unknown:
      flow_name = self._unknown['flow']
      flow = state.get_flow(flow_type=flow_name)
    elif state.has_active_flow():
      flow = state.get_flow(allow_interject=False)

    values = self._unknown.get('values', [])
    if len(values) == 0:
      if 'slot' in self._unknown:
        slot_feature = self._unknown['slot']
        clarification = f"You are trying to tell me about the {slot_feature}, is that right?"
      elif flow:
        clarification = f"You are trying to {flow.goal}, is that right? Please tell me more."
      else:
        clarification = ''

    elif len(values) == 1:
      if 'slot' in self._unknown:
        slot_feature = self._unknown['slot']
        clarification = f"You want the {slot_feature} to be {values[0]}, is that correct?"
      else:
        clarification = f"Can you confirm that you want '{values[0]}'?"

    elif len(values) == 2 or len(values) == 3:
      value_string = PromptEngineer.array_to_nl(values, connector='or')
      clarification = f"Just to be clear, do you want {value_string}?"

    else:  # len(values) >= 4
      random.shuffle(values)
      value_string = PromptEngineer.array_to_nl(values[:2], connector='or')
      clarification = f"Do you want {values[0]}, {values[1]}, or something else?"
    return clarification

  def generate_clarification(self, api, context, state):
    if state.has_active_flow():
      if 'flow' in self._unknown:
        flow_name = self._unknown['flow']
        flow = state.get_flow(flow_type=flow_name)
      else:
        flow = state.get_flow(allow_interject=False)
        flow_name = flow.flow_type
      dact_desc = flow.goal
    else:
      flow_name = 'none'
      dact_desc = 'do something with spreadsheets, but it is entirely unclear'

    table_str = ', '.join(self.current_tab_col.keys())
    col_str = PromptEngineer.column_rep(self.current_tab_col, with_break=True)
    tab_col_str = f"* Tables: {table_str}\n* Columns: {col_str}"
    support_details = self.compile_supporting_details(state)
    convo_history = context.compile_history()
    level = self.lowest_level(reverse=True)

    if flow_name == 'measure':
      prompt = self.measure_generation(convo_history, flow, level, state)
    elif flow_name == 'segment':
      prompt = self.segment_generation(convo_history, flow, level, state)
    elif level == 'general':
      prompt = general_ambiguity_prompt.format(valid_tab_col=tab_col_str, history=convo_history)
    else:
      match level:
        case 'partial':
          rating = 'basic'
          current_task = f"We believe the user wants to {dact_desc}."
          next_step = "figure out which table and column the user wants to focus on"
          reminder = "When drafting your response, note that the valid tables and columns will be shown below, so please consider them as relevant context."
        case 'specific':
          rating = 'reasonable'
          current_task = f"The user is likely trying to {dact_desc}."
          next_step = "determine the missing information to complete the task at hand"
          reminder = "A draft utterance will be shown under supporting details. Please trim down the response to 3 sentences at most, and paraphrase as necessary to ensure smoothness and clarity."
        case 'confirmation':
          rating = 'good'
          current_task = f"Namely, the user wants to {dact_desc}."
          next_step = "confirm our understanding before proceeding"
          reminder = "Potential confirmation questions will be shown under supporting details. Please trim down the response to 3 sentences at most, and paraphrase as necessary to ensure smoothness and clarity."
      prompt = other_ambiguity_prompt.format(rating=rating, current_task=current_task, next_step=next_step, reminder=reminder,
                                             valid_tab_col=tab_col_str, history=convo_history, details=support_details)
    raw_output = api.execute(prompt)
    clarification = PromptEngineer.apply_guardrails(raw_output, 'json')
    return clarification['response']

  def measure_generation(self, convo_history, flow, level, state):
    """ This function is used to generate clarification questions for the measure flow. """
    metric = flow.slots['metric'].formula
    full_name, short_name = metric.get_name('full'), metric.get_name(size='short')
    formula_json = state.slices['metrics'][short_name].display()

    match level:
      case 'partial':
        ambiguity_snippet = "provide guidance on which tables and columns are most relevant for calculating the metric"
        action_verb = "determine the columns for"
      case 'specific':
        ambiguity_snippet = "take a look at the predicted formula and fill in the missing variables to complete it"
        action_verb = "properly calculate"
      case 'confirmation':
        ambiguity_snippet = "confirm whether the predicted formula is accurate"
        action_verb = "verify the correctness of"

    prompt = measure_clarification_prompt.format(full_name=full_name, short_name=short_name, thoughts=state.thought,
                        ambiguity=ambiguity_snippet, action=action_verb, history=convo_history, formula=formula_json)
    return prompt

  def segment_generation(self, convo_history, flow, level, state):
    """ This function is used to generate clarification questions for the segment flow. """
    metric, seg_dim = flow.slots['metric'].formula, flow.slots['segment'].value['dimension']
    full_name, short_name = metric.get_name('full'), metric.get_name(size='short')
    formula_json = state.slices['metrics'][short_name].display(with_verify=True)

    match level:
      case 'partial':
        ambiguity_snippet = "provide guidance on which tables and columns are most relevant for calculating the metric"
      case 'specific':
        ambiguity_snippet = "take a look at the predicted formula and fill in the missing variables to complete it"
      case 'confirmation':
        ambiguity_snippet = "confirm particular variables in the formula that have not yet been verified"

    prompt = segment_clarification_prompt.format(full_name=full_name, short_name=short_name, thoughts=state.thought,
                            dimension=seg_dim, ambiguity=ambiguity_snippet, history=convo_history, formula=formula_json)
    return prompt

  def compile_supporting_details(self, state):
    if 'values' in self._unknown.keys():
      details = self._unknown['values']
    else:
      # split the thought into sentences based on punctuation followed by whitespace
      details = re.split(r'(?<=[.!?])\s', state.thought)
    return '\n'.join(details)

  def gather_active_entities(self, valid_columns, state, actions):
    if 'CLARIFY' not in actions: return
    active_tables = set([entity['tab'] for entity in state.entities])
    active_tables = [state.current_tab] if len(active_tables) == 0 else list(active_tables)
    self.current_tab_col = {}
    for tab_name in active_tables:
      if tab_name in valid_columns:
        self.current_tab_col[tab_name] = valid_columns[tab_name]

  def declare(self, level, flow='', slot='', values=[], generate=False):
    """ Tips:
    - include a 'flow' when declaring a specific or confirmation ambiguity
    - 'slot' should be a natural lang description of the missing piece of information, not the name of the BaseSlot
    - 'values' should be a list of possible values for the slot, most critical when asking for confirmation
    """
    self.uncertainty[level] = True
    for key, feature in [('flow', flow), ('slot', slot), ('values', values)]:
      if len(feature) > 0:
        if key == 'slot' and feature in ['source', 'target']:
          self._unknown[key] = 'chosen column'
        else:
          self._unknown[key] = feature
    if generate:
      self.needs_generation = True

  def resolve(self, level='', feature=''):
    if level == '':
      for level in ['general', 'partial', 'specific', 'confirmation']:
        self.uncertainty[level] = False
    else:
      self.uncertainty[level] = False

    if feature != '':
      del self._unknown[feature]
    self.needs_generation = False