import numpy as np
import pandas as pd
import lightgbm as lgb
from tqdm import tqdm as progress_bar

from sentence_transformers import SentenceTransformer
from collections import Counter, defaultdict
from sklearn.preprocessing import OneHotEncoder
from sklearn.metrics.pairwise import cosine_similarity
from backend.modules.experts.for_nlu import BaseExpert
from backend.utilities.search import cross_tab_exact_match, cross_tab_near_match, detect_previously_matched

class DuplicateDetector(BaseExpert):

  def __init__(self):
    self.decision_tree = lgb.LGBMClassifier(verbose=-1)
    self.e5_embedder = SentenceTransformer('intfloat/e5-base-v2')
    self.tab_medians = {}
    self.one_hot_encoders = {}
    self.epsilon = 1e-6
    self.threshold = 0.6

    self.side_to_tab = {'left': '', 'right': ''}
    self.tab_to_cols = defaultdict(list)
    self.display_cols = {'left': [], 'right': []}
    self.conflict_embeddings = defaultdict(list)

  def detect(self, tracker):
    # Given two dataframes, find matching rows between the two dataframes to merge together
    groups = {'left_solo': [], 'right_solo': [], 'matches': []}
    left_matched, right_matched, groups = detect_previously_matched(tracker, groups)

    left_embeds = self.conflict_embeddings[self.side_to_tab['left']]
    right_embeds = self.conflict_embeddings[self.side_to_tab['right']]

    # Iterate through each pair of embeddings to find potential matches
    for cardset in progress_bar(tracker.conflicts, total=len(tracker.conflicts)):
      left_idx = cardset[0]['row_id']
      # Skip rows from left-tab that have already been matched
      if left_idx in left_matched: continue
      top_match = None
      current_score = 0

      # Process each row from the right-table to find the best match that passes the minimum threshold
      for right_card in cardset[1:]:
        right_idx = right_card['row_id']
        if right_idx in right_matched: continue

        left_embed, right_embed = left_embeds[left_idx], right_embeds[right_idx]
        feature_vector = np.abs(left_embed - right_embed)
        match_score = self.decision_tree.predict_proba([feature_vector])[0, 1]
        if match_score > current_score and match_score > self.threshold:
          top_match = right_idx
          current_score = match_score

      if top_match:
        groups['matches'].append({'left': left_idx, 'right': top_match})
        left_matched.add(left_idx)
        right_matched.add(top_match)

    groups['left_solo'] = [lid for lid in range(len(left_embeds)) if lid not in left_matched]
    groups['right_solo'] = [rid for rid in range(len(right_embeds)) if rid not in right_matched]
    print("Breakdown of matches:", {key: len(vals) for key, vals in groups.items()})
    return groups

  def reset(self):
    self.conflict_embeddings = defaultdict(list)
    self.side_to_tab = {'left': '', 'right': ''}
    self.tab_to_cols = defaultdict(list)
    self.display_cols = {'left': [], 'right': []}

  def train(self, conflict_sets, positives, negatives, cross):
    # Given a list of positive and negative examples, train the Decision Tree
    left_embeds = self.conflict_embeddings[self.side_to_tab['left']]
    right_embeds = self.conflict_embeddings[self.side_to_tab['right']] if cross else left_embeds

    X, y = [], []
    for pos in positives:
      feature_vector = np.abs(left_embeds[pos[0]] - right_embeds[pos[1]])
      X.append(feature_vector)
      y.append(1)  # Label for duplicates
    for neg in negatives:
      feature_vector = np.abs(left_embeds[neg[0]] - right_embeds[neg[1]])
      X.append(feature_vector)
      y.append(0)  # Label for non-duplicates

    self.decision_tree.set_params(min_data_in_leaf=5)
    self.decision_tree.set_params(min_data_in_bin=2)
    self.decision_tree.fit(X, y)
    # if len(y) <= 10: # only the most recent batch, then use the init, see ticket [0981]
    # self.decision_tree.fit(X, y, init_model=self.decision_tree)
    return self.calculate_confidence(conflict_sets, left_embeds, right_embeds)

  def calculate_confidence(self, conflict_sets, left_embeds, right_embeds):
    if len(conflict_sets) <= 3:   # If there are very few conflict cardsets, we are very confident
      return 0.99                        # Also helps to prevent division by zero issues

    prediction_confidence = 0
    for cardset in conflict_sets:
      left_id, right_id = cardset[0]['row_id'], cardset[1]['row_id']
      feature_vector = np.abs(left_embeds[left_id] - right_embeds[right_id])

      prob = self.decision_tree.predict_proba([feature_vector])[0, 1]  # Probability of being a duplicate
      distance = 2 * abs(prob - 0.5)
      if distance > 0.5:      # log scaling for large distances, calibrates confidence to a max of 0.95
        prediction_confidence += np.log(distance + self.epsilon) / 1.54 + 0.95
      else:                   # linear scaling for small distances
        prediction_confidence += distance

    confidence_score = prediction_confidence / len(conflict_sets)
    return confidence_score

  def encode(self, table_df, tab_name, tab_schema):
    # Given a dataframe, store all the rows as conflict embeddings
    relevant_col_schema = {col: tab_schema[col] for col in self.tab_to_cols[tab_name]}
    col_types = self.prepare_for_encoding(table_df, relevant_col_schema)
    current_time = pd.Timestamp.now()

    column_embeddings = []
    for col, col_type in col_types.items():
      print(f"Encoding column {col} of type {col_type}")
      if col_type == 'text':
        emb = self.encode_text(table_df, col)
      elif col_type == 'number':
        emb = self.encode_number(table_df, col)
      elif col_type == 'datetime':
        emb = self.encode_datetime(table_df, col, current_time)
      elif col_type == 'category':
        emb = self.encode_category(table_df, col)
      elif col_type == 'boolean':
        emb = np.array([[1] if row else [0] for row in table_df[col]])
      else:
        emb = []
      if len(emb) > 0:
        column_embeddings.append(emb)

    table_embedding = np.concatenate(column_embeddings, axis=1)
    self.conflict_embeddings[tab_name] = table_embedding

  def encode_text(self, table_df, col):
    # Get embedding for text using E5-base
    column = table_df[col].fillna('').astype(str)
    # expected format prepends 'query: ' to each text
    prepared_batch = [f"query: {text}" for text in column]
    col_embedding = self.e5_embedder.encode(prepared_batch, normalize_embeddings=True)
    return col_embedding

  def encode_number(self, table_df, col):
    # Normalize numerical data between roughly -1 and 1
    number_encodings = []
    for row in table_df[col]:
      val = row / (self.tab_medians[col] * 2)
      number_encodings.append(val)
    col_embedding = np.array(number_encodings)
    return col_embedding

  def encode_datetime(self, table_df, col, current_time):
    datetime_encodings = []
    for row in table_df[col]:
      time_diff = row - current_time
      normalized_time = abs(time_diff.days)  # Normalize to days
      standard_days = round((row.timestamp() - 946684800.0) / (3600 * 24), 3)  # Normalize to seconds
      datetime_encodings.append([normalized_time, standard_days])
    col_embedding = np.array(datetime_encodings)
    return col_embedding

  def encode_category(self, table_df, col):
    encoder = self.one_hot_encoders[col]
    cat_encodings = []
    for row in table_df[col]:
      cat_embedding = encoder.transform([[row]]).flatten()
      cat_encodings.append(cat_embedding)
    col_embedding = np.array(cat_encodings)
    return col_embedding

  def prepare_for_encoding(self, table_df, raw_col_schema):
    col_types = {}

    for col, metadata in raw_col_schema.items():
      if metadata['type'] == 'number':
        if col not in self.tab_medians:
          cand_median = table_df[col].median()
          self.tab_medians[col] = self.epsilon if cand_median == 0 else cand_median
        col_types[col] = 'number'

      elif metadata['subtype'] == 'category' or metadata['subtype'] == 'status':
        if col not in self.one_hot_encoders:
          encoder = OneHotEncoder(sparse=False, handle_unknown='ignore')
          encoder.fit(table_df[[col]])
          self.one_hot_encoders[col] = encoder
        col_types[col] = 'category'

      elif metadata['subtype'] in ['boolean', 'id']:
        col_types[col] = metadata['subtype']

      elif metadata['type'] == 'datetime':
        samples = table_df[col].dropna().sample(n=min(128, len(table_df[col])), replace=False)
        if samples.nunique() <= 16:
          # TODO: add a prompt to help sort the values into ordered categories
          self.one_hot_encoders[col] = OneHotEncoder(sparse=False, handle_unknown='ignore')
          self.one_hot_encoders[col].fit(table_df[col])
        else:
          now_stamp = pd.Timestamp.now()
          behaves_like_number = 0
          for sample in samples:
            try:
              distance = (sample - now_stamp).days
              behaves_like_number += 1
            except TypeError:
              pass
          ratio = behaves_like_number / len(samples)
          col_types[col] = 'datetime' if ratio > 0.8 else 'text'

      else:
        col_types[col] = 'text'

    return col_types

  def set_tab_col(self, entities, tables):
    # Stores table_name, col_names to the appropriate sides based on a list of entities
    for entity in entities:
      self.tab_to_cols[entity['tab']].append(entity['col'])
    tab_names = list(self.tab_to_cols.keys())

    if len(tab_names) == 1:
      self.side_to_tab['left'] = tab_names[0]
      self.side_to_tab['right'] = tab_names[0]
    else:
      tab1, tab2 = tab_names[:2]
      length1, length2 = len(tables[tab1]), len(tables[tab2])
      if length1 <= length2:
        shorter, longer = tab1, tab2
      else:
        shorter, longer = tab2, tab1

      self.side_to_tab['left'] = shorter
      self.side_to_tab['right'] = longer

  def add_display_columns(self, col_options, tab_name, tab_schema, side):
    source_cols = self.tab_to_cols[tab_name]
    support_cols = []
    for col_name in col_options:
      if tab_schema[col_name]['subtype'] != 'id' and col_name not in source_cols:
        support_cols.append(col_name)

    joint_cols = set(source_cols) | set(support_cols)
    if len(joint_cols) > 5:
      if len(source_cols) < 5:
        amount_to_fill = 5 - len(source_cols)
        remaining_cols = np.random.choice(support_cols, size=amount_to_fill, replace=False)
        joint_cols = set(source_cols) | set(remaining_cols)
      else:
        joint_cols = set(source_cols)

    # Store display columns in sorted order
    for col_name in col_options:
      if col_name in joint_cols:
        self.display_cols[side].append(col_name)

  @staticmethod
  def compute_dataset_threshold(similarities, sample_size=16384):
    flattened_scores = similarities.flatten()
    num_elements = flattened_scores.size

    if num_elements < sample_size:
      samples = flattened_scores
    else:
      sampled_indices = np.random.choice(num_elements, sample_size, replace=False)
      samples = flattened_scores[sampled_indices]

    max_similarity = samples.max()
    interval = np.percentile(samples, 70) - np.percentile(samples, 65)
    interval = max(interval, 0.001)
    threshold = max_similarity - interval
    return threshold, interval

  def single_tab_duplicates(self, table_df, tab_name, tab_schema):
    # Mark potential duplicates based on target columns
    source_cols = self.tab_to_cols[tab_name]
    potential_dupes = table_df.duplicated(subset=source_cols, keep=False)
    potential_df = table_df[potential_dupes].copy()
    potential_df['group_id'] = potential_df.groupby(source_cols).ngroup()

    # Classify each group and convert into a cardset
    autofixes, conflicts = [], []
    for _, group in potential_df.groupby('group_id'):
      cardset = self.create_cards(group.index.tolist())
      if self.single_tab_merge(group, table_df.columns, source_cols, tab_schema):
        retained_ids = [cardset[0]['row_id']]
        retired_ids = [card['row_id'] for card in cardset[1:]]
        autofix_result = {'resolution': 'merge', 'retain': retained_ids, 'retire': retired_ids, 'reviewed': False}
        autofixes.append(autofix_result)
      else:
        conflicts.append(cardset)

    print(f"Found {len(autofixes)} autofix results and {len(conflicts)} conflict cardsets")
    return autofixes, conflicts

  def single_tab_merge(self, cardset, all_columns, target_cols, tab_schema):
    # Cardsets can obviously be merged if all non-target columns are the same, or they are null
    for column in all_columns:
      if column in target_cols:
        continue
      if tab_schema[column]['subtype'] == 'id':
        continue
      meaningful_values = cardset[column].dropna().unique()
      if len(meaningful_values) > 1:
        return False
    return True

  def cross_tab_duplicates(self, tables, tag_type, max_matches=64):
    # Finds up to total pairs of rows that match exactly or are embarrassingly similar
    # tables is a dict with keys of 'left' and 'right', each stores the full table dataframe
    left_tab_name = self.side_to_tab['left']
    relevant_left_cols = self.tab_to_cols[left_tab_name]
    left_df = tables[left_tab_name][relevant_left_cols]

    right_tab_name = self.side_to_tab['right']
    relevant_right_cols = self.tab_to_cols[right_tab_name]
    right_df = tables[right_tab_name][relevant_right_cols]

    # Find exact matches and filter those out from the tables
    exact_matches, match_groups = cross_tab_exact_match(left_df, right_df)
    left_matrix = left_df[~np.isin(np.arange(len(left_df)), exact_matches['left'])]
    right_matrix = right_df[~np.isin(np.arange(len(right_df)), exact_matches['right'])]
    # fuzzy_matches = self.cross_tab_fuzzy_match(left_matrix, right_matrix, exact_matches, max_matches)

    if tag_type == 'date':
      matching_rows = []   # no fuzzy matching for date columns, must pre-process to exact matches
    else:
      matching_rows = cross_tab_near_match(left_matrix, right_matrix, max_matches)

    conflicts = []
    for overlap_group in matching_rows:
      left_cards = self.create_cards(overlap_group['left'], side='left')
      right_cards = self.create_cards(overlap_group['right'], side='right')
      cross_tab_cardset = left_cards + right_cards
      conflicts.append(cross_tab_cardset)

    # Convert exact matches directly into results format (skipping the cardset format)
    autofixes = [{'resolution': 'merge', 'retain': [retain], 'retire': [retire]} for retain, retire in match_groups]
    print(f"Found {len(autofixes)} autofix results and {len(conflicts)} conflicts cardsets")
    return autofixes, conflicts

  def cross_tab_fuzzy_match(self, left_matrix, right_matrix, exact_matches, max_matches, top_k=3):
    # Finds up to total pairs of similar rows from two tables using embeddings for fuzzy matching
    similarities = cosine_similarity(left_matrix, right_matrix) # shape: len(left_embeds) x len(right_embeds)
    threshold, interval = self.compute_dataset_threshold(similarities)
    max_matches = min([max_matches, len(left_matrix), len(right_matrix)])

    found = set()
    conflicts = []
    while len(conflicts) < max_matches:

      for left_index in range(len(left_matrix)):
        if left_index in exact_matches or left_index in found: continue

        left_sim_scores = similarities[left_index]
        valid_matches = np.where(left_sim_scores >= threshold)[0]

        if valid_matches.size > 0:
          # Find the top_k right embeddings by index
          valid_scores = left_sim_scores[valid_matches]
          found.add(left_index)
          score_indexes = np.argsort(valid_scores)[-top_k:]  # only consider the top 3 neighbors
          right_indexes = [int(valid_matches[x]) for x in score_indexes]

          left_cards = self.create_cards([left_index], side='left')
          right_cards = self.create_cards(right_indexes, side='right')
          cross_tab_cardset = left_cards + right_cards
          conflicts.append(cross_tab_cardset)

        if len(conflicts) >= max_matches:
          break

      print("threshold", threshold, 'interval', interval)
      threshold -= interval

    self.threshold = threshold   # Set threshold for cross_tab_duplicates
    left_matches, right_matches = list(exact_matches['left']), list(exact_matches['right'])
    autofixes = [{'resolution':'merge', 'retain':[lm, rm], 'retire':[]} for lm, rm in zip(left_matches, right_matches)]
    print(f"Found {len(autofixes)} autofix results and {len(conflicts)} conflicts cardsets")
    return autofixes, conflicts

  def create_cards(self, cardset_ids, side='left'):
    tab_name = self.side_to_tab[side]
    column_names = self.display_cols[side]

    cardset = []
    for row_index in cardset_ids:
      card_info = {'side': side, 'row_id': row_index, 'table': tab_name, 'columns': column_names}
      cardset.append(card_info)
    return cardset
