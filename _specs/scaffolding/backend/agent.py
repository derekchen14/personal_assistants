import io
import re
import os
import json
import copy
import tempfile
import pandas as pd
from uuid import uuid4
from io import StringIO, BytesIO
from sentence_transformers import SentenceTransformer

from backend.components.world import World
from backend.components.context import Context
from backend.components.helpers import handle_breaking_errors, StorageDB, MemoryDB
from backend.components.loaders import SpreadsheetLoader, VendorLoader, WarehouseLoader
from backend.components.apis import ExternalAPI, InternalAPI

from backend.modules.nlu import NatLangUnderstanding
from backend.modules.pex import PolicyExecution
from backend.modules.res import ResponseGeneration
from database.tables import UserDataSource

from backend.utilities.interaction import *
from backend.utilities.routing import style_sql_message
from backend.prompts.general import conversation_metadata_prompt
from backend.utilities.manipulations import serialize_for_json
from database.tables import Utterance


class Agent(object):

  def __init__(self, user_id: int, args):
    """
    Assigns internal variables, initializes storage, context, world etc
    :param user_id: the user this agent works for. -1 if doesn't matter
    :param args: ML parameters. Defaults are: api_version="gpt-4o",
    temperature=0.1, threshold=0.6, drop_rate=0.1, max_length=512, level='cosine', verbose=True, debug=DEBUG
    """
    self.user_id = user_id
    self.verbose = args.verbose
    self.debug = args.debug
    self.loader = None
    self.conversation_id = None
    self.data_source_ids = [] # UUIDs for data sources entris in the database

    self.external = ExternalAPI(args)
    self.internal = InternalAPI(args)
    self.storage = StorageDB(args)              # Postgres
    self.initialize_session(args)

    embedder = SentenceTransformer('all-MiniLM-L12-v2')
    self.nlu = NatLangUnderstanding(args, self.external, self.internal, self.storage)
    self.pex = PolicyExecution(args, self.external, embedder)
    self.res = ResponseGeneration(args, self.external, embedder)

  def initialize_session(self, args):
    """ Initializes the agent with the default data """
    self.memory = MemoryDB(args, self.external)      # DuckDB
    self.context = Context(args.verbose)
    self.world = World(args)

  @handle_breaking_errors
  def understand_language(self, user_text, gold_dax):
    self.full_stream = ""       # holds the entire JSON output
    self.thought_stream = ""    # gathers just the thought portion
    self.still_thinking = True
    if len(user_text) < 2:
      return self.custom_error_message("Error: invalid input is too short.")

    last_actions = self.context.last_actions['Agent']
    last_state = self.world.current_state()

    if 'CLARIFY' in last_actions:
      # resolve the ambiguity stored in the state to prevent looping behavior
      last_state.ambiguity.resolve()
    self.context.add_turn('User', user_text, 'utterance')

    pred_dax = self.nlu.predict(self.context, self.world, gold_dax)
    if pred_dax == 'FFF' or pred_dax is None: # unsupported dax return immediately
      return last_state, 'unsupported'
    
    current_flow = self.nlu.active_flow
    if current_flow:   # if-clauses are purposely separated to prevent extra slot-filling for source
      if not current_flow.slots[current_flow.entity_slot].filled:
        # shortcut out of NLU to stream back thought to the user
        stream_of_thought = self.nlu.stream_of_thought(self.context, self.world)
        return stream_of_thought, 'stream'
    else:   # for Converse flows
      self.nlu.labels['entities'] = self.nlu.icl.predict_tab_and_col(self.context, last_state, self.world)

    dialogue_state = self.complete_nlu()
    return dialogue_state, 'state'

  def complete_nlu(self):
    new_state, old_state = self.nlu.track_state(self.context, self.world)
    flow_thought = self.nlu.labels.get('flow_thought', '')
    if len(new_state.thought) == 0 and len(flow_thought) > 0:
      new_state.thought = flow_thought

    current_flow = new_state.get_flow(allow_interject=False)
    if current_flow and current_flow.needs_to_think():
      spreadsheet = self.pex.database.db.tables
      new_state = self.nlu.contemplate(current_flow, new_state, self.context, self.world, spreadsheet)

    dialogue_state = self.nlu.finalize_state(new_state, old_state)
    self.world.insert_state(dialogue_state)
    return dialogue_state

  def user_interactions(self, payload):
    """ Given verified labels from user interaction, run the agent loop with that information. """
    state, valid_col_dict = self.world.current_state(), self.world.valid_columns

    match payload.flowType:
      case 'Analyze(measure)': labels, state = build_measure_labels(payload, state)
      case 'Visualize(plot)': labels, state = build_visualize_labels(payload, state)
      case 'Clean(dedupe)':  labels, state = remove_duplicates_labels(payload, state)
      case 'Clean(validate)':  labels, state = build_validate_labels(payload, state)
      case 'Transform(split)': labels, state = split_column_labels(payload, state)
      case 'Transform(merge)': labels, state = merge_columns_labels(payload, state)
      case 'Transform(join)':  labels, state = join_tables_labels(payload, state)
      case 'Detect(typo)': labels, state = identify_typos_labels(payload, state)

    # NLU is partially bypassed since we already know what actions we want to take.
    self.interactive_user_turn(payload, labels['dax'], labels['operations'])
    label_copy = copy.deepcopy(labels)  # to prevent the entailment of the original labels
    self.nlu.labels.update({**label_copy, 'score': 1.0, 'natural_birth': False})  # born from user interaction
    if labels['dax'] != '00F':
      self.nlu.active_flow = self.nlu.construct_flow(state, labels['dax'], valid_col_dict)

    new_state, prev_state = self.nlu.track_state(self.context, self.world)
    dialogue_state = set_state_columns(new_state, prev_state, payload, valid_col_dict, self.world.col_to_tab)
    self.nlu.reset_flags()
    self.world.insert_state(dialogue_state)

    # Execute PEX
    frame, actions, success = self.interactive_pex(dialogue_state, valid_col_dict)
    response, success = self.generate_response(frame, actions)
    return frame, response, success

  def interactive_pex(self, dialogue_state, valid_col_dict):
    try:
      frame, actions, keep_going = self.execute_policy()
      success = True
    except Exception as exp:
      valid_entities = dialogue_state.dict_to_entity(valid_col_dict)
      frame = self.pex.default_frame(dialogue_state, valid_entities)
      actions = ['CLARIFY']
      success = False

    if len(frame.code) > 0 and 'ANALYZE' in actions:
      self.set_panel_to_query(frame)
    return frame, actions, success

  def user_commands(self, payload):
    """ Given a command from the user, directly execute the command without going through the full loop """
    prev_state, valid_col_dict = self.world.current_state(), self.world.valid_columns

    if payload.flowType == 'Analyze(query)':
      labels = build_query_labels(payload, valid_col_dict)
      dialogue_state = command_flow(self.context, labels, prev_state, valid_col_dict)
      query_flow = dialogue_state.get_flow(flow_type='query')
      self.world.insert_state(dialogue_state)
      actions = ['COMMAND']

      try:
        frame, dialogue_state = self.pex.execute_command(self.context, dialogue_state, self.world)
        self.set_panel_to_query(frame)
        actions.append('ANALYZE')
        prev_frame = self.world.frames[-1]
        agent_utt_text = self.res.command_response(query_flow, self.context, frame, prev_frame)
      except Exception as exp:
        valid_entities = dialogue_state.dict_to_entity(valid_col_dict)
        frame = self.pex.default_frame(dialogue_state, valid_entities)
        self.res.top_panel = None
        agent_utt_text = f"Your modified query hit an error: {exp}"

    response = {'actions': actions, 'uncertainty': {}, 'message': agent_utt_text, 'tabType': frame.tab_type }
    if self.res.top_panel:
      response['interaction'] = self.res.top_panel['interaction']
    return frame, response

  def interactive_user_turn(self, payload, dax, ops):
    action_type = payload.flowType.split('(')[0].upper()

    self.context.add_turn('User', action_type, 'action')
    if payload.stage == 'build-variables':
      self.context.add_turn('User', f'The {ops[1]}. Separately, {ops[2]}.', 'utterance')
    else:
      self.context.add_turn('User', f'Please {ops[0]}.', 'utterance')

  def custom_error_message(self, error_message):
    payload = {'message': error_message, 'actions': [], 'ambiguity': {}, 'frame': None, 'interaction': None}
    output_type = "error"
    return payload, output_type

  def set_panel_to_query(self, frame):
    frame_msg, _ = style_sql_message(frame.code)
    frame_json = {'interaction': {'content': frame_msg, 'format': 'html', 'show': True, 'flowType': 'Default(flow)'}}
    self.res.top_panel = frame_json

  def execute_policy(self):
    self.pex.actions = set()
    curr_state = self.world.current_state()
    curr_state.keep_going = False  # start out conservative for now, default to just one pass

    frame = self.pex.manage(self.context, self.world)
    self.world.insert_frame(frame)

    actions_taken = list(self.pex.actions)  # convert from set to list
    self.context.add_actions(actions_taken, 'Agent')
    return frame, actions_taken, curr_state.keep_going

  def process_thoughts(self, chunk):
    if self.external.default_version.startswith('claude'):
      return self.process_claude_thoughts(chunk)
    elif self.external.default_version.startswith('gpt'):
      return self.process_gpt_thoughts(chunk)

  def process_gpt_thoughts(self, chunk):
    stream_json = {'interaction': {'content': '', 'format': 'html', 'show': True, 'flowType': 'Default(thought)'}}
    if self.nlu.labels['dax'] in ['002', '02D']:
      return self.full_gpt_thoughts(chunk, stream_json)
    message_chunk = chunk.choices[0].delta.content

    if message_chunk is None:   # there is no content, only a "role": "assistant"
      stream_json['interaction']['content'] = ''
    elif chunk.choices[0].finish_reason == 'stop':
      stream_json['interaction']['content'] = self.final_thought
    else:
      self.full_stream += message_chunk

      if len(self.thought_stream) < 8:
        stripped = message_chunk.strip()  # skip the first few words which is part of the prompt
        if len(stripped) > 0 and stripped not in ['```', 'json', '{', '"', 'thought', '":']:
          self.thought_stream += message_chunk

      elif self.still_thinking:
        self.thought_stream += message_chunk
        if '",\n' in self.thought_stream:
          self.final_thought = self.thought_stream.split('",\n')[0].strip()
          self.still_thinking = False
          stream_json['interaction']['content'] = self.final_thought
          return stream_json, True
        else:
          stream_json['interaction']['content'] = self.thought_stream

      else:
        stream_json['interaction']['content'] = self.final_thought

    return stream_json, self.still_thinking

  def process_claude_thoughts(self, chunk):
    stream_json = {'interaction': {'content': '', 'format': 'html', 'show': True, 'flowType': 'Default(thought)'}}
    if self.nlu.labels['dax'] in ['002', '02D']:
      return self.full_claude_thoughts(chunk, stream_json)

    if chunk.type == 'content_block_start':
      self.full_stream = '```json\n{\n  "'  # the agent prefill
    elif chunk.type == 'content_block_stop':
      stream_json['interaction']['content'] = self.final_thought
    elif chunk.type == 'content_block_delta':
      message_chunk = chunk.delta.text
      self.full_stream += message_chunk

      if len(self.thought_stream) < 8:
        message_chunk = self.strip_the_message(message_chunk)
        if len(message_chunk) > 0:
          self.thought_stream += message_chunk

      elif self.still_thinking:
        if len(self.thought_stream) > 16 and message_chunk.endswith('```'):
          message_chunk = message_chunk[:-3]  # truncate the outro portion
        self.thought_stream += message_chunk

        if '",\n' in self.thought_stream:
          self.final_thought = self.thought_stream.split('",\n')[0].strip()
          self.still_thinking = False
          stream_json['interaction']['content'] = self.final_thought
          return stream_json, True
        else:
          stream_json['interaction']['content'] = self.thought_stream
      else:
        stream_json['interaction']['content'] = self.final_thought
    # Other chunk types are: message_start, message_delta, message_stop, along with content_block_start
    return stream_json, self.still_thinking

  def strip_the_message(self, message_chunk):
    stripped = message_chunk.strip()

    for prefix in ['thought": "', 'thought', '": "']:
      if stripped.startswith(prefix):
        stripped = stripped[len(prefix):]
        break
    return stripped

  def fish_for_columns_from_stream(self, stream_json):
    captures = [' <', '> ', '>.', '>,', '(<', '>)']
    symbols =  [' ',   ' ',  '.',  ',', '(',   ')']
    for capture, symbol in zip(captures, symbols):
      stream_json = stream_json.replace(capture, symbol)
    return stream_json

  def full_gpt_thoughts(self, chunk, stream_json):
    """ Allows for a straight pass-through of the entire thought stream """
    message_chunk = chunk.choices[0].delta.content
    if chunk.choices[0].finish_reason == 'stop':
      self.final_thought = self.thought_stream
      self.still_thinking = False
    elif message_chunk is None:   # there is no content, only a "role": "assistant"
      stream_json['interaction']['content'] = ''
    else:
      if len(self.thought_stream) < 8:
        if message_chunk in ['Thought', ' Thought', ':']:
          message_chunk = ''  # skip the first few words which is part of the prompt
      self.thought_stream += message_chunk
      self.full_stream += message_chunk   # captured separately, to preserve the <column_name> format
      self.thought_stream = self.fish_for_columns_from_stream(self.thought_stream)
      stream_json['interaction']['content'] = self.thought_stream
    return stream_json, self.still_thinking

  def full_claude_thoughts(self, chunk, stream_json):
    if chunk.type == 'content_block_start':
      self.full_stream = ''
    elif chunk.type == 'content_block_stop':
      self.final_thought = self.thought_stream
      self.still_thinking = False
    elif chunk.type == 'content_block_delta':
      message_chunk = chunk.delta.text
      self.full_stream += message_chunk
      self.thought_stream += message_chunk
      self.thought_stream = self.fish_for_columns_from_stream(self.thought_stream)
      stream_json['interaction']['content'] = self.thought_stream

    return stream_json, self.still_thinking

  def wrap_up_thinking(self):
    stream_json = {'interaction': {'content': '', 'format': 'html', 'show': True, 'flowType': 'Default(thought)'}}
    if len(getattr(self, 'final_thought', '')) == 0:
      self.final_thought = 'Thinking hard ...'
    stream_json['interaction']['content'] = self.final_thought

    if self.nlu.labels['dax'] in ['002', '02D']:
      parsed = {'full_stream': self.full_stream}
    else:
      parsed = PromptEngineer.apply_guardrails(self.full_stream, 'json')
    prior_state = self.world.current_state()

    if parsed == 'error':
      self.nlu.active_flow.is_uncertain = True
    else:
      self.nlu.labels['flow_thought'] = self.final_thought
      self.nlu.labels['prediction'] = parsed
      self.nlu.labels['has_issues'] = prior_state.has_issues
      self.nlu.labels['primary_keys'] = self.memory.primary_keys
      self.nlu.active_flow.fill_slots_by_label(prior_state.current_tab, self.nlu.labels)
    return stream_json

  @handle_breaking_errors
  def generate_response(self, frame, actions):
    response = self.res.generate(actions, self.context, frame, self.world)
    response = self.follow_up_after_issue(response, self.res.follow_up_details)
    if 'raw_utterance' in response:
      self.context.add_turn('Agent', response['raw_utterance'], 'utterance')
    elif 'message' in response:
      self.context.add_turn('Agent', response['message'], 'utterance')
    return response, True

  def follow_up_after_issue(self, response, prior_labels):
    if len(prior_labels) > 0:
      prior_query = prior_labels['query'] # we know query is available because that is how we got here
      prior_state = self.world.current_state()
      frame, success = self.pex.follow_up_execution(prior_query, prior_state)
      if success:
        self.world.insert_frame(frame)
        markdown_df = frame.get_data('md', limit=64)
        prior_history = prior_labels['history']
        if len(prior_labels['thought']) == 0:
          thought = "I should use the data to answer the user's question"
        else:
          thought = prior_labels['thought']
        suffix = self.res.query_response(markdown_df, prior_history, thought)
        first_char = suffix[0].lower()
        response['message'] += f"\nAfter updating the data, {first_char}{suffix[1:]}"

    self.res.follow_up_details = {}  # either way clear the follow up
    return response

  def _rewrite_utterance(self, user_text, state):
    return user_text  # skip rewriting, instead trust that model can interpret longer convo history length

  def handle_user_actions(self, action_data, gold_dax):
    if action_data:
      if action_data['type'] == 'REVISE':
        success = self.context.revise_user_utterance(action_data['payload'])
      elif action_data['type'] == 'HOVER':
        success = self.stash_hover_data(action_data['payload'])
      elif action_data['type'] == 'REPLY':
        success = self.process_reply_data(action_data['payload'], self.world.current_state())
      self.context.add_turn('User', action_data['type'], 'action')

  def process_reply_data(self, payload, state):
    flow = state.get_flow()   # we know a flow exists since it's required to generate a suggested reply

    if flow.name() == 'format':
      flow.slots['format'].add_one(payload)
    elif flow.name() == 'validate':
      if payload == 'accept':
        flow.slots['terms'].verified = True
      elif payload == 'reject':
        flow.slots['terms'].verified = False
        state.errors.append('incorrect_mapping')

    return True

  def parse_analyze_rewrite(self, raw_output, metric):
    # Update the utterance with the re-written text, parse any verified portions and fill the slot
    # Verification: revenue [verified as SalesPrice, UnitsSold] / orders [verified as OrderId]
    raw_output = raw_output.replace('Rewritten:', '').strip()
    try:
      rewritten_text, formula = raw_output.split('\nFormula:')
      eq_index = formula.find('=')
      equation = formula[eq_index + 1:].strip()
      parts = [part.strip() for part in equation.split(metric.expression.relation)]

      for part, variable in zip(parts, metric.variables):
        # Extract the variable name from the part
        variable_name_match = re.search(r'(\w+)\s+\[verified as', part)
        if variable_name_match and variable_name_match.group(1) == variable.name:
          words = re.findall(r'\b\w+\b', part)
          column_names = [word for word in words if word in self.world.col_to_tab.keys()]
          # Directly set the table and columns for the variable if column_names are found
          if column_names:
            for col_name in column_names:
              variable.add_clause(self.world.col_to_tab[col_name], col_name, '+', False)
    except IndexError:
      rewritten_text = raw_output  # Only set rewritten_text in case of IndexError

    return rewritten_text.strip()

  def activate_loader(self, extension, multi_tab=False):
    if self.loader is None:
      if extension in ['csv', 'tsv', 'xlsx', 'ods']:
        self.loader = SpreadsheetLoader(extension, multi_tab)
      elif extension in ['ga4', 'hubspot', 'amplitude', 'segment', 'google', 'drive', 'facebook', 'salesforce']:
        self.loader = VendorLoader(extension)
      elif extension in ['databricks', 'redshift', 'bigquery', 'snowflake']:
        self.loader = WarehouseLoader(extension)

  def initial_pass(self, raw_data, tab_name, index, total):
    """ Takes an initial pass at processing the data
    Inputs:
    1) raw_data (CSV): raw table data
    2) tab_name (string): the name of the table being processed
    3) index (int): the index of the table
    4) total (int): total number of tables to process, used to determine if cycle is done
    Returns:
    1) success: whether the raw_data is valid based on file size
    2) is_done: whether this is the last table in the spreadsheet
    3) result: a list of table names if successful, or an error message otherwise"""
    file_size = len(raw_data)
    file_size_mb = file_size / (1024 * 1024)  # Bytes to MB
    print(f"Attempting to upload a file of size: {file_size_mb} MB")

    if file_size_mb > 100:
      return False, False, "File is too large, must be less than 100MB"
    try:
      if self.loader.source in ['csv', 'tsv']:
        decoded_content = raw_data.decode('utf-8')
        self.loader.holding[tab_name] = StringIO(decoded_content)
        is_done = index == total - 1
      elif self.loader.source in ['xlsx', 'ods']:
        self.loader.holding[tab_name] = BytesIO(raw_data)
        is_done = index == total - 1
      else:
        self.loader.holding[tab_name] = raw_data
        is_done = True
    except (Exception) as exp:
      print(exp)
      return False, True, "File is not a valid CSV table or has invalid characters"

    result = self.loader.get_processed()
    return True, is_done, result

  def multi_tab_pass(self, raw_data, sheet_info):
    """ Inputs:
    1) raw_data (XLSX): raw spreadsheet data containing multiple tables
    2) sheet_info (dict): metadata with keys of [ssName, tableNames, description, globalExtension]
    Returns:
    1) success (boolean): whether all the tables in the spreadsheet are valid and successfully held
    2) table_names (list): a list of table names if successful, or an empty list otherwise
    3) error_msg (string): an error message when the file is too large or invalid """
    file_size = len(raw_data)
    file_size_mb = file_size / (1024 * 1024)  # Bytes to MB
    print(f"Attempting to upload a file of size: {file_size_mb} MB")
    if file_size_mb > 100:
      return False, [], "File is too large, must be less than 100MB"

    try:
      excel_file = io.BytesIO(raw_data)
      xls = pd.ExcelFile(excel_file)
      for sheet_name, tab_name in zip(xls.sheet_names, sheet_info['tableNames']):
        self.loader.holding[tab_name] = pd.read_excel(xls, sheet_name)
    except (Exception) as exp:
      return False, [], f"Parsing multi-tab file failed: {exp}"

    table_names = self.loader.get_processed()
    return True, table_names, ""

  def fetch_tab_data(self, tab_name, row_start, row_end):
    """ Fetches data from the memory database
    Inputs: tab_name (string): the name of the table being processed
      row_start (int): the index of the first row to fetch
      row_end (int): the index of the last row to fetch
    Returns: success (bool): whether the data was successfully fetched
      table_data (list): the data from the table if successful, empty list otherwise"""
    success = False
    if tab_name in self.world.valid_tables:
      curr_schema = self.world.metadata['schema']
      try:
        special_tabs = self.pex.database.special_char_tables
        frame = self.memory.fetch_one(tab_name, curr_schema, special_tabs, row_start, row_end)
        table_data = frame.get_data('list')
        success = True
      except(Exception):
        table_data = []
    else:
      table_data = []

    if success and row_start == 0:
      state = self.world.current_state()
      state.current_tab = tab_name
      if self.context.num_utterances <= 1:
        # Add a frame at start of conversation, otherwise they will be added automatically by agent loop
        self.world.insert_frame(frame)

    return success, table_data

  def download_data(self, tab_name, export_type):
    """ Prepares the spreadsheet data for download, possible types are CSV, XLSX, and JSON """
    full_schema = self.world.metadata['schema']

    if export_type == 'csv':
      table = self.memory.download_one(tab_name, full_schema)
      with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as file_content:
        table.to_csv(file_content.name, index=False)

    elif export_type == 'xlsx':
      with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as file_content:
        with pd.ExcelWriter(file_content.name, engine='openpyxl') as writer:
          for excel_table_name, table in self.memory.download_all(full_schema):
            table.to_excel(writer, sheet_name=excel_table_name, index=False)

    elif export_type == 'json':
      table = self.memory.download_one(tab_name, full_schema)
      with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as file_content:
        table.to_json(file_content.name, orient='records')

    return file_content

  def register_data_with_agent(self, properties):
    self.context = Context(self.verbose)
    self.context.initialize_history(self.memory)
    self.world.set_defaults(self.memory)
    self.world.initialize_metadata(self.memory, self.external, properties)
    special_tabs = self.pex.add_database(self.memory, self.world.metadata['schema'])
    preview_frame = self.memory.fetch_one(self.world.default_table, self.world.metadata['schema'], special_tabs)
    self.world.insert_frame(preview_frame)
    return preview_frame
  

  def upload_data(self, spreadsheet, details={}):
    """ Decides to load default data or a new spreadsheet, depending on whether details is empty
    Details is a dict that should contain keys for ssName, description and globalExtension """
    if len(details) > 0:
      existing_sheets = self.context.available_data
      succeeded, output = self.loader.process_details(spreadsheet, existing_sheets, details, self.external)
      if succeeded:
        for table_name, table_data in output.get('ss_data', {}).items():
          if hasattr(table_data, 'to_dict'):
            # Convert DataFrame to columnar format for database
            formatted_data = {
              'columns': list(table_data.columns),
              'data': []
            }
            for col in table_data.columns:
              col_data = table_data[col].ffill().values
              # Replace NaN with None before serialization
              col_data = [None if pd.isna(v) else v for v in col_data]
              col_data = [serialize_for_json(v) for v in col_data]
              formatted_data['data'].append(col_data)
          else:
            formatted_data = table_data

          uploaded_file_id = uuid4()
          self.data_source_ids.append(uploaded_file_id)

        properties = self.memory.register_new_data(**output) 
        self.loader = None  # reset to save memory
        preview_frame = self.register_data_with_agent(properties)
        return True, preview_frame.get_data('list')
      else:
        self.loader = None
        return False, output

    else:
      dir_name, table_names = spreadsheet.ssName.strip(), spreadsheet.tabNames
      properties = self.memory.register_default_data(dir_name, table_names)
    
      preview_frame = self.register_data_with_agent(properties)
      table_data = preview_frame.get_data('list')
      return True, table_data

  def delete_data(self, tab_name):
    try:
      # Delete the table from the memory, which includes the shadow database data
      result = self.memory.delete_table(tab_name)

      if result["success"]:
        world_success, new_default = self.world.delete_table(tab_name)
        if not world_success:
          return False, "Failed to update world state after deleting the table"
        
        # Update the database in policy execution
        special_tabs = self.pex.add_database(self.memory, self.world.metadata['schema'])
        sys_prompt = self.context.write_system_prompt(self.memory)
        self.external.set_system_prompt(sys_prompt)
        
        # Update frame and default table if there are still tables available
        if len(self.world.valid_tables) > 0:
          if new_default and not any(f.raw_table == new_default for f in self.world.frames):
            preview_frame = self.memory.fetch_one(new_default, self.world.metadata['schema'], special_tabs)
            self.world.insert_frame(preview_frame)
          success_message = f"Successfully deleted table '{tab_name}' and updated agent state"
        else:
          success_message = f"Successfully deleted the last table '{tab_name}'"        
        return True, success_message
      
      # Return the status from the memory operation if deletion failed
      return result["success"], result["message"]
    except Exception as ecp:
      error_message = f"Error: Failed to delete table '{tab_name}': {ecp}"
      return False, error_message

  def generate_table_metadata(self, tab_col_dict):
    """ Generate a name and description for the conversation based on the tables """
    tables_string = "; ".join(tab_col_dict.keys())
    columns_string = PromptEngineer.column_rep(tab_col_dict)
    prompt = conversation_metadata_prompt.format(tables=tables_string, columns=columns_string)
    response = self.external.execute(prompt, version='claude-haiku')
    response = PromptEngineer.apply_guardrails(response, 'json')
    return {'name': response.get('name', ''), 'description': response.get('description', '') }

  def save_session_state(self):
    """Save the current state of all tables back to PostgreSQL"""
    if not self.data_source_ids:
      return True, "No data sources to save"

    try:
      for data_source_id in self.data_source_ids:
        # Get the data source to find its table name
        data_source = self.storage.get_sources_by_ids([data_source_id])[0]
        if not data_source: continue

        # Get the current state of the table from memory
        if data_source.name in self.memory.tables:
          table_data = self.memory.tables[data_source.name]
          self.storage.save_table_state(data_source_id, data_source.name, table_data)
      return True, "Successfully saved all tables"
    except Exception as e:
      return False, f"Error saving tables: {str(e)}"

  def close(self):
    """Close the session and save any pending changes"""
    success, message = self.save_session_state()
    if not success and self.verbose:
      print(f"Warning: {message}")
    
    if hasattr(self, 'memory'):
      self.memory.close()
    if hasattr(self, 'storage'):
      self.storage.close()
