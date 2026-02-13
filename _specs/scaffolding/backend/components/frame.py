import re
import json
import pandas as pd
from backend.assets.ontology import NA_string

class Frame(object):

  def __init__(self, table_name='', tab_type='direct', source='default'):
    self.raw_table = table_name   # the name of the main table
    self.tab_type = tab_type      # direct, decision, dynamic, or derived
    self.source = source          # sql, pandas, plotly, interaction, or default
    self.properties = {}
    self.shadow = {}

    self.data = pd.DataFrame()    # used for derived tables
    self.code = ''                # used for derived tables
    self.error = ''               # options: code_generation, invalid_dataframe, empty_results, null_values_found
    self.visual = None            # a visual representation of the data expressed as a plotly figure
    self.warning = ''             # warning message to user
    self.primary_key = ''         # the primary key of the table

    self.has_content = False
    self.has_changes = False
    self.active_conflicts = []
    self.issues_entity = {}
    self.resolved_rows = []
    self.control = {'create': '', 'drop': '', 'rename': ''}   # name of possible tables to be controlled

  def get_data(self, form='df', limit=-1):
    data = self.data.head(limit) if limit > 0 else self.data

    if form == 'df':
      return data
    elif form == 'str':
      return str(data)
    elif form == 'json':
      if self.has_content:
        return self.show_display_view() if len(self.shadow) > 0 else data.to_json(orient='records')
      else:
        return self._empty_data(form)
    elif form == 'md':
      return data.to_markdown(index=False)
    elif form == 'dict':
      return data.to_dict()
    elif form == 'define':
      return self.defining_characteristics()
    elif form == 'list':
      return self._json_friendly_list(data)

  def set_data(self, dataframe, code='', source=''):
    self.data = dataframe
    self.has_content = len(self.data) > 0
    if len(code) > 0:
      self.code = code
    if len(source) > 0:
      self.source = source

  def get_columns(self) -> list:
    if self.has_content:
      return self.data.columns.tolist()
    else:
      return []

  def _empty_data(self, form):
    # use the columns of the dataframe to create a list of empty dicts
    empty = [dict(zip(self.data.columns, [""]*len(self.data.columns)))]
    return json.dumps(empty) if form == 'json' else empty

  def _json_friendly_list(self, data):
    if self.has_content:
      filled_data = data.fillna(NA_string)
      data_as_list = list(filled_data.T.to_dict().values())

      try:
        # check if first few rows of data can be converted to json, to prevent downstream errors
        converted = json.dumps(data_as_list[:10])
      except TypeError:
        # convert any numpy datatypes to standard python datatypes that can be serialized
        for row in data_as_list:
          for column, value in row.items():
            if isinstance(value, (pd.Timestamp, pd.Interval)):
              row[column] = str(value)
      return data_as_list
    else:
      return self._empty_data('list')

  def defining_characteristics(self):
    characteristics = {
      'tabs': self.properties.get('tabs', [self.raw_table]),
      'cols': self.data.columns.tolist(), 'rows': len(self.data),
      'control': self.control, 'reset': self.has_changes
    }

    if self.tab_type == 'dynamic':
      if len(self.active_conflicts) > 0:
        # frame for resolving conflicts
        cardset_idx = self.properties.get('cardset_index', 0)
        cardset = self.active_conflicts[cardset_idx]
        conflict_rows, conflict_cols = self.populate_conflicts(cardset)

        characteristics['tabs'] = cardset['tables']    # list of tables
        characteristics['rows'] = conflict_rows
        characteristics['cols'] = conflict_cols
        characteristics['conflicts'] = max(max(cr) for cr in conflict_rows) + 1

      else:
        # frame for resolving issues
        issue_col = self.issues_entity['col']
        characteristics['tabs'] = [self.issues_entity['tab']]  # single table within a list
        characteristics['rows'] = self.data.index.tolist()
        characteristics['cols'] = self.issues_entity['col']    # single column string
        characteristics['issues'] = self.data[issue_col].fillna(NA_string).to_dict()
    return characteristics

  def populate_conflicts(self, cardset):
    conflict_rows, conflict_cols = [], []

    # cards for removing duplicates
    if 'cards' in cardset:
      conflict_rows.append(cardset['row_ids'])
      one_card = cardset['cards'][0]
      conflict_cols.append(list(one_card.keys()))

    else: # cards for integrating tables
      for side in ['left', 'right']:
        row_ids = cardset['row_ids'][side]
        one_card = cardset[side][0]
        conflict_rows.append(row_ids)
        conflict_cols.append(list(one_card.keys()))

    return conflict_rows, conflict_cols

  def store_display_view(self, properties, shadow_db):
    shadow_entities = []

    for col_name in self.data.columns:
      if col_name in properties:
        col_type = properties[col_name].get('type', 'text')
        col_subtype = properties[col_name].get('subtype', 'general')
        col_supplement = properties[col_name].get('supplement', {})
        display = shadow_db.display_as_type(self.data, 'temp', col_name, col_type, col_subtype, col_supplement)
        self.shadow[col_name] = display

      shadow_entities.append({'tab': 'temp', 'col': col_name})
    return shadow_entities

  def show_display_view(self):
    display_view = self.data.copy()
    for col_name, display_data in self.shadow.items():
      display_view[col_name] = display_data
    return display_view.to_json(orient='records')

  def signal_failure(self, error_type, warning_msg=''):
    """ Warning messages are primarily used for prompting the model to resolve ambiguities.
    * They do not contain a prefix in the beginning, nor any punctuation at the end
    * We assume warnings follow the phrase: 'We have a problem where ...', so they are not capitalized
    * Are not directed toward the user, but instead state the problem in a neutral tone
    """
    warning_messages = {
      'dataframe_is_none': 'results were dropped somewhere since dataframe is None',
      'invalid_dataframe': 'results were corrupted since dataframe is invalid',
      'empty_results': 'the query returned an empty dataframe with zero rows',
      'null_values_found': 'the output dataframe contains null values'
    }

    if warning_msg == '':
      if error_type in warning_messages:
        warning_msg = warning_messages[error_type]
    elif error_type == 'code_generation':
      warning_msg = f'an error occurred during code generation: {warning_msg}'

    self.error = error_type
    self.warning = warning_msg

  def overcome_failure(self, verbose=False):
    self.error = ''
    self.warning = ''

    if verbose:
      print(f"  Repaired SQL Query:\n  {self.code}")
      print(self.get_data('md', limit=7))

  def is_successful(self):
    return len(self.error) == 0 or self.error == 'null_values_found'

  def data_by_location(self, row_id, col_name=''):
    """ returns the value of the cell at the given row_id and col_name """
    if row_id in self.data.index:
      if len(col_name) == 0:
        if len(self.primary_key) > 0:
          return self.data.loc[row_id, self.primary_key]
        else:
          raise ValueError("Missing column name when pulling from Frame.")
      else:
        return self.data.loc[row_id, col_name]
    else:
      raise ValueError(f"row_id {row_id} not found in {self.data.index}")



  def preview_row_count(self, flow):
    # Returns the number of rows to display during RES preview
    truncated = False
    num_rows = len(self.data)

    if 'operation' in flow.slots:
      for operation in flow.slots['operation'].values:
        if operation.startswith('aggregate'):
          if 'top' in operation or 'bottom' in operation:
            # search for a number 0 to 99 within the operation string
            top_bottom_pattern = r'(top|bottom)\s?(\d{1,2})'
            limit_match = re.search(top_bottom_pattern, operation)
            if limit_match:
              req_amount = limit_match.group(2)
              num_rows = min(16, int(req_amount))
              truncated = True
              break

    if self.has_content and len(self.data) > 64 and not truncated:
      num_rows = 64
    return num_rows
  
  def serialize(self):
    """Serialize frame object into a JSON-serializable format for database storage"""
    return {
      'type': self.tab_type,
      'columns': self.get_columns(),
      'status': 'success' if self.is_successful() else 'error',
      'source': self.source,
      'code': self.code
    }