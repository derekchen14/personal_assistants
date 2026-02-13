import re
import traceback
import pandas as pd

from backend.components.frame import Frame
from backend.components.engineer import PromptEngineer
from backend.components.metadata.typechecks import TypeCheck
from backend.modules.experts.executors import DatabaseExecutor
from backend.modules.flow import flow_selection
from backend.modules.mixins.analyze import AnalyzeMixin
from backend.modules.mixins.visualize import VisualizeMixin
from backend.modules.mixins.clean import CleanMixin
from backend.modules.mixins.transform import TransformMixin
from backend.modules.mixins.detect import DetectMixin
from backend.utilities.pex_helpers import one_off_col_mismatch
from backend.modules.mixins.internal import InternalMixin

from utils.help import flow2dax
from backend.assets.ontology import related_terms, default_limit
from backend.utilities.search import *
from backend.prompts.for_pex import *

class PolicyExecution(AnalyzeMixin, VisualizeMixin, CleanMixin, DetectMixin, TransformMixin, InternalMixin):

  def __init__(self, args, api, embedder):
    self.verbose = args.verbose
    self.api = api
    self.attempts = 0  # [title, lower, upper]
    self.embedder = embedder

  def add_database(self, memory, schema_data):
    self.database = DatabaseExecutor(self.api, memory, schema_data, self.verbose)
    return self.database.special_char_tables

  @staticmethod
  def validate_dataframe(df, code, source, state, tab_type='derived'):
    """ check that the dataframe does not contain errors such as null values or empty results """
    error_encountered = None

    if df is None:
      error_encountered = 'dataframe_is_none'
    else:
      try:
        is_empty = df.empty
        if is_empty:
          error_encountered = 'empty_results'
        else:
          blank_row = df.iloc[0].isnull().all()
          nan_row = pd.isna(df.iloc[0]).any()
          if blank_row or nan_row:
            error_encountered = 'null_values_found'
      except AttributeError:
        error_encountered = 'invalid_dataframe'

    if state.has_issues and error_encountered == 'null_values_found':
      error_encountered = None   # ignore null value errors if we are already dealing with them

    if error_encountered in ['dataframe_is_none', 'invalid_dataframe']:
      frame = Frame(state.current_tab)
    else:
      frame = Frame(state.current_tab, tab_type)
      frame.set_data(df, code, source)

    if error_encountered:
      frame.signal_failure(error_encountered)
    return frame

  def execute_command(self, context, state, world):
    frame = Frame(state.current_tab, tab_type='derived')
    if state.command_type == 'sql':
      sql_query = state.thought
      state.thought = "Executing SQL command ..."
      db_output = self.database.db.execute(sql_query)
      frame.set_data(db_output, sql_query, 'sql')
    elif state.command_type == 'python':
      pandas_code = state.thought
      state.thought = "Executing Python code ..."
      exec(pandas_code)
      frame.set_data(db_output, pandas_code, 'pandas')
      self.update_system_prompt([state.current_tab], world, context, None)

    if self.verbose:
      print(frame.get_data('md'))
    return frame, state

  def set_preference_value(self, context, state, world):
    frame = Frame(state.current_tab)
    valid_columns = PromptEngineer.column_rep(world.valid_columns, with_break=True)
    prompt = set_preference_prompt.format(history=context.compile_history(), valid_cols=valid_columns)
    raw_output = self.api.execute(prompt)
    loaded_pref = PromptEngineer.apply_guardrails(raw_output, 'json')

    if 'error' in loaded_pref.keys() or loaded_pref.get('name', 'error') == 'error':
      frame.signal_failure('custom', "I'm not sure what preference you're referring to. Can you please rephrase your request?")
    else:
      pref_name = loaded_pref['name']
      pref_value = loaded_pref['value']
      pref_detail = loaded_pref['detail']

      context.preferences.set_pref(pref_name, pref_value, pref_detail)
      state.slices['preferences'].append(pref_name)
      print(f"Updated preference value for {pref_name}: {pref_value} ({pref_detail})")

    if frame.is_successful() and state.has_active_flow():
      flow_name = extract_partial(state.get_flow(return_name=True))
      state.store_dacts('', flow2dax(flow_name))
      frame, state = self.take_action(context, state, world)

    return frame, state

  def default_frame(self, state, valid_entities=[]):
    frame = Frame(state.current_tab)

    if len(state.entities) > 0 and len(valid_entities) > 0:
      first_table = state.entities[0]['tab']
      valid_columns = [ent['col'] for ent in valid_entities if ent['tab'] == first_table]

      relevant_columns = []
      for ent in state.entities:
        if ent['tab'] == first_table:
          if ent['col'] not in valid_columns:     # which also checks if columnn name is '*'
            return frame
          else:
            relevant_columns.append(ent['col'])

      if len(first_table) > 0 and len(relevant_columns) != len(valid_columns):
        column_names = []
        for col in relevant_columns:
          for special_char in ['(', ' ', ',']:
            if special_char in col:
              column_names.append(f'"{col}"')
              break
          else:
            column_names.append(col)
        columns = ",".join(column_names)
        default_query = f"SELECT {columns} FROM {first_table} LIMIT {default_limit};"
        try:
          db_output = self.database.db.execute(default_query)
        except Exception as ecp:
          print(f"Error in default_frame - {ecp}")
          return frame
        frame = Frame(first_table, 'derived', source='default')
        frame.set_data(db_output, default_query)
    return frame

  def take_snapshot(self, tab_name, num_rows=0):
    full_df = self.database.db.tables[tab_name]
    if num_rows == 0:
      snapshot_df = full_df.copy()
    else:
      snapshot_df = full_df.head(num_rows).copy()
    return snapshot_df

  def check_alignment(self, frame, world, state):
    """Convert derived frame tab_type if all conditions are aligned with a direct table """
    if frame.tab_type == 'derived' and 'COMMAND' not in self.actions:
      all_tables = [entity['tab'] for entity in state.entities]
      num_tables = len(set(all_tables))
      if num_tables == 1 and state.current_tab == state.entities[0]['tab']:
        aligned = True
      else:
        aligned = False

      if frame.has_content:
        # check that the columns are aligned with the raw table
        for col_name in frame.data.columns:
          if col_name not in world.valid_columns[frame.raw_table]:
            aligned = False
            break
        # check that the rows are aligned with the raw table
        contains_where = 'WHERE' in frame.code
        contains_grouping = 'GROUP BY' in frame.code
        contains_distinct = 'DISTINCT' in frame.code
        if frame.source == 'sql' and (contains_where or contains_grouping or contains_distinct):
          aligned = False
      else:
        aligned = False

      if state.dax in ['014', '14A', '14B', '14C'] and 'REPAIR' not in self.actions:
          aligned = True

      if aligned:
        frame.primary_key = self.database.db.primary_keys[frame.raw_table]
        frame.tab_type = 'direct'

    return frame

  def analyze_policies(self, context, state, world, dax):
    self.actions.add('ANALYZE')
    
    match dax:
      case '001': return self.query_action(context, state, world)
      case '01A': return self.pivot_table(context, state, world)
      case '002': return self.measure_action(context, state, world)
      case '02D': return self.segment_analysis(context, state, world)
      case '014': return self.describe_action(context, state, world)
      case '14C': return self.check_existence(context, state, world)
      case '248': return self.inform_metric(context, state, world)
      case '268': return self.define_metric(context, state, world)

  def visualize_policies(self, context, state, world, dax):
    self.actions.add('VISUALIZE')

    match dax:
      case '003': return self.plot_action(context, state, world)
      case '023': return self.trend_analysis(context, state, world)
      case '038': return self.explain_action(context, state, world)
      case '23D': return self.manage_report(context, state, world)
      case '38A': return self.save_to_dashboard(context, state, world)
      case '136': return self.design_chart(context, state, world)
      case '13A': return self.style_table(context, state, world)

  def clean_policies(self, context, state, world, dax):
    self.actions.add('CLEAN')

    match dax:
      case '006': return self.update_action(context, state, world)
      case '36D': return self.validate_action(context, state, world)
      case '36F': return self.format_action(context, state, world)
      case '0BD': return self.pattern_fill(context, state, world)
      case '06B': return self.impute_missing_values(context, state, world)
      case '06E': return self.assign_datatype(context, state, world)
      case '06F': return self.undo_action(context, state, world)
      case '068': return self.persist_preference(context, state, world)
      case '7BD': return self.remove_duplicates(context, state, world)

  def transform_policies(self, context, state, world, dax):
    snapshot_df = self.take_snapshot(state.current_tab, num_rows=5)
    self.actions.add('TRANSFORM')

    match dax:
      case '005': frame, state = self.insert_action(context, state, world)
      case '007': frame, state = self.delete_action(context, state, world)
      case '056': frame, state = self.transpose_action(context, state, world)
      case '057': frame, state = self.cut_and_paste(context, state, world)
      case '5CD': frame, state = self.split_column(context, state, world)
      case '58A': frame, state = self.materialize_view(context, state, world)
      case '05A': frame, state = self.join_tables(context, state, world)
      case '05B': frame, state = self.append_rows(context, state, world)
      case '05C': frame, state = self.merge_columns(context, state, world)
      case '456': frame, state = self.call_external_api(context, state, world)

    frame = self.transform_safety_net(frame, snapshot_df, state)
    return frame, state

  def detect_policies(self, context, state, world, dax):
    self.actions.add('DETECT')

    match dax:
      case '46B': return self.identify_blanks(context, state, world)
      case '46C': return self.identify_concerns(context, state, world)
      case '46E': return self.identify_typos(context, state, world)
      case '46F': return self.identify_problems(context, state, world)
      case '46D': return self.connect_information(context, state, world)
      case '468': return self.resolve_issues(context, state, world)
      case '146': return self.uncover_insights(context, state, world)

  def internal_policies(self, context, state, world, dax):
    self.actions.add('INTERNAL')

    match dax:
      case '089': return self.think_carefully(context, state, world)
      case '39B': return self.peek_at_data(context, state, world)
      case '149': return self.search_meta_data(context, state, world)
      case '129': return self.compute_action(context, state, world)
      case '19A': return self.stage_action(context, state, world)
      case '489': return self.consider_preferences(context, state, world)
      case '9DF': return self.handle_uncertainty(context, state, world)

  def accept_reject_policies(self, context, state, world, dact_list):
    # Manage user acceptance or rejection of agent suggestion, along with general confirm / deny
    previous_frame = world.frames[-1]

    if state.has_issues:      # Resolving issues such as null values or outliers
      if dact_list[-1] == 'confirm':
        state.command_type = 'confirm'
      elif dact_list[-1] == 'deny':
        state.command_type = 'deny'

      flow_name = extract_partial(state.get_flow(return_name=True))
      state.store_dacts(dax=flow2dax(flow_name))
      frame, state = self.take_action(context, state, world)

    elif state.has_staging:   # Creating a staging table
      if dact_list[-1] == 'confirm':
        prev_state = world.states[-2]
        state.store_dacts(prev_state.get_dialog_act('string'), prev_state.get_dialog_act('hex'))
        frame, state = self.take_action(context, state, world)

        user_pref = context.find_relevant_preference()
        if user_pref:
          user_pref.set_ranking('amount', state.new_column)

      elif dact_list[-1] == 'deny':
        self.actions.add('STAGING|ignore')
        state.flow_stack.pop()
        frame = Frame(state.current_tab)

    else:
      frame = previous_frame # just re-use the most recent frame
    return frame, state

  def is_computation_needed(self, context, frame, state, world):
    prompt = compute_needed_prompt.format(history=context.compile_history())
    raw_output = self.api.execute(prompt, version='claude-haiku')
    prediction = PromptEngineer.apply_guardrails(raw_output, 'json')

    if prediction['question'].lower() != 'none':
      # create the compute flow and add it to the stack
      new_dax = '129'
      state.store_dacts(dax=new_dax)
      compute_flow = flow_selection[new_dax](world.valid_columns)
      compute_flow.slots['question'].add_one(prediction['question'])
      state.flow_stack.append(compute_flow)
      frame, state = self.compute_action(context, state, world)
    return frame, state

  def repair_frame(self, context, frame, state, valid_col_dict):
    if self.attempts == 0 and state.dax in ['014', '14A', '14B', '14C']:
      new_query = self.attempt_describe_repair(context, state)
    elif self.attempts < 3:
      new_query = self.attempt_manual_repair(frame, state)
    # elif self.attempts < 4:
    #   new_query = self.attempt_fix_broken_df(frame, context, valid_col_dict)
    else:
      new_query = self.attempt_fix_empty_results(frame, context, valid_col_dict)

    if new_query == 'exit-repair':
      return frame

    try:
      db_output = self.database.db.execute(new_query)
      frame = self.validate_dataframe(db_output, new_query, 'sql', state)
    except Exception as error_msg:
      frame.warning = str(error_msg)

    if frame.error:
      print(f"Made {self.attempts+1} attempts to repair query, but still failed with {frame.warning}")
    else:
      self.actions.add("REPAIR")
      frame.set_data(db_output, new_query, source='sql')
      frame.tab_type = 'derived'
      frame.overcome_failure(self.verbose)

    return frame

  def attempt_fix_broken_df(self, frame, context, valid_col_dict):
    source_strings = {'sql': 'SQL query', 'pandas': 'Python code', 'plotly': 'Plotly visualization'}
    new_query = 'exit-repair'

    if frame.error in ['invalid_dataframe', 'dataframe_is_none']:
      source_str = source_strings[frame.source]
      prompt = broken_dataframe_prompt.format(source=source_str, error_message=frame.warning, code=frame.code,
                            history=context.compile_history(), col_desc=self.tab_col_to_nl(valid_col_dict))
      raw_code = self.api.execute(prompt)

      if 'select' in raw_code.lower():
        new_query = PromptEngineer.apply_guardrails(raw_code, 'sql')
      elif 'df' in raw_code.lower():
        new_query = PromptEngineer.apply_guardrails(raw_code, 'python')
    return new_query

  def attempt_describe_repair(self, context, state):
    new_query = 'exit-repair'
    if len(state.additional_facts) > 0:
      fact_string = '\n'.join(state.additional_facts)
      prompt = add_facts_prompt.format(history=context.compile_history(), thought=state.thought, facts=fact_string)
      raw_code = self.api.execute(prompt)

      if 'select' in raw_code.lower():
        new_query = PromptEngineer.apply_guardrails(raw_code, 'sql')
    self.attempts += 3
    return new_query

  def attempt_manual_repair(self, frame, state):
    old_query = frame.code

    inner_value_regex = r"=\s*\'([^\']*)\'"
    value_match = re.search(inner_value_regex, old_query)
    year_regex = r"year\s*=\s*(\d{4})"
    year_match = re.search(year_regex, old_query)

    if value_match:  # there's a string inside
      full_match = value_match.group()
      before_str = full_match[2:-1]

      if self.attempts == 0:
        after_str = before_str.lower()
        new_query = old_query.replace(before_str, after_str)
      elif self.attempts == 1:
        after_str = before_str.upper()
        new_query = old_query.replace(before_str, after_str)
      elif self.attempts == 2:
        after_str = before_str.title()
        new_query = old_query.replace(before_str, after_str)

    elif year_match:
      full_match = year_match.group()
      try:
        year = int(full_match[-4:])
        new_query = old_query.replace(str(year), str(year - 1))
      except ValueError as ecp:
        self.attempts += 3
    else:
      self.attempts += 2   # nothing we can do with our current methods
      new_query = 'exit-repair'
    return new_query

  def attempt_fix_empty_results(self, frame, context, valid_col_dict):
    new_query = 'exit-repair'

    if frame.error == 'empty_results' and 'RESOLVE' not in self.actions:
      prompt = empty_results_prompt.format(history=context.compile_history(), query=frame.code, 
                        results=frame.get_data('md'), col_desc=self.tab_col_to_nl(valid_col_dict))
      raw_code = self.api.execute(prompt)

      if 'select' in raw_code.lower():
        new_query = PromptEngineer.apply_guardrails(raw_code, 'sql')
    return new_query

  def attempt_staging_table(self, frame, context, state, valid_col_dict):
    # Perhaps adding a column as an intermediate step will make it easier to generate a working query
    if 'RESOLVE' in self.actions:
      return frame, state

    history = context.compile_history()
    cols = PromptEngineer.column_rep(valid_col_dict, with_break=True)
    prompt = staging_table_prompt.format(history=history, columns=cols, query=frame.code)
    raw_output = self.api.execute(prompt)
    decision = PromptEngineer.apply_guardrails(raw_output, 'json')

    if 'error' in decision.keys():
      return frame, state
    else:
      num_sources = len(decision['source'])
      num_targets = len(decision['target'])

    if num_targets > 0:
      frame.warning = decision['thought']

      if num_sources == 1 and num_targets == 1:
        new_dax = '005'    # derive a new column based on an existing column
      elif num_sources > 1 and num_targets == 1:
        new_dax = '05C'    # merge multiple columns into a single column
      elif num_sources == 1 and num_targets > 1:
        new_dax = '5CD'    # split a column into multiple columns with text2cols
      elif num_sources > 1 and num_targets > 1 and num_sources == num_targets:
        new_dax = '055'    # multiple columns to multiple columns
      else:
        return frame, state

      new_flow = flow_selection[new_dax](valid_col_dict)
      for source_entity in decision['source']:
        new_flow.slots['source'].add_one(**source_entity)
      for target_entity in decision['target']:
        new_flow.slots['target'].add_one(**target_entity)
      new_flow.is_newborn = False

      self.actions.add('STAGING')
      state.flow_stack.append(new_flow)

      state.store_dacts('', new_dax)
      state.has_staging = True
    return frame, state

  def tab_col_to_nl(self, columns_dict, connector='and'):
    # Converts a dictionary of tab: [col1, col2] to a natural language description
    nl_tabs = []
    for table, col_list in columns_dict.items():
      nl_cols = PromptEngineer.array_to_nl(col_list, 'and')
      nl_tabs.append(f"{nl_cols} in the {table} table.")
    return '\n'.join(nl_tabs)

  def finalize_frame(self, context, frame, state, world):
    # Remove alignment check for now, and only add back if there are more usecases
    # frame = self.check_alignment(frame, world, state)
    # check if possible changes have been made to the underlying table
    if self.actions.intersection({'CLEAN', 'TRANSFORM', 'ISSUE'}):
      frame.has_changes = True

    insight_flow = state.get_flow(flow_type='insight')
    if insight_flow and insight_flow.stage == 'automatic-execution':
      if insight_flow.slots['plan'].approved and state.has_plan:
        state.keep_going = True

    if not frame.has_content:
      df_head = self.database.db.tables[frame.raw_table].head(default_limit)
      if frame.source in ['default', 'sql'] and len(frame.code) == 0:
        default_query = f"SELECT * FROM {frame.raw_table} LIMIT {default_limit};"
        frame.set_data(df_head, default_query, 'sql')
      else:
        frame.set_data(df_head)
      if frame.tab_type == 'derived':
        frame.tab_type = 'direct'

    if frame.tab_type == 'derived':
      predicted_props, typed_data = self.check_types(context, frame.data)
      frame.set_data(typed_data, frame.code, frame.source)
      active_entities = frame.store_display_view(predicted_props, self.database.db.shadow)
      frame = self.attach_subtype(frame, world, active_entities, predicted_props)
    else:
      frame = self.attach_subtype(frame, world, state.entities)

    if self.verbose:
      print(f"  Frame - tab_name: {frame.raw_table}, tab_type: {frame.tab_type}, source: {frame.source}")
      if frame.error:
        print(f"  Failure type: {frame.error}")
      if state.intent != 'Converse':
        print(f"  Updated state:\n{state}")
    return frame

  def review_flow(self, context, frame, state, world):
    # Checks the current flow to see if the action was completed
    flow = state.get_flow()

    if frame.is_successful():
      if 'SUGGEST' in self.actions or 'INTERACT' in self.actions:
        print('User feedback is needed')
    elif 'CLARIFY' in self.actions:
      if 'INTERACT' in self.actions:
        self.actions.remove('CLARIFY')
      elif flow.parent_type == 'Detect' and flow.is_newborn:
        state.flow_stack.pop()  # remove issue flow from the stack since already dealing with clarification
    elif 'SELECT' in self.actions and 'PREFER' not in self.actions:
      frame, state = self.consider_preferences(context, flow, frame, state, context.preferences)
    elif frame.error in ['invalid_dataframe', 'dataframe_is_none']:
      self.actions.add('CLARIFY')
      state.ambiguity.declare('general')
      error_object = {'code': frame.code, 'error': frame.error.replace('_', ' ')}
      state.errors.append(error_object)
    elif frame.error in ['empty_results', 'null_values_found', 'needs_more_info']:
      frame, state = self.attempt_staging_table(frame, context, state, world.valid_columns)
      pass  # minor error, staging was not needed
    else:
      self.actions.add('CLARIFY')
      if flow is None:
        state.ambiguity.declare('general')
      elif frame.error == 'code_generation':
        frame, state = self.handle_coding_errors(flow, frame, state, context)
      else:
        frame, state = self.handle_flow_ambiguity(flow, frame, state, context)

    flow.is_newborn = False
    flow.is_uncertain = False
    state.errors = []   # reset the error history for the next iteration
    return state

  def follow_up_execution(self, prior_query, prior_state):
    # execute a query immediately after being exposed on the Flow stack
    try:
      db_output = self.database.db.execute(prior_query)
      frame = self.validate_dataframe(db_output, prior_query, 'sql', prior_state, 'derived')
    except Exception as ecp:
      print(f"Follow up Execution Error - {ecp}")
      return {}, False
    return frame, frame.is_successful()

  def handle_coding_errors(self, flow, frame, state, context):
    code_1, error_1 = state.errors[0]['code'], state.errors[0]['error']
    if len(state.errors) > 1:
      second_error = state.errors[1]
      code_2, error_2 = second_error['code'], second_error['error']
      code_gen_2 = f"We then attempted to generate the following code:\n{code_2}\nThis then led to a new error: {error_2}"
    else:
      code_gen_2 = ''

    prompt = code_generation_error.format(dact_goal=flow.goal, history=context.compile_history(), thought=state.thought,
                                          code_one=code_1, error_one=error_1, code_generation_two=code_gen_2)
    raw_output = self.api.execute(prompt)
    decision = PromptEngineer.apply_guardrails(raw_output, 'json')

    if 'error' in decision.keys():
      state.ambiguity.declare('specific', flow=flow.name())
    else:
      state.proposed_action = decision['action']          # pro-active action
      state.ambiguity.declare('partial')                  # uncertainty level
      state.ambiguity.observation = decision['response']  # clarification question

    return frame, state

  def handle_flow_ambiguity(self, flow, frame, state, context):
    prompt = clarify_ambiguity_prompt.format(goal=flow.goal, warning_msg=frame.warning,
                                             history=context.compile_history(look_back=3), thought=state.thought)
    raw_output = self.api.execute(prompt)
    decision = PromptEngineer.apply_guardrails(raw_output, 'json')

    if 'error' in decision.keys():
      state.ambiguity.declare('specific', flow=flow.name())
    else:
      state.ambiguity.declare(decision['level'])          # uncertainty level
      state.ambiguity.observation = decision['response']  # clarification question
    return frame, state

  def consider_preferences(self, context, flow, frame, state, preferences):
    # Check if the user has preferences that can be applied to the current frame
    user_pref = context.find_relevant_preference()
    self.actions.add('CLARIFY')

    if user_pref:
      if user_pref.endorsed:
        ranked_pref = user_pref.top_rank()
        state = self.apply_preference(state, user_pref, ranked_pref)

      else:
        convo_history = context.compile_history(look_back=3)
        prompt = ask_for_pref_prompt.format(history=convo_history, preference=user_pref.name)
        clarification_question = self.api.execute(prompt)
        if clarification_question.lower() != 'none':
          state.ambiguity.observation = clarification_question.strip()

    if len(state.ambiguity.observation) == 0:
      frame, state = self.handle_flow_ambiguity(flow, frame, state, context)
    return frame, state

  def apply_preference(self, state, user_pref, ranked_pref):
    # TODO: actually run through the policy again to see if results improve, for now just ask for clarification
    preference_name = user_pref.name
    message = f"Previously, you mentioned that when talking about '{preference_name}', you prefer to use '{ranked_pref}'."
    message += " Does that apply to the current situation?"
    state.ambiguity.observation = message
    return state

  def attach_subtype(self, frame, world, entities, properties={}):
    # Add subtype info to the columns in each of the given entities
    for entity in entities:
      tab_name, col_name = entity['tab'], entity['col']
      column_props = {}

      if col_name == '*':
        continue

      elif tab_name in world.metadata['schema']:
        try:
          column_props = world.metadata['schema'][tab_name].get_type_info(col_name)
        except KeyError as ecp:
          print(f"  Warning: {col_name} not found in world schema")

      elif col_name in properties:
        column_props = properties[col_name]

      elif col_name in frame.data.columns:
        column_props = TypeCheck.build_properties(col_name, frame.data[col_name])

      if len(column_props) > 0:
        frame.properties[f"{tab_name}.{col_name}"] = column_props['subtype']
    return frame

  def check_types(self, context, table, properties={}):
    num_columns, num_rows = len(table.columns), len(table)

    # Take a first pass at predicting the datatype and subtype for each column in the table using the model API
    predicted_properties = {}
    if num_columns > 0 and num_columns <= 10:
      convo_history = context.compile_history()
      table_md = PromptEngineer.display_preview(table, max_rows=32)
      prompt = type_check_prompt.format(history=convo_history, content=table_md)

      if len(properties) > 0:
        type_prediction = {'columns': properties}
      else:
        user_msg = "Each column should have a datatype and subtype."
        raw_output = self.api.execute(prompt, sys_override={'role': 'user', 'content': user_msg})
        type_prediction = PromptEngineer.apply_guardrails(raw_output, 'json')

      predicted_properties = attach_property_details(type_prediction['columns'], num_rows)
      predicted_properties = one_off_col_mismatch(table, predicted_properties)

      for col_name, column in table.items():
        try:
          col_props = predicted_properties[col_name]
          column, col_props = self.database.db.shadow.convert_to_type('temp', column, col_props)
          predicted_properties[col_name] = col_props
          table[col_name] = column
        except Exception as ecp:
          print(f"Error in running type check for column {col_name}: {ecp}")
          continue

    # If any of the columns are missing, then rely on the TypeCheck class to make a guess
    if len(predicted_properties) < num_columns:
      for col_name, column in table.items():
        if col_name not in predicted_properties:
          col_props = TypeCheck.build_properties(col_name, column)
          column, col_props = self.database.db.shadow.convert_to_type('temp', column, col_props)
          predicted_properties[col_name] = col_props
          table[col_name] = column

    return predicted_properties, table

  def update_system_prompt(self, changed_tables: list, world, context, flow):
    for changed_table in changed_tables:
      self.database.db.complete_registration(changed_table)
      if ' ' in changed_table or '-' in changed_table:
        self.database.special_char_tables.add(changed_table)

      table_content = self.database.db.tables[changed_table]
      if 'format' in flow.slots.keys():
        world.declare_metadata(table_content, changed_table, self.database.db, flow)
      else:
        world.update_metadata(table_content, changed_table, self.database.db.shadow, flow)

    world.set_defaults(self.database.db)
    sys_prompt = context.write_system_prompt(self.database.db)
    self.api.set_system_prompt(sys_prompt)
    self.database.db.api.set_system_prompt(sys_prompt)

  def set_new_table_metadata(self, new_tab_name, world, context, table_content, old_tab_names, properties={}):
    # Register new table within the PEX database and MemoryDB
    if ' ' in new_tab_name or '-' in new_tab_name:
      self.database.special_char_tables.add(new_tab_name)
    predicted_props, table_content = self.check_types(context, table_content, properties)
    self.database.db.register_new_table(context, new_tab_name, old_tab_names, table_content)

    # Update the metadata for the new tables
    finalized_props = world.construct_metadata(table_content, predicted_props, new_tab_name, old_tab_names)
    world.construct_issue_md(new_tab_name, finalized_props, self.api)
    self.database.db.engineers[new_tab_name] = PromptEngineer(finalized_props, new_tab_name, self.api)
    world.set_defaults(self.database.db)

  def fill_preference_details(self, context, state, world):
    """Pre-action hook to handle the flow before taking action"""
    preference = context.check_user_preferences(endorsed=True)
    if not preference: return state
    pref = preference.top_rank(include_detail=True)
    value, detail = pref['value'], pref['detail']

    if preference.name == 'caution':
      return state

    elif len(preference.entity) == 0:
      # attempt to fill the preference
      if preference.name == 'goal':
        # goal = f"The user is trying to determine the 'best' of something according to the {value} of {detail}."
        goal = f"The user is trying to determine the 'best' of something according to the {value}."
      elif preference.name == 'timing':
        # goal = f"The user wants to review 'recent' data, which is considered the {detail} {value}."
        goal = f"The user wants to review 'recent' data, which is considered the {value}."
      elif preference.name == 'special':
        # goal = f"The user gathering information for the week, which goes from {value} to {detail}."
        goal = f"The user gathering information for the week, which starts on {value}."

      convo_history = context.compile_history()
      valid_col_str = PromptEngineer.column_rep(world.valid_columns, with_break=True)
      prompt = preference_entity_prompt.format(goal_description=goal, history=convo_history, valid_cols=valid_col_str)
      raw_output = self.api.execute(prompt)
      prediction = PromptEngineer.apply_guardrails(raw_output, 'json')
      entity = prediction['target']

      if prediction['confidence'] == 'high':
        preference.assign_entity(entity['tab'], entity['col'], ver=True)  # the model is over-confident at the moment
      elif prediction['confidence'] == 'medium':
        preference.assign_entity(entity['tab'], entity['col'], ver=False)
      else:  # confidence == low
        preference.assign_entity(entity['tab'], entity['col'], ver=False)
        self.actions.add('CLARIFY')

    elif not preference.entity['ver']:
      self.actions.add('CLARIFY')
      state.ambiguity.declare('confirmation', slot=f"meaning of {preference.name}", values=[value])
      col_str = preference.entity['col']

      if preference.name == 'goal':
        clarification = f"When determining the 'best' of something according to the {value} of {detail}, I will use the {col_str} column."
      elif preference.name == 'timing':
        clarification = f"When reviewing 'recent' data, I will use {col_str} to determine {detail} {value}."
      elif preference.name == 'special':
        clarification = f"When checking for the start of the week, I will use the {col_str} column."

      question = [" Does that work?", " Is that correct?", " Is that ok?"]
      clarification += random.choice(question)
      state.ambiguity.observation = clarification

    return state

  def fallback_policy(self, context, state, world):
    old_flow = state.flow_stack.pop()  # drop the current flow since it was not correct
    new_dax = old_flow.fall_back
    state.store_dacts(dax=new_dax)
    new_flow = flow_selection[new_dax](world.valid_columns)

    if state.has_issues:
      state.flow_stack.append(old_flow)  # Resolve flow is still relevant, so we put it back
    else:
      self.actions.clear()

    prefilled_slot = old_flow.slots[old_flow.entity_slot].filled
    if prefilled_slot:
      for entity in old_flow.slots[old_flow.entity_slot].values:
        if entity.get('ver', False) or not old_flow.verify_to_transfer:
          ent_slot = new_flow.entity_slot
          new_flow.slots[ent_slot].add_one(**entity)

    if 'operation' in new_flow.slots and 'operation' in old_flow.slots:
      new_flow.slots['operation'].values = old_flow.slots['operation'].values

    state.flow_stack.append(new_flow)
    return self.take_action(context, state, world)

  def take_action(self, context, state, world):
    """ Takes action based on the dact """
    dax = state.get_dialog_act(form='hex')
    intent = state.intent

    if intent == 'Analyze':
      state = self.fill_preference_details(context, state, world)
      frame, state = self.analyze_policies(context, state, world, dax)
    elif intent == 'Visualize':
      frame, state = self.visualize_policies(context, state, world, dax)
    elif intent == 'Clean':
      frame, state = self.clean_policies(context, state, world, dax)
    elif intent == 'Transform':
      frame, state = self.transform_policies(context, state, world, dax)
    elif intent == 'Detect':
      frame, state = self.detect_policies(context, state, world, dax)
    elif intent == 'Internal':
      frame, state = self.internal_policies(context, state, world, dax)

    flow = state.get_flow()
    if flow.fall_back:
      frame, state = self.fallback_policy(context, state, world)

    return frame, state

  def talking_action(self, context, state, valid_entities, world):
    """ Takes action based on the dact """
    frame = self.default_frame(state, valid_entities)
    dact_list = state.get_dialog_act(form='list')
    dax = state.get_dialog_act(form='hex')

    if dax in ['00A', '00B', '00C']:  # describe, tab/row/col nouns
      if len(state.entities) == 0:
        state.entities = [{'tab': state.current_tab, 'col': '*', 'ver': False}]
      else:
        state.current_tab = state.entities[0]['tab']
      frame = Frame(state.current_tab)

    elif dax in ['048', '068', '248', '268']:
      self.actions.add('PREFER')        # pull and update user preferences
      frame, state = self.user_preference_policies(context, state, world, dax)
    elif dax.endswith('E') or dax.endswith('F'):
      frame, state = self.accept_reject_policies(context, state, world, dact_list)

    else:
      frame, state = self.is_computation_needed(context, frame, state, world)
    return frame, state

  def manage(self, context, world):
    """ Main function that executes the policy and returns the final frame """
    state = world.current_state()
    valid_col_dict = world.valid_columns
    valid_entities = state.dict_to_entity(valid_col_dict)

    if len(state.command_type) > 0:
      self.actions.add("COMMAND")
      frame, state = self.execute_command(context, state, world)
    elif state.intent == 'Converse':
      frame, state = self.talking_action(context, state, valid_entities, world)
    else:  # take action on what needs to be done based on dact distribution
      frame, state = self.take_action(context, state, world)

      while frame.error and self.attempts < 4 and frame.source != "default":
        frame = self.repair_frame(context, frame, state, valid_col_dict)
        self.attempts += 1
      self.attempts = 0   # reset attempt count
      state = self.review_flow(context, frame, state, world)

    frame = self.finalize_frame(context, frame, state, world)
    return frame
