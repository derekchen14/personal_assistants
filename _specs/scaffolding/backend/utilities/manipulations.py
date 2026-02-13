import re
import numpy as np
import pandas as pd
from collections import defaultdict
from datetime import datetime as dt

from backend.components.engineer import PromptEngineer
from collections import Counter
from backend.assets.ontology import missing_tokens

def check_slice_preferences(context, flow, state):
  # Check if there are any preferences that need to be updated
  if len(state.slices['preferences']) > 0:
    pref_name = state.slices['preferences'].pop()
    user_pref = context.preferences.get_pref(pref_name, top_ranking=False)

    new_ent = flow.slots['target'].values[0]
    new_table, new_column = new_ent['tab'], new_ent['col']

    pref_value = user_pref.top_rank()
    pref_detail = f"{new_column} column in {new_table} table"
    user_pref.set_ranking(pref_value, pref_detail)
    user_pref.assign_entity(new_table, new_column, ver=True)

  return state, context

def can_join_by_id(flow, memory_db, world):
  # There is no need to ask for user interaction if the tables have a common ID column for joining immediately
  unique_tables = list(set([entity['tab'] for entity in flow.slots['source'].values]))
  # There should be exactly two tables
  if len(unique_tables) != 2:
    return False

  id_columns = defaultdict(list)
  for side, tab_name in zip(['left', 'right'], unique_tables):
    valid_col_list = world.valid_columns[tab_name]
    tab_schema = world.metadata['schema'][tab_name]
    for col_name in valid_col_list:
      if tab_schema.get_type_info(col_name)['subtype'] == 'id':
        id_columns[side].append(col_name)

  # Both tables must contain at least one ID column
  if len(id_columns['left']) == 0 or len(id_columns['right']) == 0:
    return False

  # Test if they share common values which can be used as foreign keys
  left_tab_name, right_tab_name = unique_tables
  left_table, right_table = memory_db.tables[left_tab_name], memory_db.tables[right_tab_name]
  left_pkey, right_pkey = memory_db.primary_keys[left_tab_name], memory_db.primary_keys[right_tab_name]

  for left_column in id_columns['left']:
    left_values = left_table[left_column].unique()
    num_left = min(128, len(left_values))
    left_samples = np.random.choice(left_values, num_left, replace=False)

    for right_column in id_columns['right']:
      right_values = right_table[right_column].unique()
      num_right = min(128, len(right_values))
      right_samples = np.random.choice(right_values, num_right, replace=False)

      # they should not both be primary keys
      if left_column == left_pkey and right_column == right_pkey:
        continue

      # the ratios represent how much of the samples are found in the other table
      left_overlap_count = len(set(left_samples).intersection(right_values))
      right_overlap_count = len(set(right_samples).intersection(left_values))
      left_ratio, right_ratio = left_overlap_count / num_left, right_overlap_count / num_right
      # if these are truly foreign keys, then the ratios should be high
      if (left_ratio + right_ratio > 1.0):
        flow.slots['source'].drop_unverified()
        flow.slots['source'].add_one(unique_tables[0], left_column)
        flow.slots['source'].add_one(unique_tables[1], right_column)
        return True

  return False

def can_join_directly(flow, world):
  # There should be exactly two tables
  unique_tables = list(set([entity['tab'] for entity in flow.slots['source'].values]))
  if len(unique_tables) == 2:
    left_tab, right_tab = unique_tables
  else:
    return False

  # There should be exactly two columns
  left_columns = [entity['col'] for entity in flow.slots['source'].values if entity['tab'] == left_tab]
  right_columns = [entity['col'] for entity in flow.slots['source'].values if entity['tab'] == right_tab]
  if len(left_columns) == 1 and len(right_columns) == 1:
    left_col, right_col = left_columns[0], right_columns[0]
  else:
    return False

  # The column types must match
  left_col_type = world.metadata['schema'][left_tab].get_type_info(left_col)
  right_col_type = world.metadata['schema'][right_tab].get_type_info(right_col)
  return left_col_type['type'] == right_col_type['type']

def foreign_key_column_found(flow, state):
  left_entity, right_entity = flow.slots['source'].values
  left_tab, right_tab = left_entity['tab'], right_entity['tab']
  left_col, right_col = left_entity['col'], right_entity['col']
  state.ambiguity.declare('confirmation', slot='source', values=[left_col, right_col])

  if left_col == right_col:
    observe = f"There is already a column called '{left_col}' that can join the {left_tab} and {right_tab} tables together. "
    observe += "You can directly ask your query without merging the two tables."
    flow.completed = True       # This is so straightforward that we can directly mark the flow as complete
  else:
    observe = f"It seems we can join the {left_tab} and {right_tab} tables using the {left_col} and {right_col} columns. "
    observe += "Did you know renaming one of the columns to the other is sufficient for connecting these tables together."
  state.ambiguity.observation = observe
  return flow, state

def apply_merge_styles(current_df, style_name, style_detail, reference_col, results):
  suitable_count = 0

  for result in results:
    retain_df = current_df.loc[result['retain']]
    retire_df = current_df.loc[result['retire']]

    if style_name == 'order':
      retain_value = retain_df.index[0]
      retire_value = retire_df.index[0]
    else:
      retain_value = retain_df[reference_col].iloc[0]
      retire_value = retire_df[reference_col].iloc[0]

    if retain_value == retire_value:
      suitable_count += 1
    elif explains_merge(style_name, style_detail, retain_value, retire_value):
      suitable_count += 1

  score = suitable_count / float(len(results))
  return score

def explains_merge(style_name, detail, retain_value, retire_value):
  if style_name == 'contains':
    style_func = lambda x, y: detail in str(x) and detail not in str(y)
  else:
    setting_options = get_setting_options(style_name)
    style_func = setting_options.get(detail, lambda x, y: False)
  return style_func(retain_value, retire_value)

def get_setting_options(style_name):
  match style_name:
    case 'order':
      return {'first': lambda x, y: x < y, 'last': lambda x, y: x > y}
    case 'time':
      return {'earlier': lambda x, y: x < y, 'later': lambda x, y: x > y}
    case 'binary':
      return {'positive': lambda x, y: x is True and y is False,
              'negative': lambda x, y: x is False and y is True}
    case 'size':
      return {'minimum': lambda x, y: x < y, 'maximum': lambda x, y: x > y}
    case 'length':
      return {'longer': lambda x, y: len(str(x)) > len(str(y)),
              'shorter': lambda x, y: len(str(x)) < len(str(y))}
    case 'alpha':
      return {'A to Z': lambda x, y: str(x) < str(y),
              'Z to A': lambda x, y: str(x) > str(y)}
    case _:
      return {}

def trivial_duplicate_case(flow, tables, world):
  tab_name = flow.slots['removal'].values[0]['tab']
  all_columns = tables[tab_name].columns
  tab_schema = world.metadata['schema'][tab_name]
  source_columns = set([entity['col'] for entity in flow.slots['removal'].values if entity['tab'] == tab_name])

  trivial_case = False
  # scenario is trivial when user selects all columns
  if len(source_columns) == len(all_columns):
    trivial_case = True

  # scenario is also trivial if there is one column missing and it is an ID column
  elif len(source_columns) == len(all_columns) - 1:
    excluded_col = list(set(all_columns) - source_columns)[0]
    col_schema = tab_schema.get_type_info(excluded_col)
    if col_schema['subtype'] == 'id':
      trivial_case = True
  return trivial_case

def make_column_list(valid_col_list, selected_cols):
  column_list = []
  for col_name in valid_col_list:
    if col_name in selected_cols:
      column_list.append(f'@{col_name}')
    else:
      column_list.append(col_name)
  column_list = ', '.join(column_list)
  return column_list

def possible_reference_columns(flow, data_schema, valid_col_list):
  # Set default reference columns for merge styles that require a column to operate on, see [0714]
  col_options = {'boolean': [], 'number': [], 'text': [], 'time': []}
  source_cols = [entity['col'] for entity in flow.slots['removal'].values]

  # try to find a column that matches the requirements for each style
  for col_name in valid_col_list:
    if col_name in source_cols:
      continue
    schema = data_schema.get_type_info(col_name)
    if schema['subtype'] == 'boolean':
      col_options['boolean'].append(col_name)
    elif schema['type'] == 'number':
      col_options['number'].append(col_name)
    elif schema['type'] == 'text':
      col_options['text'].append(col_name)
    elif schema['subtype'] in ['timestamp', 'date', 'time', 'month']:
      col_options['time'].append(col_name)

  style_to_type = { 'binary': 'boolean', 'contains': 'text', 'length': 'text',
                    'alpha': 'text', 'size': 'number', 'time': 'time'}
  for merge_style, column_type in style_to_type.items():
    reference = flow.slots['settings'].value['reference']
    if isinstance(reference, str):
      reference = {}     # if reference is still a string, then convert it to a dictionary
    style_column = reference.get(f'{merge_style}_col', '')

    if len(col_options[column_type]) > 0 and len(style_column) == 0:
      reference[f'{merge_style}_col'] = col_options[column_type][0]
    flow.slots['settings'].value['reference'] = reference
  return flow

def serialize_for_json(value):
  if isinstance(value, np.generic):
    return value.item()
  elif isinstance(value, pd.Timestamp):
    return value.isoformat()
  elif isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
    return None
  else:
    return value

def count_to_nl(count):
  match count:
    case 1: return "one"
    case 2: return "two"
    case 3: return "three"
    case _: return str(count)

def skip_repeat_token(template):
  # if a token is repeated two steps ahead, we should remove it
  tokens = template.split()
  idx = 0
  while idx < len(tokens) - 2:
    if tokens[idx] == tokens[idx + 2]:  # Remove the next two tokens
      del tokens[idx + 1]
      del tokens[idx + 1]
    else:
      idx += 1  # Only increment if no deletion happens
  response = " ".join(tokens)
  return response

def determine_level(prepare_methods):
  method_names = [method['name'] for method in prepare_methods]

  for method in ['stage', 'validate', 'dedupe', 'merge', 'prune']:
    if method in method_names:
      return 'intermediate'
  for method in ['embed', 'measure', 'cross', 'other']:
    if method in method_names:
      return 'advanced'

  if len(method_names) >= 8:
    level = 'advanced'
  elif len(method_names) >= 4:
    level = 'intermediate'
  else:
    level = 'basic'
  return level

def preview_tables(table_names, tables, num_rows=16):
  preview_lines = []
  for index, tab_name in enumerate(table_names):
    table_df = tables[tab_name]
    preview_lines.append(f"Table {index + 1}: {tab_name} ({len(table_df)} rows)")
    preview_lines.append(PromptEngineer.display_preview(table_df, max_rows=num_rows, signal_limit=False))
    preview_lines.append('')

  data_preview = '\n'.join(preview_lines)
  return data_preview

def get_row_limit(num_columns, default=8, max_cells=256):
  # Returns the number of rows to display given the column count, such that total num_cells < max_cells
  if num_columns <= 16:
    return max_cells // max(1, num_columns)
  else:  # if there are a lot of columns, just use the default limit
    return default

def unique_value_distribution(column, settings, targets=None, suffix=''):
  """
  settings is a dictionary with the following keys:
    - include_nulls: whether to include null values in the distribution
    - show_nulls_as_count: whether to show null values as a count or as a separate category
    - show_arrow: whether to show an arrow for targeting the value with issues
  suffix could be 'cases', 'rows', 'instances', 'occurrences', etc.
  """
  num_values = settings.get('num_values', 4)
  num_uniques = column.nunique()
  unique_counts = Counter(column)
  max_values_to_show = min(num_uniques, num_values)
  top_values = unique_counts.most_common(max_values_to_show)

  # determine which unique values have issues
  if settings['show_arrow'] and targets is not None:
    displayed = False
    unique_issues = targets['original_value'].dropna().unique()
  else:
    displayed = True  # if we are not showing an arrow, then we have already displayed all the unique issues
    unique_issues = set()

  lines = []
  for value, count in top_values:
    if isinstance(value, str) and len(value) > 128:
      value = value[:128] + " ..."
    sample_line = f"{value} - {count}{suffix}"

    if count > 1 and len(suffix) > 0:
      sample_line += "s"
    if settings['show_arrow'] and value in unique_issues:
      displayed = True
      sample_line += " <--"

    lines.append(sample_line)
    if len(lines) >= max_values_to_show:
      break

  if not displayed:
    for value in unique_issues:
      count = unique_counts[value]
      sample_line = f"{value} - {count}{suffix}"
      if count > 1 and len(suffix) > 0:
        sample_line += "s"
      sample_line += " <--"
      lines.append(sample_line)

  if settings['include_nulls']:
    null_count = column.isna().sum()
    if null_count > 0:
      if settings['show_nulls_as_count']:
        line = f"<N/A> - {null_count}{suffix}"
      else:
        line = f"{null_count} empty rows"
      lines.append(line)

  if num_uniques > num_values:
    num_remaining = num_uniques - num_values
    lines.append(f"{num_remaining} remaining values ...")

  data_distribution = '\n'.join(lines)
  return data_distribution

def find_default_value(series, limit=4096) -> str:
  # Find the first blank or missing value in a pandas Series by checking for common missing tokens.
  if limit < 0 or limit >= len(series):
    limited_edition = series
  else:
    limited_edition = series.head(limit)

  for value in limited_edition.astype(str).str.lower():
    if value in missing_tokens:
      return value
  return ''

def date_format_alignment(date_str):
  # Check if string matches ISO 8601 date format 'YYYY-MM-DD'
  date_pattern = r'^(\d{4})-(\d{2})-(\d{2})$'
  days_in_month = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

  if date_match := re.match(date_pattern, date_str):
    year, month, day = map(int, date_match.groups())

    if 1000 <= year <= 9999 and 1 <= month <= 12:
      days_allowed = days_in_month[month]
      if 1 <= day <= days_allowed:
        return True
  return False

def month_format_alignment(month_str):
  # Check if string represents a valid month number (1-12)
  is_aligned = month_str.isdigit() and 1 <= int(month_str) <= 12
  return is_aligned

def quarter_format_alignment(quarter_str):
   # Check if string represents a valid quarter decimal (YYYY.Q format)
  if not quarter_str.replace('.', '').replace('-', '').isdigit():
    return False

  quarter_float = float(quarter_str)
  year_part = int(quarter_float)
  fractional_part = quarter_float % 1

  valid_year = year_part == 0 or (1000 <= year_part <= 9999)
  valid_quarter = fractional_part in [0.0, 0.25, 0.5, 0.75]

  return valid_year and valid_quarter

def time_format_alignment(time_str):
 # Check if string matches ISO 8601 time format 'HH:MM:SS'
 time_pattern = r'^(\d{2}):(\d{2}):(\d{2})$'

 if time_match := re.match(time_pattern, time_str):
   hour, minute, second = map(int, time_match.groups())
   return 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59
 return False

def timestamp_format_alignment(timestamp_str):
  # Check if string matches ISO 8601 timestamp format 'YYYY-MM-DDTHH:MM:SSZ'
  if not timestamp_str.endswith('Z') or 'T' not in timestamp_str:
    return False

  date_part, time_part = timestamp_str[:-1].split('T')
  date_is_aligned = date_format_alignment(date_part)
  time_is_aligned = time_format_alignment(time_part)
  return date_is_aligned and time_is_aligned

def week_format_alignment(week_str):
  # Check if string represents a valid week number (1-7)
  is_aligned = week_str.isdigit() and 1 <= int(week_str) <= 7
  return is_aligned