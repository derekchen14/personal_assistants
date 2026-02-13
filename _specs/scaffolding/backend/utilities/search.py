import os
os.environ['NLTK_DATA'] = os.path.join(os.path.dirname(__file__), 'utils', 'nltk_data')

import re
from math import ceil
import numpy as np
import pandas as pd
import Levenshtein as lev
import random

from textblob import Word
from collections import defaultdict, Counter
from tqdm import tqdm as progress_bar
from datasketch import MinHash, MinHashLSH

from backend.assets.ontology import common_abbreviations, state_abbreviations
from backend.prompts.grounding import grounding_prompts
from backend.components.engineer import PromptEngineer

def find_nearest_valid_option(target: str, valid_options: list[str]) -> str:
  if not target or not valid_options:
    return target

  # First try exact match
  if target in valid_options:
    return target

  # Next try case-insensitive match
  target_lower = target.lower()
  for valid_opt in valid_options:
    if valid_opt.lower() == target_lower:
      return valid_opt

  # Finally, try matching just letters/numbers, ignoring space and punctuation
  target_alphanumeric = ''.join(char.lower() for char in target if char.isalnum())
  for valid_opt in valid_options:
    valid_alphanumeric = ''.join(char.lower() for char in valid_opt if char.isalnum())
    if valid_alphanumeric == target_alphanumeric:
      return valid_opt

  return target

def sample_from_series(series: pd.Series, max_samples=16384, sample_rate=0.1, contiguous=False, strict=False):
  """ draw up to 16,384 (2^14) samples or 10% of the series, whichever is smaller """
  sample_size = min(max_samples, ceil(len(series) * sample_rate))
  if contiguous:
    start_idx = random.randint(0, len(series) - sample_size)
    if strict:
      data = series.iloc[start_idx:start_idx + sample_size]
    else:
      data = series.iloc[start_idx:start_idx + sample_size] if len(series) > 10000 else series
  else:
    if strict:
      data = series.sample(n=sample_size, replace=False)
    else:
      data = series.sample(n=sample_size, replace=False) if len(series) > 10000 else series
  return data

def convert_to_date(date_string):
  try:
    return pd.to_datetime(date_string, errors='coerce')
  except ValueError:
    return pd.NaT

def hash_row(row, num_perm=128):
  mh = MinHash(num_perm=num_perm)
  for value in row:
    mh.update(str(value).encode('utf8'))
  return mh

def detect_exact_duplicates(df, num_perm=128, threshold=0.9):
  """Detect duplicates using MinHash LSH (locality sensitive hashing)  
  Rows are considered duplicates of each other if at least 90% of the values in the two rows
  are exact matches. We transform this rule to Jaccard similarity threshold for MinHashLSH. """
  minhashes = {index: hash_row(row, num_perm) for index, row in df.iterrows()}
  lsh = MinHashLSH(threshold=threshold, num_perm=num_perm)
  for index, minhash in minhashes.items():
    lsh.insert(index, minhash)

  duplicate_groups = []
  for index in df.index:
    duplicates = lsh.query(minhashes[index])
    if len(duplicates) > 1:
      duplicate_groups.append(duplicates)
  return duplicate_groups

lower_case_abbrev = {k.lower(): v for k, v in common_abbreviations.items()}

def normalize_term(term):
  # replace punctuation and underscores, change to lowercase
  processed = re.sub(r'\W|_', ' ', term.lower())
  tokens = processed.split()
  # deal with marketing and state abbreviations
  tokens = [lower_case_abbrev.get(token, token) for token in tokens]
  tokens = [state_abbreviations.get(token, token) for token in tokens]
  # lemmatize tokens for further normalization
  tokens = [Word(token).lemmatize() for token in tokens]
  processed = ' '.join(tokens)
  tokens.sort()
  return processed, tokens

def select_columns_to_display(df, start_columns):
  """ Selects up to 7 columns to display in the table looking left and then right """
  result = start_columns[:]
  options = list(df.columns)
  left_indexes = [options.index(i) - 1 for i in start_columns]
  right_indexes = [options.index(i) + 1 for i in start_columns]

  while len(result) < 7 and len(result) < len(options):
    for left, right in zip(left_indexes, right_indexes):
      if left >= 0 and options[left] not in result:
        result.append(options[left])
        if len(result) == 7 or len(result) == len(options):
          return result

      if right < len(options) and options[right] not in result:
        result.append(options[right])
        if len(result) == 7 or len(result) == len(options):
          return result

    left_indexes = [i - 1 for i in left_indexes]
    right_indexes = [i + 1 for i in right_indexes]
  return result

def select_rows_to_display(df, start_rows):
  """ Selects a balanced amount of rows to display based on number of start rows """
  all_indices = set(df.index)
  remaining = all_indices.difference(set(start_rows))

  ratio = 3 / np.sqrt(len(start_rows))
  n_indices = int(np.round(ratio * len(start_rows)))

  sampled_rows = np.random.choice(list(remaining), size=n_indices, replace=False)
  final_indices = list(start_rows) + list(sampled_rows)
  return final_indices

def count_overlaps(row1, row2):
  num_exact_overlap, num_high_overlap = 0, 0
  for val1, val2 in zip(row1, row2):
    str1, str2 = str(val1), str(val2)
    same_length = len(str1) == len(str2)

    if str1 == str2:
      num_exact_overlap += 1
    elif same_length and str1[0] == str2[0] and str1[-1] == str2[-1]:
      num_high_overlap += 1

  return num_exact_overlap, num_high_overlap

def rows_are_extremely_similar(row1, row2, num_columns):
  exact_overlap, high_overlap = count_overlaps(row1, row2)

  if num_columns == 1:
    return high_overlap == 1
  elif num_columns == 2:
    return exact_overlap == 1 and high_overlap == 1
  elif num_columns == 3:
    return exact_overlap >= 2
  elif num_columns == 4:
    return exact_overlap >= 2 and high_overlap >= 1
  else:  # extend the pattern for more than 4 columns
    required_exact = (num_columns + 1) // 2
    return exact_overlap >= required_exact and (exact_overlap > required_exact or high_overlap >= 1)

def cross_tab_near_match(left_df, right_df, max_matches):
  # Returns a list of dicts, where each dict contains lists of matching row ids
  matching_rows = []
  processed_rows = set()
  num_columns = len(left_df.columns)

  for left_idx, left_row in progress_bar(left_df.iterrows(), total=len(left_df)):
    if left_idx in processed_rows:
      continue
    current_group = {'left': [left_idx], 'right': []}

    # Check against other rows in left_df
    for other_left_idx, other_left_row in left_df.iterrows():
      if other_left_idx != left_idx and other_left_idx not in processed_rows:
        if rows_are_extremely_similar(left_row, other_left_row, num_columns):
          current_group['left'].append(other_left_idx)
          processed_rows.add(other_left_idx)

    # Check against rows in right_df
    for right_idx, right_row in right_df.iterrows():
      if rows_are_extremely_similar(left_row, right_row, num_columns):
        current_group['right'].append(right_idx)

    processed_rows.add(left_idx)
    if len(current_group['right']) > 0:
      matching_rows.append(current_group)
    if len(matching_rows) >= max_matches:
      break

  return matching_rows

def cross_tab_exact_match(left_df, right_df):
  match_groups = []
  exact_groups = defaultdict(set)

  for left_index, left_row in progress_bar(left_df.iterrows(), total=len(left_df)):
    left_content = "/".join(left_row.astype(str))
    group = [left_index]

    for right_index, right_row in right_df.iterrows():
      if right_index in exact_groups['right']:
        continue

      right_content = "/".join(right_row.astype(str))
      if left_content == right_content:
        group.append(right_index)
        break

    if len(group) > 1:  # Only add groups with at least one match
      match_groups.append(group)
      exact_groups['left'].add(left_index)
      exact_groups['right'].add(right_index)

  exact_matches = {side: list(matches) for side, matches in exact_groups.items()}
  return exact_matches, match_groups

def detect_previously_matched(tracker, groups):
  # Store any pre-labeled results as matches
  left_matched, right_matched = set(), set()

  for cardset in tracker.results:
    if cardset['resolution'] == 'merge':
      left_row_id = cardset['retain'][0]
      right_row_id = cardset['retire'][0]

      groups['matches'].append({'left': left_row_id, 'right': right_row_id})
      left_matched.add(left_row_id)
      right_matched.add(right_row_id)

  return left_matched, right_matched, groups

def attach_property_details(column_properties, tab_size):
  defaults = {'month': '%b', 'week': '%a', 'date': '%Y-%m-%d', 'quarter': '%o', 'currency': '$',
              'timestamp': '%Y-%m-%dT%H:%M:%S%z', 'year': '%Y', 'time': '%H:%M:%S', 'day': '%a'}

  parsed_properties = {}
  for col_name, prop in column_properties.items():
    subtype = prop['subtype']
    supplement = {}
    if subtype in defaults:
      supplement[subtype] = defaults[subtype]

    parsed_properties[col_name] = {'col_name': col_name, 'total': tab_size, 'type': prop['datatype'],
              'subtype': subtype, 'supplement': supplement, 'potential_problem': [], 'potential_concern': False }
  return parsed_properties

def static_entity_prompt(context, labels):
  valid_cols, valid_tabs, current_tab = labels['table_info']
  intent, dax = labels['intent'], labels['dax']
  preview_md = labels.get('preview', 'N/A')
  flow_prompts = grounding_prompts[intent]
  history = context.compile_history()

  if dax in ['146', '46D', '468']:   # open-ended requests for insight, connection, fix
    prompt = flow_prompts[dax].format(history=history, valid_tabs=valid_tabs, valid_cols=valid_cols)
  elif intent == 'Detect':
    prompt = flow_prompts[dax].format(curr_tab=current_tab, history=history, valid_cols=valid_cols)
  elif dax in ['014', '14C']:
    prompt = flow_prompts[dax].format(tables=valid_tabs, columns=valid_cols, current=current_tab, history=history)
  elif dax == '58A':
    prompt = flow_prompts[dax].format(tables=valid_tabs, preview=preview_md, history=history)
  else:
    prompt = flow_prompts[dax].format(history=history, valid_tabs=valid_tabs, valid_cols=valid_cols)

  return prompt

def transfer_issues_entity_to_state(state, frame):
  issues_tab = frame.issues_entity.get('tab', '')
  issues_col = frame.issues_entity.get('col', '')

  if len(issues_tab) > 0 and len(issues_col) > 0:
    state.has_issues = True
    state.current_tab = issues_tab
    state.entities = [entity for entity in state.entities if entity['col'] != '*']

    stored = False
    for entity in state.entities:
      if entity['tab'] == issues_tab and entity['col'] == issues_col:
        stored = True
    if not stored:
      state.entities.append(frame.issues_entity)
  return state

def wrap_up_issues(flow, state):
  state.has_issues = False
  state.has_plan = False
  flow.completed = True
  return flow, state

def metric_name_finder(phrase):
  short_name, long_name = 'N/A', 'N/A'

  # Case 1: Direct match in common abbreviations
  if phrase in common_abbreviations:
    short_name, long_name = phrase, common_abbreviations[phrase]
    return short_name, long_name

  # Case 2: Match after normalization
  scrubbed = phrase.lower().replace('_', ' ')
  for acronym, expanded in common_abbreviations.items():
    if scrubbed == acronym.lower() or scrubbed == expanded.lower():
      short_name, long_name = acronym, expanded
      return short_name, long_name

  # Case 3: Attempt to infer from delimited parts
  for delimiter in [' ', '-', '_']:
    if delimiter in phrase:
      parts = phrase.split(delimiter)
      short_name = delimiter.join([part[0].upper() for part in parts])
      long_name = ' '.join(parts)
      return short_name, long_name

  # Case 4: Default handling based on length
  if len(phrase) <= 3:
    short_name = phrase.upper()
  else:
    long_name = phrase
  return short_name, long_name

def extract_partial(full_name):
  if '(' in full_name and ')' in full_name:
    temp_name = full_name[:-1]               # remove the trailing ')' from the name
    partial_name = temp_name.split('(')[1]   # remove the leading 'Intent(' from the name
  else:
    partial_name = full_name
  return partial_name
