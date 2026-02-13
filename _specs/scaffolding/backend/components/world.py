import re
import json
import time as tm
from collections import defaultdict

from backend.components.state import DialogueState
from backend.components.metadata.issues import metadata_map
from backend.components.metadata.schema import Schema
from backend.components.metadata.typechecks import TypeCheck

class World(object):

  def __init__(self, args):
    # accessing the most recent dialogue state is short and simple 'self.world.states[-1]'
    self.states = []        # list of all dialogue states
    self.frames = []        # list of derived data outputs

    self.campaigns = {}     # campaigns that are active or inactive
    self.channels = {}      # marketing channels to cycle through
    self.metadata = {}

    self.caution_level = args.level   # low, medium, or high

  def set_defaults(self, memory_db):
    valid_table_names = list(memory_db.tables.keys())
    self.valid_tables = valid_table_names
    self.valid_columns = {table: memory_db.tables[table].columns.tolist() for table in valid_table_names}
    self.default_table = valid_table_names[0]
    self.col_to_tab = {col: table for table, columns in self.valid_columns.items() for col in columns}

  def is_valid_entity(self, tab, col):
    # takes in two strings, table name and column name, and checks if they are valid
    return tab in self.valid_tables and col in self.valid_columns[tab]

  def are_valid_entities(self, entities):
    # takes in a list of entities and checks if they are all valid
    return all(self.is_valid_entity(entity['tab'], entity['col']) for entity in entities)

  def initialize_metadata(self, memory_db, api, properties):
    start = tm.time()
    for md_name, metadata_class in metadata_map.items():
      self.metadata[md_name] = {}
      for tab_name in self.valid_tables:
        tab_props = properties[tab_name]
        if md_name == 'schema':
          print(f"Primary key for {tab_name} is {memory_db.primary_keys[tab_name]}")
          table = memory_db.tables[tab_name]
          self.metadata[md_name][tab_name] = metadata_class(table, tab_name, tab_props, self.caution_level, api=api)
        else:
          self.metadata[md_name][tab_name] = metadata_class(tab_name, tab_props, self.caution_level, api=api)
    end = tm.time()
    print("Total time taken to build metadata: ", round(end-start, 2), " seconds")

  def declare_metadata(self, table, tab_name, memory_db, flow):
    # rather than creating a new schema based on checking types, we declare the new type and format directly
    col_name = flow.slots['source'].values[0]['col']
    subtype_name = flow.slots['subtype'].value

    col_properties = self.metadata['schema'][tab_name].tab_properties[col_name]
    col_properties['supplement'][subtype_name] = flow.slots['format'].value
    self.metadata['schema'][tab_name].tab_properties[col_name] = col_properties

  def update_metadata(self, table, tab_name, shadow, flow):
    # create a new schema for the revised table
    current_scheme = self.metadata['schema'][tab_name]
    current_props = current_scheme.tab_properties  # dict with column_name as key
    revised_props = {}

    # extract additional columns to consider for TypeChecking
    source_slot = flow.slots.get('source', None)
    source_columns = []
    if source_slot and len(source_slot.values) > 0:
      source_columns = [entity['col'] for entity in source_slot.values if entity['tab'] == tab_name]

    for col in table.columns:
      if col in current_props and col not in source_columns:
        revised_props[col] = current_props[col]
      else:
        if flow.flow_type == 'datatype' and flow.properties:
          new_col_properties = flow.properties
        else:
          new_col_properties = TypeCheck.build_properties(col, table[col])
        column, col_props = shadow.convert_to_type(tab_name, table[col], new_col_properties)
        table[col] = column
        revised_props[col] = col_props
    self.metadata['schema'][tab_name] = Schema(table, tab_name, revised_props, current_scheme.level)

  def construct_metadata(self, table, predicted_props, tab_name, old_names=[]):
    # create a new schema for the newly merged table
    current_props = {}
    for old_tab_name in old_names:
      current_scheme = self.metadata['schema'][old_tab_name]
      old_props = current_scheme.tab_properties
      for col in old_props:
        current_props[col] = old_props[col]

    finalized_props = {}
    for col in table.columns:
      if col in predicted_props:
        finalized_props[col] = predicted_props[col]
      elif col in current_props:
        finalized_props[col] = current_props[col]
      else:
        finalized_props[col] = TypeCheck.build_properties(col, table[col])

    self.metadata['schema'][tab_name] = Schema(table, tab_name, finalized_props, 'medium')
    return finalized_props

  def construct_issue_md(self, tab_name, tab_properties, api):
    for md_name, metadata_class in metadata_map.items():
      level = self.caution_level

      if md_name == 'schema':
        continue
      else:
        mdata = metadata_class(tab_name, tab_properties, level, api)
      self.metadata[md_name][tab_name] = mdata

  def has_data(self, tab_type=''):
    if len(self.frames) > 0:
      if tab_type:
        return any(frame.tab_type == tab_type for frame in self.frames)
      else:
        return True
    return False

  def previous_queries(self):
    prev_queries = []
    skipped_frames = 0  # if we skip 2 frames in a row, we're probably dealing with a different scenario

    for frame in reversed(self.frames):
      if frame.source == 'sql' and len(frame.code) > 0:
        prev_queries.append(frame.code)
        skipped_frames = 0
      else:
        skipped_frames += 1

      if frame.code.startswith(f"-- Step 1"):
        print("stopped due to step 1")
      if len(prev_queries) == 3 or frame.code.startswith(f"-- Step 1") or skipped_frames > 1:
        break

    if len(prev_queries) == 0:
      prev_queries.append("N/A")
    return prev_queries

  def current_state(self, form='object'):
    # initialize the dialogue state if it doesn't exist, then return it
    if len(self.states) == 0:
      default_tab = self.default_table
      entities = [{'tab': default_tab, 'col': col_name, 'ver': False} for col_name in self.valid_columns[default_tab]]
      initial_state = DialogueState(entities=entities, dax='FFF')
      initial_state.current_tab = default_tab
      initial_state.turn_id = 0
      self.states.append(initial_state)
    last_state = self.states[-1]
    return last_state if form == 'object' else str(last_state)

  def current_schema(self):
    tab_schema = {}
    for entity in self.current_state().entities:
      table = entity['tab']
      tab_schema[table] = self.metadata['schema'][table]
    return tab_schema

  def insert_state(self, state):
    # IMPORTANT: we need some way to take a snapshot of the state, such that if the state
    # is changed in the future, we can still access the original state at this point in time
    if state is not None:
      self.states.append(state)
    return state

  def insert_frame(self, frame):
    if self.has_data():
      if frame != self.frames[-1]:
        self.frames.append(frame)
    else:
      self.frames.append(frame)
    return frame

  def delete_table(self, tab_name):
    try:
      # Remove table from metadata
      for md_name in self.metadata:
        if tab_name in self.metadata[md_name]:
          del self.metadata[md_name][tab_name]
      
      # Update world's tracking of valid tables and columns
      if tab_name in self.valid_tables:
        self.valid_tables.remove(tab_name)
        del self.valid_columns[tab_name]
        
        # Update the col_to_tab mapping
        cols_to_remove = [col for col, tab in self.col_to_tab.items() if tab == tab_name]
        for col in cols_to_remove:
          del self.col_to_tab[col]
      
      # Update default table if needed
      new_default = None
      if self.default_table == tab_name and len(self.valid_tables) > 0:
        self.default_table = self.valid_tables[0]
        new_default = self.default_table
      
      # Remove any frames referencing the deleted table
      self.frames = [f for f in self.frames if f.raw_table != tab_name]
      
      return True, new_default
    except Exception as err:
      err_message = "Error in World.delete_table: {err}"
      return False, err_message
    
  def get_simplified_schema(self, tab_name):
    schema = self.metadata['schema'][tab_name]
    simplified_schema = {}
    for col_name, col_props in schema.tab_properties.items():
      simplified_schema[col_name] = col_props['subtype']
    return simplified_schema