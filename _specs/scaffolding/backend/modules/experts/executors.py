import re
import ast
import random
import time as tm
import pandas as pd
import numpy as np

import math
import scipy
import traceback
import matplotlib
from datetime import datetime as dt

matplotlib.use('Agg')  # To prevent display errors, since we shouldn't be plotting at this stage

from backend.assets.ontology import default_limit, common_tlds
from backend.components.engineer import PromptEngineer
from backend.prompts.for_executors import *
from backend.utilities.pex_helpers import quote_tables

class BasePEX(object):
  def __init__(self, api, verbose):
    self.api = api
    self.verbose = verbose
    self.special_char_tables = set()

  def execute_with_retries(self, state, task, prompt, convo_history, preview='', valid_tabs=[]):
    """ Execute either python or sql code snippet and retry up to three times if an error occurs
      * api - Foundation Model API object
      * state - DialogueState object
      * task - full name of the flow being executed in Intent(dact) format
      * prompt - message to be sent to the API
      * convo_history - conversation history as a long string, compiled from context object
    """
    attempts_left = 3
    has_error = True
    num_max_tokens = state.slices.get('max_tokens', 512)
    error_msg, generated_code = "", ""

    if task.startswith('Analyze') or task.startswith('Visualize'):
      repair_template = sql_repair_prompt
      code_type = 'sql'
    else:
      repair_template = pandas_repair_prompt
      code_type = 'python'
      extra_context = {'self': self, 'pd': pd, 'np': np, 're': re, 'random': random}
      if len(valid_tabs) == 2 and valid_tabs[1] == 'Resolve':
        task = valid_tabs.pop()
        main_df = valid_tabs.pop()
        extra_context['main_df'] = main_df

    while attempts_left > 0 and has_error:
      start_time = tm.time()

      if has_error and len(error_msg) > 0:
        state.errors.append({'code': generated_code, 'error': error_msg})
        print(f"Attempting to fix {code_type.upper()} code ...")
        thought = f"Thought: {state.thought}\n" if len(state.thought) > 0 else ""
        prompt = repair_template.format(prior_code=generated_code, execution_error=error_msg, history=convo_history,
                                        thought=thought, dialogue_state=str(state), data_preview=preview)
      raw_code = self.api.execute(prompt, version='claude-sonnet', max_tok=num_max_tokens)

      if raw_code.lower().startswith('error'):
        error_message = raw_code.split('Error:')[1]
        print(f"  {task} Error -", error_message)
        return error_message, 'error'   # early return to indicate ambiguous scenario

      quoted_code = quote_tables(raw_code, self.special_char_tables) if code_type == 'sql' else raw_code
      generated_code = PromptEngineer.apply_guardrails(quoted_code, code_type, valid_tabs)
      print(f"  {task} took {tm.time() - start_time:.2f} seconds")

      try:
        if self.incomplete_code_errors(generated_code, code_type):
          num_max_tokens *= 2
          raise ValueError("The generated code appears to be truncated due to token limit, please try again.")
        elif task.startswith('Analyze') or task.startswith('Visualize'):
          result = self.db.execute(generated_code)
        else:
          exec(generated_code, extra_context)
          result = self.db.tables[state.current_tab].head(default_limit)

        has_error = False
      except Exception as ecp:
        print(f"{code_type.upper()} Code Execution Error - {ecp}")
        if 'never closed' in str(ecp):
          num_max_tokens *= 2
        tb_lines = traceback.format_exception(ecp.__class__, ecp, ecp.__traceback__)
        error_msg = ''.join(tb_lines[-5:])
        has_error = True
      attempts_left -= 1

    if has_error:
      return error_msg, 'error'
    return result, generated_code

  def generate_artifact(self, context, prompt, state, custom_params={}):
    """ Unlike execute_with_retries, this method does not operate on the table, but instead returns some artifact.
    Other differences include: 
      * extra libraries are included as part of the context, but notably not 'self'
      * does not use valid_tabs, since we are not operating on a table
      * does not check for execution errors, but _does_ check for function syntax errors
      * doubles the starting max tokens for code generation and increases further with each retry
    """
    attempts_left = 3
    has_error = True
    error_msg, generated_code = "", ""
    convo_history = context.compile_history()

    artifact_key = custom_params.pop('artifact_key', 'result')
    data_preview = custom_params.pop('data_preview', 'N/A')
    trigger_phrase = custom_params.pop('trigger_phrase', '```python')
    execution_context = custom_params.pop('exec_context', {})
    prefix_string = custom_params.pop('prefix_string', '```')
    max_tokens = custom_params.pop('max_tokens', 1024)

    extra_context = {'np': np, 'pd': pd, 're': re, 'dt': dt, 'math': math, 'scipy': scipy}
    extra_context.update(execution_context)
    context_keys = PromptEngineer.array_to_nl(list(extra_context.keys()), connector='and')

    content = "You are an outstanding data analyst who is exceptionally skilled at writing Python code."
    content += f" You have access to {context_keys}. Do not try to import any other libraries."
    content += " Your output should be directly executable with no text or explanations before or after the code block."
    prompt_override = {'role': 'system', 'content': content}

    while attempts_left > 0 and has_error:
      start_time = tm.time()

      if has_error and len(error_msg) > 0:
        max_tokens = int(max_tokens * 1.414)
        state.errors.append({'code': generated_code, 'error': error_msg})
        print(f"Attempting to repair Python code ...")
        thought = f"Thought: {state.thought}\n" if len(state.thought) > 0 else ""
        prompt = pandas_repair_prompt.format(prior_code=generated_code, execution_error=error_msg, history=convo_history,
                                        thought=thought, dialogue_state=str(state), data_preview=data_preview)

      raw_code = self.api.execute(prompt, prefix=prefix_string, max_tok=max_tokens, sys_override=prompt_override)
      trigger_phrase = '```python' if trigger_phrase not in raw_code else trigger_phrase
      generated_code = PromptEngineer.activate_guardrails(raw_code, trigger_phrase)
      print(f"  Python code generation took {tm.time() - start_time:.2f} seconds")

      try:
        if artifact_key not in ['result', 'fig']:
          try:
            parsed = ast.parse(generated_code)
            if not (len(parsed.body) == 1 and isinstance(parsed.body[0], ast.FunctionDef)):
              raise ValueError("Code must contain exactly one function definition and no import statements")
          except SyntaxError as syn_err:
            raise ValueError(f"Invalid Python syntax: {syn_err}")

        exec(generated_code, extra_context)
        result = extra_context.get(artifact_key, 'error')
        if result == 'error':
          raise ValueError("The requested computation is beyond my current capabilities.")
        has_error = False
      except Exception as ecp:
        print(f"Python Execution Error - {ecp}")
        tb_lines = traceback.format_exception(ecp.__class__, ecp, ecp.__traceback__)
        error_msg = ''.join(tb_lines[-5:])
        has_error = True
      attempts_left -= 1

    if has_error:
      return error_msg, 'error'
    return result, generated_code

  def execute_on_custom_df(self, state, context, support, main_df):
    """ Execute on a custom dataframe holding the values as they are displayed rather than stored """
    attempts_left = 3
    has_error = True
    error_msg, generated_code = "", ""

    prompt, task, row_ids = support['prompt'], support['task'], support['row_ids']
    convo_history = context.compile_history()

    while attempts_left > 0 and has_error:
      start_time = tm.time()

      if has_error and len(error_msg) > 0:
        state.errors.append({'code': generated_code, 'error': error_msg})
        print(f"Attempting to fix Python code ...")
        thought = f"Thought: {state.thought}\n" if len(state.thought) > 0 else ""
        prompt = pandas_repair_prompt.format(prior_code=generated_code, execution_error=error_msg,
                                        history=convo_history, thought=thought, dialogue_state=str(state))
      raw_code = self.api.execute(prompt, version='claude-sonnet')

      if raw_code.lower().startswith('error'):
        error_message = raw_code.split('Error:')[1]
        print(f"  {task} Error -", error_message)
        return error_message, 'error'   # early return to indicate ambiguous scenario

      valid_lines = []
      for line in raw_code.split('\n'):
        if len(line) == 0:
          continue
        if any([line.startswith(phrase) for phrase in ["```", "import", "# ", "_"]]):
          continue
        else:
          vline = line.rstrip()
        print(f"  {vline}")
        valid_lines.append(vline)

      generated_code = "\n".join(valid_lines)
      print(f"  {task} took {tm.time() - start_time:.2f} seconds")

      try:
        extra_context = {'self': self, 'pd': pd, 'main_df': main_df, 'row_ids': row_ids}
        exec(generated_code, extra_context)
        has_error = False
      except Exception as ecp:
        print(f"Python Code Execution Error - {ecp}")
        error_msg = str(ecp)
        has_error = True
      attempts_left -= 1

    if has_error:
      return error_msg, 'error'
    return main_df, generated_code

  def retry_query_with_hint(self, context, db_output, flow, metric_name, query_code, state):
    """ Attempts to re-generate SQL query, with additional hint based on flow-specific scenario """
    print(f"Retrying query with hint ...")
    display_df = db_output.fillna("N/A").to_string(index=False)
    if len(state.errors) > 0:
      query_code = state.errors[-1]['code']
    convo_history = context.compile_history()

    if flow.name() == 'query':
      prompt = query_hint_prompt.format(dataframe=display_df, thought=state.thought, history=convo_history,
                                            dialogue_state=str(state), sql_query=query_code)
    elif flow.name() == 'measure':
      prompt = analyze_hint_prompt.format(metric=metric_name, thought=state.thought, dataframe=display_df,
                                            history=convo_history, sql_query=query_code)
    raw_code = self.api.execute(prompt, version='claude-sonnet')
    revised_code = PromptEngineer.apply_guardrails(raw_code, 'sql')

    if revised_code == 'error':
      print("Could not fix the SQL query, even with hint")
      return False, 'error'
    elif query_code == revised_code:
      return db_output, query_code
    else:
      # TODO: hack to remove repeated WHERE clauses
      existing_lines = set()
      final_lines = []
      replace_flag = False

      for line in revised_code.split('\n'):
        stripped = line.strip()
        if stripped.startswith('WHERE') and stripped in existing_lines:
          replace_flag = True
        elif replace_flag and stripped.startswith('AND'):
          line = line.replace('AND', 'WHERE', 1)
          final_lines.append(line)
          replace_flag = False
        else:
          existing_lines.add(stripped)
          final_lines.append(line)
      revised_code = '\n'.join(final_lines)

      # execute the revised SQL query
      revised_df = self.db.execute(revised_code)
      return revised_df, revised_code

  def incomplete_code_errors(self, generated_code, code_type):
    """ Check for common errors that indicate the code is incomplete """
    if code_type == 'python':
      common_methods = ['replace', 'fillna', 'dropna', 'apply', 'map', 'transform', 'agg', 'groupby', 'merge', 'join']
      method_match = f"=\\s*.+\\.({'|'.join(common_methods)})$"
      # function call without closing paren, and assignment without value
      patterns = [r'\w+\($', r'=\s*$', method_match]
      return any(re.search(regex, generated_code) for regex in patterns)
    elif code_type == 'json':
      if re.search(r'{\s*$', generated_code):
        return True       # dict/block without closing
      elif re.search(r'\[\s*$', generated_code):
        return True       # list without closing

    return False

class DatabaseExecutor(BasePEX):
  # query a in-memory database, populated by CSVs

  def __init__(self, api, database, schema_data, verbose):
    super().__init__(api, verbose)
    self.db = database
    self.all_tab_names = list(database.tables.keys())    # list

    self.valid_columns = {}               # dict of lists
    for table_name in self.all_tab_names:
      if ' ' in table_name or '-' in table_name:
        self.special_char_tables.add(table_name)
      table = database.tables[table_name]
      self.valid_columns[table_name] = list(table.columns)

    self.build_table_desc()
    self.build_year_reminder(schema_data)

  def get_entities_schema(self, entities, state, as_list=True):
    entity_dict = state.entity_to_dict(entities)

    schema_output = []
    for tab_name, columns in entity_dict.items():
      query = f"PRAGMA table_info({tab_name})"
      col_info = self.db.execute(query)
      col_to_type = dict(zip(col_info['name'], col_info['type']))
      schema_output.append(f"Table - {tab_name}")

      for col_name in columns:
        if col_name in col_to_type:
          schema_output.append(f"{col_name}: {col_to_type[col_name]}")

    if as_list:
      return schema_output
    else:
      return "\n".join(schema_output)

  def query_data(self, context, flow, state, world):
    """ If successful, returns a dataframe and the SQL query used to generate it as a string
    Otherwise, returns an error message and the string 'error' """
    if state.has_plan:
      return self.execute_step(context, flow, state, world)

    convo_history = context.compile_history()
    preferences = context.write_pref_description()
    ops_string = PromptEngineer.array_to_nl(flow.slots['operation'].values, connector='and')

    source_df = self.db.tables[state.current_tab]
    source_cols = [ent['col'] for ent in flow.slots['source'].values if ent['tab'] == state.current_tab]
    tab_col_str = PromptEngineer.tab_col_rep(world)
    source_md = PromptEngineer.display_samples(source_df, source_cols, num_samples=16)

    preview_lines = ["_Data Preview_"]
    preview_lines.append(source_md)
    preview_lines.append("\n_Column Schema_")
    preview_lines.extend(self.get_entities_schema(flow.slots['source'].values, state))
    preview_desc = "\n".join(preview_lines)

    match state.get_dialog_act():
      case '001': prompt_template = sql_for_query_prompt
      case '01A': prompt_template = sql_for_pivot_prompt
      case '003': prompt_template = sql_for_chart_prompt
    prompt = prompt_template.format(year_reminder=self.reminder, data_preview=preview_desc, history=convo_history,
              thought=state.thought, valid_tab_col=tab_col_str, operations=ops_string, pref_reminder=preferences)

    task = flow.name(full=True)
    result, sql_query = self.execute_with_retries(state, task, prompt, convo_history, source_md)
    return result, sql_query

  def execute_step(self, context, flow, state, world):
    """ Returns a dataframe and the SQL query used, where the focus is on the operations and not the conversation """
    detect_flow = state.get_flow(flow_type='insight', allow_interject=False)
    current_plan = detect_flow.slots['plan']

    step_num = sum([1 for step in current_plan.steps if step['checked']]) + 1
    step_desc = current_plan.current_step('description')
    plan_desc = PromptEngineer.display_plan(current_plan.steps, join_key='\n')

    main_tab = flow.slots['source'].table_name()
    source_df = self.db.tables[main_tab]
    source_cols = [ent['col'] for ent in flow.slots['source'].values if ent['tab'] == main_tab]
    source_md = PromptEngineer.display_samples(source_df, source_cols, num_samples=16)

    tab_col_str = PromptEngineer.tab_col_rep(world)
    goal = detect_flow.slots['analysis'].value
    preferences = context.write_pref_description()

    match state.get_dialog_act():
      case '001': prompt_template = sql_query_plan_prompt
      case '01A': prompt_template = sql_pivot_plan_prompt
      case '003': prompt_template = sql_chart_plan_prompt

    prompt = prompt_template.format(step_number=step_num, step_description=step_desc, overall_plan=plan_desc, goal=goal,
                                        data_preview=source_md, valid_tab_col=tab_col_str, thought=state.thought,
                                        previous_queries='\n'.join(world.previous_queries()), pref_reminder=preferences)
    task = flow.name(full=True)
    convo_history = context.compile_history(look_back=7, keep_system=False)
    state.slices['max_tokens'] = 1024  # double the max tokens for plan execution
    result, sql_query = self.execute_with_retries(state, task, prompt, convo_history, source_md)

    del state.slices['max_tokens']
    sql_query = f"-- Step {step_num}:\n" + sql_query
    return result, sql_query

  def analyze_data(self, context, flow, prompt, state):
    """ Whereas query calculates variables as the Clause level, analyze calculates metrics at the Expression level """
    metric_name = flow.slots['metric'].formula.get_name()
    task = flow.name(full=True)
    convo_history = context.compile_history(look_back=9, keep_system=False)
    db_output, query_string = self.execute_with_retries(state, task, prompt, convo_history)

    if query_string != 'error':
      # if the metric total within the dataframe is zero, then try to fix the query
      column_mapping = {col.lower(): col for col in db_output.columns}
      col_metric = column_mapping.get(flow.slots['metric'].value.lower())
      if col_metric and db_output[col_metric].sum() == 0:
        return self.retry_query_with_hint(context, db_output, flow, metric_name, query_string, state)

    return db_output, query_string

  def build_year_reminder(self, schema_data):
    self.reminder = ""
    for tab_name, valid_cols in self.valid_columns.items():
      for col_name in valid_cols:
        type_info = schema_data[tab_name].get_type_info(col_name, False)
        if type_info['subtype'] in ['year', 'date', 'timestamp']:
          self.reminder = "\nIf the request involves any sort of date (ie. months, weeks or quarters) without specifying a year, please filter for the year 2025."
          break

  def remove_data(self, table_name, row_ids):
    self.db.tables[table_name].drop(row_ids, inplace=True)

  def build_table_desc(self):
    if len(self.db.tables) > 1:
      table_names = list(self.db.tables.keys())
      last_table = table_names[-1]
      instances = []
      for t_name in table_names[:-1]:
        instances.append(f"db.{t_name} for the {t_name.title()} table")
      prefix_tables = ', '.join(instances)
      suffix_table = f", and db.{last_table}, corresponding to the {last_table.title()} table"
      table_description = prefix_tables + suffix_table
    elif len(self.db.tables) == 1:
      single_table = self.all_tab_names[0]
      table_title = single_table.replace('_', ' ').title()
      table_description = f"db.{single_table} corresponding to the {table_title} table"
    else:
      table_description = ""
    self.table_desc = table_description

  def manipulate_data(self, context, state, prompt, valid_tabs):
    """ If successful, returns a dataframe and the Python code used to generate it as a string
    Otherwise, returns a dataframe and the error message string """
    convo_history = context.compile_history()
    task = state.get_flow(allow_interject=False, return_name=True)
    result, pandas_code = self.execute_with_retries(state, task, prompt, convo_history, '', valid_tabs)
    return result, pandas_code
    
class WarehouseExecutor(BasePEX):
  # connections to Redshift, BigQuery, Snowflake, etc.

  def __init__(self, warehouse, verbose):
    super().__init__(verbose)
    self.warehouse = warehouse

  def queri_data(self, dialogue_state, messages, utterance, form="str"):
    nlu_output = f"User request: {utterance}\n{dialogue_state}"
    sql_query = sql_for_query_prompt.format(nlu_output=nlu_output)
    result = self.warehouse.execute(sql_query, form)
    return result

class GraphExecutor(BasePEX):
  # connections to Neo4j, Dgraph, Knowledge base of triples etc.
  def __init__(self, graph, verbose):
    super().__init__(verbose)
    self.graph = graph

  def queri_data(self, dialogue_state, messages, utterance, form="str"):
    nlu_output = f"User request: {utterance}\n{dialogue_state}"
    sql_query = sql_for_query_prompt.format(nlu_output=nlu_output)
    result = self.graph.execute(sql_query, form)
    return result
