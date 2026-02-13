import os
from backend.utilities.manipulations import serialize_for_json
os.environ['NLTK_DATA'] = os.path.join(os.path.dirname(__file__), 'utils', 'nltk_data')

import re
import pandas as pd
import numpy as np
import chardet
from collections import defaultdict, Counter
from datetime import datetime as dt
from textblob import Word

import random
import duckdb
import functools

from backend.db import get_db
from backend.assets.ontology import error_responses, date_mappings, date_formats, time_formats, default_limit
from backend.assets.ontology import missing_tokens, default_tokens, NA_string
from backend.assets.descriptions import preloaded_descriptions
from backend.components.frame import Frame
from backend.components.engineer import PromptEngineer
from backend.components.metadata.typechecks import TypeCheck
from database.tables import UserDataSource

def handle_breaking_errors(func):
  def wrapper(self, utterance, actions):
    # returns the full stacktrace
    if self.debug:
      return func(self, utterance, actions)

    try:
      return func(self, utterance, actions)
    except Exception as err:
      print(f"ERROR: {err}")
      error_message = random.choice(error_responses)
      response = {'message': error_message, 'actions': [], 'interaction': None, 'frame': None,
                'uncertainity': {'general': True, 'partial': False, 'specific': False, 'confirmation': False}}
      return response, "error"
  return wrapper

class StorageDB(object):
  """ Usage:
  storage = StorageDB(args)
  result = storage.execute("SELECT * FROM orders WHERE price > 80;")
  for row in result:
    print(row)
  storage.insert_item('INSERT INTO users (name) VALUES (:name)', {'name': 'John'})

  user = User(username='john')
  storage.session.add(user)
  storage.session.commit()

  messages = session.query(Message).filter(Message.user == user).all()
  """
  def __init__(self, args):
    self.verbose = args.verbose
    self._session = None

  def execute(self, query):
    """Execute a query with a fresh session"""
    session = get_db()
    try:
      result = session.execute(query)
      return result
    except Exception as e:
      session.rollback()
      raise
    finally:
      session.close()

  def insert_item(self, data):
    """Insert an item with a fresh session"""
    session = get_db()
    try:
      session.add(data)
      session.commit()
    except Exception as e:
      session.rollback()
      raise
    finally:
      session.close()
      
  def close(self):
    """Close the current session if it exists"""
    if self._session is not None:
      self._session.close()
      self._session = None

  def get_user_sources(self, user_id):
    session = get_db()
    try:
      return session.query(UserDataSource).filter_by(user_id=user_id).all()
    finally:
      session.close()

  def get_sources_by_ids(self, ids):
    session = get_db()
    try:
      return session.query(UserDataSource).filter(UserDataSource.id.in_(ids)).all()
    finally:
      session.close()

  def save_table_state(self, data_source_id, table_name, table_data):
    """Save the current state of a table back to PostgreSQL"""
    session = None
    try:
      # Get the data source
      session = get_db()
      data_source = session.query(UserDataSource).filter_by(id=data_source_id).first()
      if not data_source:
        return False, "Data source not found"

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

      # Update the content
      data_source.content = formatted_data

      # Commit changes
      session.commit()
      return True, "Successfully saved table state"

    except Exception as e:
      if session:
        session.rollback()
      return False, f"Error saving table state: {str(e)}"
    finally:
      if session:
        session.close()

class MemoryDB(object):
  """ Usage:
  memory = MemoryDB(args.verbose, "shoe store")
  memory.execute("SELECT price > 90 FROM orders;")
  all_data = memory.fetch_all()
  """
  def __init__(self, args, api):
    self.verbose = args.verbose       
    self.debug = args.debug       
    self.api = api

    self.db_connection = duckdb.connect(':memory:')
    self.shadow = ShadowDB()
    self.init_tables()

  def init_tables(self):
    self.tables = {}
    self.description = {}
    self.primary_keys = {}
    self.engineers = {}

  def register_default_data(self, dir_name, table_names):
    self.init_tables()
    table_data = {}
    for tab_name in table_names:
      table_path = os.path.join("database", "storage", dir_name, f"{tab_name}.csv")
      rawdata = open(table_path, 'rb').read()
      encoding_type = chardet.detect(rawdata)['encoding']
      table_data[tab_name] = pd.read_csv(table_path, encoding=encoding_type) # we know the file is CSV because it's our own preset data
    return self.register_tables(dir_name, table_data)

  def register_new_data(self, ss_name, ss_goal, ss_data):
    self.init_tables()
    if " to " in ss_goal:
      parts = ss_goal.split(" to ")
      ss_goal = " to ".join(parts[1:])
    ss_goal = ss_goal[:-1] if ss_goal.endswith(".") else ss_goal
    self.description['goal'] = ss_goal.strip()
    return self.register_tables(ss_name, ss_data)

  def register_tables(self, spreadsheet_name, spreadsheet_data):
    # All missing value in MemoryDB is NaN
    properties = {}
    for tab_name, table in spreadsheet_data.items():
      print("Registering table:", tab_name)
      table = self.clean_table(tab_name, table)  # All blank cell are NaNs
      self.shadow.initialize_issues(tab_name)

      tab_properties = {}
      for col_name, column in table.items():
        col_props = TypeCheck.build_properties(col_name, column)
        column, col_props = self.shadow.convert_to_type(tab_name, column, col_props)  # all NaN are remained
        tab_properties[col_name] = col_props
        table[col_name] = column

      self.engineers[tab_name] = PromptEngineer(tab_properties, tab_name, self.api)
      self.tables[tab_name] = table
      properties[tab_name] = self.set_primary_keys(tab_name, tab_properties, table)
      self.complete_registration(tab_name, spreadsheet_name)
    return properties

  def handle_duplicate_columns(self, table):
    """Renames duplicate columns by appending _2, _3, etc."""
    counts = defaultdict(int)
    new_columns = []

    for column in table.columns:
      counts[column] += 1
      if counts[column] > 1:
        new_name = f"{column}_{counts[column]}"
        new_columns.append(new_name)
      else:
        new_columns.append(column)

    table.columns = new_columns
    return table

  def clean_table(self, tab_name, table):
    # Handle duplicate column names first
    table = self.handle_duplicate_columns(table)

    # remove blank columns
    blank_col_index = [col for col in table.columns if table[col].isna().all()]
    if len(blank_col_index) > 0:
      table.drop(columns=blank_col_index, inplace=True)

    # There must be a column name for each column
    rename_map = {}
    unnamed_cols = []
    for col_name in table.columns:
      if not isinstance(col_name, str):
        rename_map[col_name] = str(col_name)
      elif col_name.strip() != col_name:
        rename_map[col_name] = col_name.strip()
      elif 'Unnamed:' in col_name:
        unnamed_cols.append(col_name)
      elif col_name == '':
        unnamed_cols.append(col_name)

    if len(rename_map) > 0:
      table.rename(columns=rename_map, inplace=True)
    if len(unnamed_cols) > 0:
      table.drop(columns=unnamed_cols, inplace=True)

    # remove all the rows that are blank
    if table.isna().all(axis=1).any():
      table.dropna(how='all', inplace=True)
    return table

  def update_table(self, tab_name, tab_schema, changes):
    # Given a table_update item with row_id and col_name, update to the new value
    null_mapper = {'int64': pd.NA, 'float64': np.nan, 'datetime64[ns]': pd.NaT, '<M8[ns]': pd.NaT, 'object': ''}
    num_changes = 0
    needs_registration = False

    for change in changes:
      try:
        value = int(change.newValue) if change.newValue.isdigit() else change.newValue
        datatype = str(self.tables[tab_name][change.col].dtype)

        if value == '':
          self.tables[tab_name].loc[change.row, change.col] = null_mapper.get(datatype, value)

        else:
          col_schema = tab_schema.get_type_info(change.col)
          col_format = col_schema['supplement'].get(col_schema['subtype'], None)
          safe_transaction = True

          if col_format:
            if datatype in ['datetime64[ns]', '<M8[ns]']:
              parsed = pd.to_datetime(value, errors='coerce')
              if pd.isna(parsed):
                safe_transaction = False
              elif value != parsed.strftime(col_format):
                safe_transaction = False
            elif datatype in ['float64', 'int64']:
              parsed = pd.to_numeric(value, errors='coerce')
              if pd.isna(parsed):
                safe_transaction = False

          if safe_transaction:
            self.tables[tab_name].loc[change.row, change.col] = value
          else:  # rather than updating the value (which changes the dtype of the column)
            # set the row in the main table as null, and
            self.tables[tab_name].loc[change.row, change.col] = null_mapper[datatype]
            # store the new value as a problem in the shadow table
            one_prob = {'row_id': change.row,'column_name': change.col,'original_value': value,
                        'issue_type': 'problem', 'issue_subtype': 'unsupported', 'revised_term': None}
            new_issue = pd.DataFrame([one_prob])
            self.shadow.issues[tab_name] = pd.concat([self.shadow.issues[tab_name], new_issue], ignore_index=True)

        if datatype != 'object':  # object columns already update themselves automatically
          needs_registration = True
        num_changes += 1
      except Exception as exp:
        error_msg = f"Encountered {exp}; Completed {num_changes}/{len(changes)} changes"
        return False, error_msg

    if needs_registration:
      self.db_connection.register(tab_name, self.tables[tab_name])
    success_msg = f"Successfully completed {num_changes} changes"
    if self.verbose:
      print("  " + success_msg)
    return True, success_msg

  def set_primary_keys(self, tab_name, tab_properties, table):
    candidates = [col for col in table.columns if tab_properties[col]['subtype'] in ['id', 'whole']]
    candidates.extend(table.columns[:3])   # primary keys are often in the first three columns
    top_candidate = self.check_for_pkey(set(candidates), tab_name, tab_properties)

    if top_candidate:
      pkey = top_candidate
      # table.set_index(pkey, inplace=False)   purposely skipped to prevent the column from being removed
    else:
      pkey = self.make_primary_key(tab_name)
      table.reset_index(inplace=True)
      table.rename(columns={'index': pkey}, inplace=True)
      table.set_index(pkey, inplace=True)
    self.primary_keys[tab_name] = pkey

    if pkey in tab_properties:
      if tab_properties[pkey]['subtype'] in ['whole', 'general', 'category']:
        tab_properties[pkey]['type'] = 'id'
        tab_properties[pkey]['subtype'] = 'unique'
    else:
      tab_properties[pkey] = {'col_name': pkey, 'total': len(table), 'type': 'unique', 'subtype': 'id'}
    return tab_properties

  def check_for_pkey(self, candidates, tab_name, tab_properties, minimum_score=0.8):
    """ returns most likely primary key from a list of candidates if any pass the minimum score """
    top_candidate = None
    for cand_col in candidates:
      properties = tab_properties[cand_col]
      column = self.tables[tab_name][cand_col]
      total_score = 0

      # amount of overlap with the table name
      _, overlap_score = PromptEngineer.token_overlap(cand_col, tab_name)
      total_score += overlap_score * 0.3

      # special keywords of 'key' or 'id'
      if cand_col.lower().endswith('key') or cand_col.lower().endswith('id'):
        total_score += 0.05

      # percentage of unique values
      unique_score = column.nunique() / len(column)
      total_score += unique_score * 0.35

      # percentage of non-empty values
      empty_count = 0
      for empty_subtype in ['null', 'missing', 'default']:
        empty_count += properties['supplement'][empty_subtype]
      empty_score = 1 - (empty_count / len(column))
      total_score += empty_score * 0.2

      # whether all values are roughly the same size
      sizes = column.astype(str).apply(len)
      size_range = sizes.max() - sizes.min()
      size_diff = 3 - size_range
      roughly_same_size = size_diff > 0
      if roughly_same_size:
        total_score += 0.1 * size_diff

      # give a boost if the column is an id subtype
      if properties['subtype'] == 'id':
        total_score *= 1.15

      # giant boost if the values are sequential integers
      series = column.dropna().head(32)
      if (series.dtype in ['int64', 'Int64'] and series.diff().dropna().eq(1).all()):
        total_score *= 1.2

      if total_score > minimum_score:
        top_candidate = cand_col
        minimum_score = total_score

    return top_candidate

  @staticmethod
  def make_primary_key(table_name):
    if '_' in table_name:
      # split snake case into words
      parts = table_name.split('_')
    else:
      # split camel case into words
      parts = re.findall(r'[A-Z](?:[a-z]+|[A-Z]*(?=[A-Z]|$))', table_name)
    parts = [part.lower() for part in parts if len(part) > 0]

    if len(parts) >= 3:
      primary_key = "".join([part[0] for part in parts[:3]]) + "_id"
    elif len(table_name) > 8:
      stemmed = Word(table_name).stem()
      primary_key = (stemmed if stemmed else table_name[:3]) + "_id"
    else:
      primary_key = table_name + "_id"
    return primary_key

  def complete_registration(self, tab_name, db_name=''):
    if db_name in preloaded_descriptions and tab_name in preloaded_descriptions[db_name]:
      self.description['goal'] = preloaded_descriptions[db_name]['goal']
      self.description[tab_name] = preloaded_descriptions[db_name][tab_name]
    else:
      current_table, current_pkey = self.tables[tab_name], self.primary_keys[tab_name]
      engineer = self.engineers[tab_name]
      updated_description = engineer.compile_description(current_table, current_pkey)
      self.description[tab_name] = updated_description

    # register the table within DuckDB
    if len(db_name) > 0:
      self.db_name = db_name
    self.db_connection.register(tab_name, self.tables[tab_name])

  def register_new_table(self, context, tab_name, old_tab_names, table_content):
    # Create a new primary key for the new table
    pkey = self.make_primary_key(tab_name)
    table_content.reset_index(inplace=True)
    table_content.rename(columns={'index': pkey}, inplace=True)
    table_content.set_index(pkey, inplace=True)
    self.primary_keys[tab_name] = pkey

    # Set a description and register it within DuckDB
    if context.actions_include(['CREATION'], 'User'):
      tab_desc = f"Materialize a permanent view called {tab_name} from a temporary table."
    elif context.actions_include(['PIVOT'], 'Agent'):
      tab_desc = f"Pivot table named {tab_name} created when grouping by {table_content.columns[1]}"
    else:
      old_tab_string = ' and '.join(old_tab_names)
      tab_desc = f"Dynamically created table for {tab_name} that is the result of merging the {old_tab_string} tables."
    self.description[tab_name] = tab_desc
    self.db_connection.register(tab_name, table_content)

  def execute(self, query_str):
    # result = self.db_connection.execute(query_str).fetchdf()
    result = self.db_connection.query(query_str).df()
    return result

  def download_all(self, schema):
    # A generator that returns tuples of table name and table info for downloading
    for tab_name, table in self.tables.items():
      table_schema = schema[tab_name]
      output_df = table.where(pd.notnull(table), None)
      for col_name in output_df.columns:
        props = table_schema.get_type_info(col_name)
        output_column = self.shadow.display_as_type(output_df, **props)
        output_df[col_name] = output_column.replace(NA_string, '')
      yield (tab_name, output_df)

  def download_one(self, tab_name, schema):
    # Returns a single displayed table for downloading
    table_schema = schema[tab_name]
    table = self.tables[tab_name]
    output_df = table.where(pd.notnull(table), None)

    for col_name in output_df.columns:
      props = table_schema.get_type_info(col_name)
      output_column = self.shadow.display_as_type(output_df, **props)
      output_df[col_name] = output_column.replace(NA_string, '')
    return output_df

  def fetch_one(self, tab_name, schema, special_tabs, start=0, end=default_limit):
    # Fetches rows from a single table in the database
    # Always quote table names to handle numeric or special character table names
    table_ref = f'"{tab_name}"'
    # We go from 0-256, 256-512, 512-1024, 1024-2048, 2048-3072, 3072-4096, etc.
    limit = end - start if start > 0 else end
    offset = f"OFFSET {start} " if start > 0 else ""
    fetch_query = f"SELECT * FROM {table_ref} {offset}LIMIT {limit};"

    df = self.db_connection.query(fetch_query).df()
    db_output = df.where(pd.notnull(df), None)

    table_schema = schema[tab_name]
    for col_name in db_output.columns:
      try:
        props = table_schema.get_type_info(col_name)
        props['supplement']['offset'] = start
        db_output[col_name] = self.shadow.display_as_type(db_output, **props)
      except Exception as err: # the new created primary key is not in the schema
        print(f"Error when attempting to display column {col_name} from shadow:", err)
        continue

    frame = Frame(tab_name)
    frame.set_data(db_output, fetch_query)
    frame.primary_key = self.primary_keys.get(tab_name, None)
    return frame
    
  def delete_table(self, tab_name):
    # Validate that the object exists in our tracking dictionary
    if tab_name not in self.tables:
      error_message = f"Table '{tab_name}' does not exist in the database"
      return {"success": False, "message": error_message}
    
    try:
      # First try to drop it as a view, then as a table if that fails
      try:
        # Try to drop as a view first
        self.db_connection.execute(f"DROP VIEW IF EXISTS \"{tab_name}\"")
        object_type = "view"
      except Exception as view_err:
        if "Catalog Error: Existing object" in str(view_err):
          # If it's a catalog error about object type, try dropping as a table
          self.db_connection.execute(f"DROP TABLE IF EXISTS \"{tab_name}\"")
          object_type = "table"
        else:
          # Re-raise any other error
          raise view_err
      
      # Remove table information from all tracking dictionaries
      if tab_name in self.tables:
        del self.tables[tab_name]
      if tab_name in self.description:
        del self.description[tab_name]
      if tab_name in self.primary_keys:
        del self.primary_keys[tab_name]
      if tab_name in self.engineers:
        del self.engineers[tab_name]
      self.shadow.delete_shadow_tab(tab_name)
      
      success_message = f"Successfully deleted {object_type} '{tab_name}'"
      return {"success": True, "message": success_message}
      
    except Exception as exp:
      error_message = f"Failed to delete {tab_name}: {exp}"
      return {"success": False, "message": error_message}

  def close(self):
    """Close the database connection and clean up resources"""
    if hasattr(self, 'db_connection'):
      self.db_connection.close()
    self.tables = {}
    self.description = {}
    self.primary_keys = {}
    self.engineers = {}

def null_safety_decorator(func):
  """Decorator to catch exceptions due to NaN values in a DataFrame column and handle them."""
  @functools.wraps(func)
  def wrapper_to_catch_null(self, column, *args, **kwargs):
    try:
      return func(self, column, *args, **kwargs)
    except AttributeError as err:
      print(f"An exception occurred when converting columns: {err}")
      if isinstance(column, pd.Series):
        column = column.fillna(NA_string)
      return column
  return wrapper_to_catch_null

class ShadowDB(object):
  """ Potentially holds onto extra computed columns that are not in storage or memory 
  Currently holds helper functions for converting from ShadowTab to DisplayTab, and vice versa
  """
  def __init__(self):
    self.digit_to_time = self.reverse_date_mapping()
    # parent key is tab_name, child key is a column name, value is pandas series of the column in string format
    self.tab_props = defaultdict(dict)
    # key is tab_name, value is DataFrame with row_id, column_name, issue_type, issue_subtype, original_value
    self.issues = {}

  def initialize_issues(self, tab_name):
    issue_columns = ['row_id', 'column_name', 'issue_type', 'issue_subtype', 'original_value', 'revised_term']
    self.issues[tab_name] = pd.DataFrame(columns=issue_columns)
    # Memory optimization for repeated strings
    self.issues[tab_name]['issue_type'] = self.issues[tab_name]['issue_type'].astype('category')
    self.issues[tab_name]['issue_subtype'] = self.issues[tab_name]['issue_subtype'].astype('category')
    self.tab_props[tab_name] = {}

  def delete_shadow_tab(self, tab_name):
    # Remove all shadow data associated with the specified table.
    del self.tab_props[tab_name]
    del self.issues[tab_name]

  def add_to_issues(self, tab_name, col_name, problematic_rows, orig_column, issue_type='problem', issue_subtype='mixed_type'):
    # problematic_rows should be a pandas Series boolean mask
    if not problematic_rows.any() or tab_name not in self.issues:
      return  # No issues to add

    problems = []
    for idx in orig_column.index[problematic_rows]:
      problems.append({
        'row_id': idx,
        'column_name': col_name,
        'original_value': orig_column.loc[idx],
        'issue_type': issue_type,
        'issue_subtype': issue_subtype,
        'revised_term': None  # Default for non-typo issues
      })

    new_issues = pd.DataFrame(problems)
    self.issues[tab_name] = pd.concat([self.issues[tab_name], new_issues], ignore_index=True)

  def get_problematic_value(self, tab_name, column_name, row_id, default_value=NA_string):
    # Helper method to retrieve the original values from the issues dataframe
    if tab_name not in self.issues:
      return default_value

    issues_df = self.issues[tab_name]
    matching_issues = issues_df[
      (issues_df['column_name'] == column_name) &
      (issues_df['row_id'] == row_id)
    ]

    if not matching_issues.empty:
      return matching_issues.iloc[0]['original_value']
    return default_value

  def reverse_date_mapping(self):
    digit_to_time = defaultdict(dict)

    for subtype, mapping in date_mappings.items():
      for form, time_to_digit in mapping.items():
        time_list = ['added_for_zero_indexing']
        time_list.extend(time_to_digit.keys())
        digit_to_time[subtype][form] = time_list
    return digit_to_time

  def convert_to_boolean(self, tab_name, column, properties):
    bool_map = {
      'True': True, 'true': True, 'TRUE': True, 'T': True, 1: True,
      'False': False, 'false': False, 'FALSE': False, 'F': False, 0: False
    }
    mapped_booleans = column.map(bool_map)
    problematic_mask = mapped_booleans.isna() & column.notna() # Has value, but not a boolean
    self.add_to_issues(tab_name, properties['col_name'], problematic_mask, column)
    return mapped_booleans

  def convert_to_id(self, tab_name, column, properties):
    samples = column.sample(min(1024, len(column)), random_state=1)
    sample_numeric = pd.to_numeric(samples, errors='coerce')
    if sample_numeric.isna().any():
      return column
    sample_integers = sample_numeric.apply(lambda x: float(x).is_integer())

    if sample_integers.all():
      original_column = column.copy()
      parsed_ids = pd.to_numeric(column, errors='coerce').astype('Int64')

      self.add_to_issues(tab_name, properties['col_name'], parsed_ids.isna(), original_column)
      return parsed_ids
    else:
      return column

  def convert_to_currency(self, tab_name, column, properties):
    original_column = column.copy()
    if column.dtype == 'object':
      # [-+] captures the negative sign
      # \d{1,3} is one to three digits of values
      # (?:,\d{3}) is 0 or more groups of 3-digits with commas
      # (?:\.\d+) optionally, capture the information after a decimal point
      # %? optionally, capture the percentage sign
      column = column.astype(str).str.extract(r'([-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?%?|[-+]?\d+\.?\d*%?)')[0]
      column = column.astype(str).str.replace(',', '')

    parsed_currencies = pd.to_numeric(column, errors='coerce')
    self.add_to_issues(tab_name, properties['col_name'], parsed_currencies.isna(), original_column)
    return parsed_currencies

  def convert_to_percent(self, tab_name, column, properties):
    # Converts possible strings into floats, e.g. "100%" -> 1.0
    original_column = column.copy()
    if column.dtype == 'object':
      column = column.astype(str).str.replace('%', '')

    parsed_percentages = pd.to_numeric(column, errors='coerce')
    self.add_to_issues(tab_name, properties['col_name'], parsed_percentages.isna(), original_column)

    cleaned_rows = parsed_percentages.dropna()
    samples = cleaned_rows.sample(min(128, len(cleaned_rows)), random_state=1)
    within_range = samples.mean() > -1 and samples.mean() < 1 and samples.max() < 10
    return parsed_percentages if within_range else parsed_percentages / 100

  def convert_to_decimal(self, tab_name, column, properties):
    cleaned_column = column.astype(str).str.replace(',', '').str.replace(' ', '')
    parsed_decimals = pd.to_numeric(cleaned_column, errors='coerce')
    self.add_to_issues(tab_name, properties['col_name'], parsed_decimals.isna(), column)
    return parsed_decimals

  def convert_to_whole(self, tab_name, column, properties):
    cleaned_column = column.astype(str).str.replace(',', '').str.replace(' ', '')
    try:
      parsed_wholes = pd.to_numeric(cleaned_column, errors='coerce').astype('Int64')
    except TypeError:
      parsed_wholes = pd.to_numeric(cleaned_column, errors='coerce').round().astype(pd.Int64Dtype())

    self.add_to_issues(tab_name, properties['col_name'], parsed_wholes.isna(), column)
    return parsed_wholes

  def establish_date_format(self, column, properties):
    """ Fill in the display format for dates, if it's not already specified """
    if 'date' in properties['supplement']:
      return properties
    samples = column.sample(min(len(column), 128)).astype(str)
    format_counter = Counter()

    # Check against each option in date_formats
    for row in samples:
      for date_format in date_formats:
        try:
          if dt.strptime(row, date_format):
            format_counter[date_format] += 1
            break
        except ValueError:
          continue

    most_likely_format, format_count = format_counter.most_common(1)[0]
    if format_count < 16:
      most_likely_format = '%Y-%m-%d'  # default to ISO format if we don't have enough evidence
    properties['supplement']['date'] = most_likely_format
    return properties

  def establish_month_format(self, column, properties):
    """ Fill in the display format for months, if it's not already specified """
    if 'month' in properties['supplement']:
      return properties
    samples = column.sample(min(len(column), 128)).astype(str)
    format_counter = Counter()

    for row in samples:
      if row.isnumeric():   # numeric form
        format_counter['%I'] += 1
      elif len(row) == 3:   # abbreviated form
        format_counter['%b'] += 1
      else:                 # full form
        format_counter['%B'] += 1

    most_likely_format = format_counter.most_common(1)[0][0]
    properties['supplement']['month'] = most_likely_format
    return properties

  def establish_quarter_format(self, column, properties):
    """ Fill in the display format for quarters, if it's not already specified """
    if 'quarter' in properties['supplement']:
      return properties
    samples = column.sample(min(len(column), 128)).astype(str)
    format_counter = Counter()

    for row in samples:
      # Check for quarter information
      if row.isnumeric():
        format_counter['numeric'] += 1
      elif row.lower().endswith('quarter'):
        format_counter['full'] += 1
      elif re.search(r'\b\d+(st|nd|rd|th)\b', row):
        format_counter['ordinal'] += 1
      else:
        format_counter['abbreviated'] += 1
      # Check for year information
      if re.search(r'(\d{4})', row):
        format_counter['long_year'] += 1
      elif re.search(r"'(\d{2})", row):
        format_counter['short_year'] += 1

    # Set a format if at least half of the rows match the format
    if format_counter['long_year'] > 64:
      for separator in ['-', '/', ' ']:
        if samples.str.contains(separator).sum() > 64:
          if format_counter['ordinal'] > 64:
            chosen_format = f'%o{separator}%Y'
          else:
            chosen_format = f'%q{separator}%Y'
    elif format_counter['short_year'] > 64:
      chosen_format = "%q'%y"
    else:
      if format_counter['numeric'] > 64:
        chosen_format = '%I'
      elif format_counter['full'] > 64:
        chosen_format = '%Q'
      elif format_counter['ordinal'] > 64:
        chosen_format = '%o'
      else:         # abbreviated form is the default
        chosen_format = '%q'

    properties['supplement']['quarter'] = chosen_format
    return properties

  def establish_time_format(self, column, properties):
    """ Fill in the display format for times, if it's not already specified """
    if 'time' in properties['supplement']:
      return properties
    samples = column.sample(min(len(column), 128)).astype(str)
    format_counter = Counter()

    # Check against each option in time_formats
    for row in samples:
      for time_format in time_formats:
        try:
          if dt.strptime(row, time_format):
            format_counter[time_format] += 1
            break
        except ValueError:
          continue

    most_likely_format, format_count = format_counter.most_common(1)[0]
    if format_count < 16:
      most_likely_format = '%H:%M:%S'  # default to 24-hour format if we don't have enough evidence
    properties['supplement']['time'] = most_likely_format
    return properties

  def establish_timestamp_format(self, column, properties):
    """ Fill in the display format for timestamps, if it's not already specified """
    if 'timestamp' in properties['supplement']:
      return properties

    samples = column.sample(min(len(column), 128)).astype(str)
    format_counter = Counter()

    # Check against each option in timestamp_formats
    for row in samples:
      if row.lower().endswith('z'):
        format_counter['has_z'] += 1
      if 'T' in row:
        format_counter['has_t'] += 1
      if row.endswith('AM') or row.endswith('PM'):
        format_counter['has_indicator'] += 1

    # Set a format if at least half of the rows match the format
    if format_counter['has_z'] > 64:
      chosen_format = '%Y-%m-%dT%H:%M:%SZ' if format_counter['has_t'] > 64 else '%Y-%m-%d %H:%M:%SZ'
    elif format_counter['has_indicator'] > 64:
      chosen_format = '%Y-%m-%d %I:%M:%S %p'
    elif format_counter['has_t'] > 64:
      chosen_format = '%Y-%m-%dT%H:%M:%S'
    else:  # default to space-separated format
      chosen_format = '%Y-%m-%d %H:%M:%S'

    properties['supplement']['timestamp'] = chosen_format
    return properties

  def establish_week_format(self, column, properties):
    """ Fill in the display format for weeks, if it's not already specified """
    if 'week' in properties['supplement']:
      return properties
    samples = column.sample(min(len(column), 128)).astype(str)
    format_counter = Counter()

    for row in samples:
      if row.isnumeric():   # numeric form
        format_counter['%I'] += 1
      elif len(row) == 3:   # abbreviated form
        format_counter['%a'] += 1
      else:                 # full form
        format_counter['%A'] += 1

    most_likely_format = format_counter.most_common(1)[0][0]
    properties['supplement']['week'] = most_likely_format
    return properties

  def convert_to_date(self, tab_name, column, properties):
    properties = self.establish_date_format(column, properties)

    column = column.apply(lambda x: re.sub(r'(?<=\d)(st|nd|rd|th)', '', str(x)))
    column = column.apply(lambda x: x[:-6].strip() if x.endswith('+00:00') else x)
    column = column.apply(lambda x: x[:-9].strip() if x.endswith('T00:00:00') else x)
    column = column.apply(lambda x: x[:-8].strip() if x.endswith('00:00:00') else x)

    parsed_dates = pd.to_datetime(column, format=properties['supplement']['date'], errors='coerce')
    self.add_to_issues(tab_name, properties['col_name'], parsed_dates.isna(), column)
    return parsed_dates, properties

  def convert_to_month(self, tab_name, column, properties):
    original_column = column.copy()
    column = column.astype(str).str.lower()

    # Try to convert directly to numeric first
    parsed_month = pd.to_numeric(column, errors='coerce')

    # For rows that couldn't be converted, try text mappings
    for format_key, mapping in date_mappings['month'].items():
      mask = parsed_month.isna()
      if mask.any():
        parsed_month = parsed_month.fillna(column.map(mapping))

    # Anything left over is a problem
    self.add_to_issues(tab_name, properties['col_name'], parsed_month.isna(), original_column)
    return parsed_month, properties

  def convert_to_quarter(self, tab_name, column, properties):
    original_column = column.copy()
    column = column.astype(str).str.lower()
    parsed_quarters = pd.Series(index=column.index, dtype='float64')
    properties = self.establish_quarter_format(column, properties)

    for row_idx, value in column.items():
      # Remove common punctuation and whitespace
      clean_value = re.sub(r'[.,\s]+', '', value)

      try:  # Try to parse as a decimal directly
        decimal_value = float(clean_value)
        year_part = int(decimal_value)
        quarter_part = decimal_value - year_part
        # Only accept valid quarter decimals: 0.0, 0.25, 0.5, 0.75
        if abs(quarter_part - round(quarter_part * 4) / 4) < 1e-8:
          parsed_quarters[row_idx] = decimal_value
          continue
      except ValueError:
        pass

      year, quarter_num = 0, 0

      # Match quarter abbreviations (ie. Q1, Q2), ordinals (ie. 1st, 2nd), and full names
      if q_match := re.search(r'q(\d)', clean_value):
        quarter_num = int(q_match.group(1))
      if ord_match := re.search(r'(\d)(st|nd|rd|th)', clean_value):
        quarter_num = int(ord_match.group(1))
      for idx_name, quarter_name in enumerate(['first', 'second', 'third', 'fourth']):
        if quarter_name in clean_value:
          quarter_num = idx_name + 1
          break

      # Extract year if present
      year_match = re.search(r'(\d{4})', clean_value)
      if year_match:
        year = int(year_match.group(1))
      elif re.search(r"'(\d{2})", clean_value):
        year_short = int(re.search(r"'(\d{2})", clean_value).group(1))
        year = 2000 + year_short if year_short < 50 else 1900 + year_short

      # Convert to decimal format
      if 1 <= quarter_num <= 4:
        quarter_decimal = (quarter_num - 1) * 0.25
        parsed_quarters[row_idx] = year + quarter_decimal
      else:
        parsed_quarters[row_idx] = pd.NA

    # Store problematic rows
    self.add_to_issues(tab_name, properties['col_name'], parsed_quarters.isna(), original_column)
    return parsed_quarters, properties

  def convert_to_time(self, tab_name, column, properties):
    original_column = column.copy()
    column = column.astype(str).str.lower()
    properties = self.establish_time_format(column, properties)

    parsed_times = pd.to_datetime(column, format=properties['supplement']['time'], errors='coerce')
    self.add_to_issues(tab_name, properties['col_name'], parsed_times.isna(), original_column)
    return parsed_times, properties

  def convert_to_timestamp(self, tab_name, column, properties):
    """  See Ticket [1674] for more details
    exact=True is stricter and requires an exact match to be converted to a timestamp
    exact=False is more lenient and will convert to a timestamp if it can find any match
    For example, '2023-02-01 12:30' with exact=True is considered invalid because it's missing the seconds component
    But with exact=False, pandas fills in the missing seconds with '00' and successfully parses the datetime
    """
    properties = self.establish_timestamp_format(column, properties)
    # First attempt: Let pandas try with its optimized parser, catches 95% of cases
    parsed_timestamps = pd.to_datetime(column, errors='coerce', exact=False)
    failed_mask = parsed_timestamps.isna() & column.notna()

    if failed_mask.any():
      failed_values = column[failed_mask]

      # Second attempt: Handle timezone abbreviations
      tz_patterns = {
        r'\b(PST|PDT)\b': 'US/Pacific',       r'\b(EST|EDT)\b': 'US/Eastern',
        r'\b(CST|CDT)\b': 'US/Central',       r'\b(MST|MDT)\b': 'US/Mountain',
      }

      for pattern, tz_name in tz_patterns.items():
        mask = failed_values.astype(str).str.contains(pattern, na=False)
        if mask.any():  # if any of the failure cases contains timezone abbreviation, then clean it and parse again
          cleaned = failed_values[mask].astype(str).str.replace(pattern, '', regex=True)
          parsed = pd.to_datetime(cleaned, errors='coerce')
          # Localize to the timezone, then convert to UTC, then replace the parsed values if successful
          if not parsed.isna().all():
            try:
              parsed = parsed.dt.tz_localize(tz_name).dt.tz_convert('UTC').dt.tz_localize(None)
              parsed_timestamps.loc[failed_values[mask].index] = parsed
            except Exception as exp:
              pass  # Skip if we encounter issues with localization due to Daylight Savings or other edge cases

    self.add_to_issues(tab_name, properties['col_name'], parsed_timestamps.isna(), column)
    return parsed_timestamps, properties

  def convert_to_week(self, tab_name, column, properties):
    original_column = column.copy()
    column = column.astype(str).str.lower()

    # Try to convert directly to numeric first
    parsed_week = pd.to_numeric(column, errors='coerce')

    # For rows that couldn't be converted, try text mappings
    for format_key, mapping in date_mappings['week'].items():
      mask = parsed_week.isna()
      if mask.any():
        parsed_week = parsed_week.fillna(column.map(mapping))

    # Anything left over is a problem
    self.add_to_issues(tab_name, properties['col_name'], parsed_week.isna(), original_column)
    return parsed_week, properties

  def convert_dates_and_times(self, tab_name, column, properties):
    if properties['subtype'] in ['year', 'day', 'hour', 'minute', 'second']:
      column = column.astype('Int64')
    else:
      match properties['subtype']:
        case 'month':     column, properties = self.convert_to_month(tab_name, column, properties)
        case 'week':      column, properties = self.convert_to_week(tab_name, column, properties)
        case 'quarter':   column, properties = self.convert_to_quarter(tab_name, column, properties)
        case 'date':      column, properties = self.convert_to_date(tab_name, column, properties)
        case 'time':      column, properties = self.convert_to_time(tab_name, column, properties)
        case 'timestamp': column, properties = self.convert_to_timestamp(tab_name, column, properties)

    return column, properties

  def convert_to_type(self, tab_name, column, properties):
    self.store_blank_values(tab_name, column, properties)
    self.store_uncategorized_column(tab_name, column, properties)

    if properties['type'] == 'datetime':
      column, properties = self.convert_dates_and_times(tab_name, column, properties)
    match properties['subtype']:
      case 'id':      column = self.convert_to_id(tab_name, column, properties)
      case 'boolean': column = self.convert_to_boolean(tab_name, column, properties)
      case 'currency':column = self.convert_to_currency(tab_name, column, properties)
      case 'percent': column = self.convert_to_percent(tab_name, column, properties)
      case 'decimal': column = self.convert_to_decimal(tab_name, column, properties)
      case 'whole':   column = self.convert_to_whole(tab_name, column, properties)
      case _: pass

    return column, properties

  def store_blank_values(self, tab_name, column, properties):
    # Detect and store all types of blank values (null, missing, default) in issues dataframe
    blanks = []

    null_mask = column.isna() | (column == '')
    for idx in column.index[null_mask]:
      blanks.append({'row_id': idx, 'issue_type': 'blank','issue_subtype': 'null', 'original_value': None })

    missing_mask = column.astype(str).isin(missing_tokens)
    for idx in column.index[missing_mask]:
      blanks.append({'row_id': idx, 'issue_type': 'blank', 'issue_subtype': 'missing', 'original_value': column.loc[idx]})

    default_mask = column.astype(str).isin(default_tokens)
    for idx in column.index[default_mask]:
      blanks.append({'row_id': idx, 'issue_type': 'blank', 'issue_subtype': 'default', 'original_value': column.loc[idx]})

    if blanks and tab_name in self.issues:
      new_issues = pd.DataFrame([{'column_name': properties['col_name'], **blank} for blank in blanks])
      self.issues[tab_name] = pd.concat([self.issues[tab_name], new_issues], ignore_index=True)

  def store_uncategorized_column(self, tab_name, column, properties):
    # hold onto the raw format for future processing
    unknown_datatype = properties['type'] == 'unknown'
    unknown_subtype = properties['subtype'] == 'unknown'
    potential_probs = len(properties['potential_problem']) > 0
    if unknown_datatype or unknown_subtype or potential_probs:
      if tab_name != 'temp':
        self.tab_props[tab_name][properties['col_name']] = column

  @null_safety_decorator
  def display_as_boolean(self, df, tab_name, col_name):
    def get_display_value(row):
      if pd.isna(row[col_name]):
        return self.get_problematic_value(tab_name, col_name, row.name, NA_string)
      return row[col_name]

    return df.apply(get_display_value, axis=1)

  @null_safety_decorator
  def display_as_id(self, df, tab_name, col_name):
    def get_display_value(row):
      if pd.isna(row[col_name]):
        return self.get_problematic_value(tab_name, col_name, row.name, NA_string)
      return row[col_name]

    return df.apply(get_display_value, axis=1)

  @null_safety_decorator
  def display_as_currency(self, df, tab_name, col_name, supplement):
    currency_sign = supplement.get('currency', '$')
    def get_display_value(row):
      if pd.isna(row[col_name]):
        return self.get_problematic_value(tab_name, col_name, row.name, NA_string)
      return f"{currency_sign}{row[col_name]:,.2f}"

    return df.apply(get_display_value, axis=1)

  @null_safety_decorator
  def display_as_percent(self, df, tab_name, col_name):
    def get_display_value(row):
      if pd.isna(row[col_name]):
        return self.get_problematic_value(tab_name, col_name, row.name, NA_string)
      return f"{row[col_name]:.2%}"

    return df.apply(get_display_value, axis=1)

  @null_safety_decorator
  def display_as_decimal(self, df, tab_name, col_name):
    def get_display_value(row):
      if pd.isna(row[col_name]):
        return self.get_problematic_value(tab_name, col_name, row.name, NA_string)
      return f"{row[col_name]:.3f}"

    return df.apply(get_display_value, axis=1)

  @null_safety_decorator
  def display_as_time(self, df, tab_name, col_name, supplement):
    time_format = supplement.get('time', '%H:%M')
    def get_display_value(row):
      if pd.isna(row[col_name]):
        return self.get_problematic_value(tab_name, col_name, row.name, NA_string)
      elif time_format:
        return row[col_name].strftime(time_format)
      else:
        return row[col_name].dt.time.astype(str)

    return df.apply(get_display_value, axis=1)

  @null_safety_decorator
  def display_as_date(self, df, tab_name, col_name, supplement):
    date_format = supplement.get('date', '%Y-%m-%d')
    def get_display_value(row):
      if pd.isna(row[col_name]):
        return self.get_problematic_value(tab_name, col_name, row.name, NA_string)
      return row[col_name].strftime(date_format)

    return df.apply(get_display_value, axis=1)

  @null_safety_decorator
  def display_as_month(self, df, tab_name, col_name, supplement):
    month_abbreviations = [NA_string, 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    month_full = [NA_string, 'January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
    month_format = supplement.get('month', '%b')

    if df[col_name].dtype == 'datetime64[ns]':
      if month_format == '%I':
        display_column = df[col_name].dt.month
      else:
        display_column = df[col_name].dt.strftime(month_format)
    else:
      # Check if values are already in month_abbreviations or month_full
      display_column = df[col_name].astype(str).copy()
      # Only convert numeric-looking values
      numeric_values = pd.to_numeric(df[col_name], errors='coerce')
      mask_numeric = (numeric_values.notna()) & (numeric_values > 0)

      if mask_numeric.any():
        numeric_df = numeric_values[mask_numeric].fillna(0).astype(int)

        match month_format:
          case '%I': pass  # Keep original values
          case '%b': display_column[mask_numeric] = numeric_df.apply(lambda x: month_abbreviations[x])
          case '%B': display_column[mask_numeric] = numeric_df.apply(lambda x: month_full[x])

    display_column = self.attach_problematic_values(display_column, col_name, supplement, tab_name)
    return display_column.fillna(NA_string)

  @null_safety_decorator
  def display_as_week(self, df, tab_name, col_name, supplement):
    week_abbreviations = [NA_string, 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
    week_full = [NA_string, 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    week_format = supplement.get('week', '%a')

    if df[col_name].dtype == 'datetime64[ns]':
      if week_format == '%I':
        display_column = df[col_name].dt.dayofweek
      else:
        display_column = df[col_name].dt.strftime(week_format)
    else:
      # Check if values are already in week_abbreviations or week_full
      display_column = df[col_name].copy()
      # Only convert numeric-looking values
      mask_numeric = df[col_name].astype(str).str.match(r'^\d+$')

      if mask_numeric.any():
        numeric_df = pd.to_numeric(df[col_name][mask_numeric], errors='coerce')
        numeric_df = numeric_df.fillna(0).astype(int)

        match week_format:
          case '%I': pass  # Keep original values
          case '%a':
            display_column[mask_numeric] = numeric_df.apply(lambda x: week_abbreviations[x])
          case '%A':
            display_column[mask_numeric] = numeric_df.apply(lambda x: week_full[x])

    display_column = self.attach_problematic_values(display_column, col_name, supplement, tab_name)
    return display_column.fillna(NA_string)

  @null_safety_decorator
  def display_as_quarter(self, df, tab_name, col_name, supplement):
    ordinal_quarters = [NA_string, '1st', '2nd', '3rd', '4th']
    quarter_abbreviations = [NA_string, 'Q1', 'Q2', 'Q3', 'Q4']
    quarter_full = [NA_string, 'First Quarter', 'Second Quarter', 'Third Quarter', 'Fourth Quarter']
    quarter_format = supplement.get('quarter', '%q')

    def get_display_value(row):
      if pd.isna(row[col_name]):
        return self.get_problematic_value(tab_name, col_name, row.name, NA_string)

      # 0.0 = Q1, 0.25 = Q2, 0.5 = Q3, 0.75 = Q4
      quarter_value = row[col_name]
      year = int(quarter_value)
      quarter_num = min(4, int((quarter_value - year) * 4) + 1)

      replacements = {
        '%I': '0' + str(quarter_num),     '%-I': str(quarter_num),     '%o': ordinal_quarters[quarter_num],
        '%q': quarter_abbreviations[quarter_num],   '%Q': quarter_full[quarter_num],
        '%y': "" if year == 0 else str(year)[-2:],  '%Y': "" if year == 0 else str(year)
      }

      display_value = quarter_format
      for pattern, replacement in replacements.items():
        display_value = display_value.replace(pattern, replacement)
      return display_value

    display_column = df.apply(get_display_value, axis=1)
    display_column = self.attach_problematic_values(display_column, col_name, supplement, tab_name)
    return display_column.fillna(NA_string)

  @null_safety_decorator
  def display_as_timestamp(self, df, tab_name, col_name, supplement):
    timestamp_format = supplement.get('timestamp', '%Y-%m-%dT%H:%M:%S%z')
    def get_display_value(row):
      if pd.isna(row[col_name]):
        return self.get_problematic_value(tab_name, col_name, row.name, NA_string)
      return row[col_name].strftime(timestamp_format)

    return df.apply(get_display_value, axis=1)

  def attach_problematic_values(self, display_column, col_name, supplement, tab_name):
    offset = supplement.get('offset', 0)
    if offset < len(display_column) and tab_name in self.issues:
      issues_df = self.issues[tab_name]
      matching_issues = issues_df[issues_df['column_name'] == col_name]

      for _, issue in matching_issues.iterrows():
        row_id = issue['row_id']
        if row_id >= offset:
          display_column[row_id-offset] = issue['original_value']
    return display_column

  def display_as_type(self, df, tab_name, col_name, type, subtype, supplement={}):
    """ Insert the original values for problematic rows, fill NaNs with <N/A> """
    if len(df[col_name]) == 0: return df[col_name]

    match subtype:
      case 'id':        column = self.display_as_id(df, tab_name, col_name)
      case 'boolean':   column = self.display_as_boolean(df, tab_name, col_name)
      case 'currency':  column = self.display_as_currency(df, tab_name, col_name, supplement)
      case 'percent':   column = self.display_as_percent(df, tab_name, col_name)
      case 'decimal':   column = self.display_as_decimal(df, tab_name, col_name)
      case 'date':      column = self.display_as_date(df, tab_name, col_name , supplement)
      case 'month':     column = self.display_as_month(df, tab_name, col_name, supplement)
      case 'quarter':   column = self.display_as_quarter(df, tab_name, col_name, supplement)
      case 'time':      column = self.display_as_time(df, tab_name, col_name, supplement)
      case 'timestamp': column = self.display_as_timestamp(df, tab_name, col_name, supplement)
      case 'week':      column = self.display_as_week(df, tab_name, col_name, supplement)
      case _:           column = df[col_name].astype(object).fillna(NA_string)

    if column.name != col_name:
      column.name = col_name
    return column
