import re
import json
import numpy as np
import pandas as pd
from collections import defaultdict, Counter
from typing import List
from fuzzywuzzy import fuzz

from backend.utilities.search import normalize_term
from backend.components.metadata import MetaData
from backend.components.engineer import PromptEngineer
from backend.prompts.general import similar_terms_prompt
from backend.assets.ontology import typo_corpus

class Typo(MetaData):
  def __init__(self, table_name, table_properties, level, api=None):
    super().__init__(table_properties, table_name, level, api)
    self.name = 'typo'
    self.groups_by_column = {}

  def detect_issues(self, issue_df, column):
    """ Look for typos in the columm, which can be one of two types:
    misspelled: the word is not in the dictionary, a classic typo
    replacement: word or phrase exists, but is incorrect based on context
    """
    col_name = column.name
    new_issues = []

    if col_name in self.text_cols or col_name in self.term_cols:
      misspelled_issues = self.detect_misspelled(column)
      new_issues.extend(misspelled_issues)

      self.detect_syntactic_similarity(column)
      if col_name in self.term_cols:
        self.detect_semantic_similarity(column)

      # Merge clusters and groups to get replacement issues
      replacement_issues = self.merge_clusters_and_groups(column)
      new_issues.extend(replacement_issues)

    if new_issues:
      new_issues_df = pd.DataFrame(new_issues)
      issue_df = pd.concat([issue_df, new_issues_df], ignore_index=True)

    typo_rows = self.detected_row_ids(issue_df, col_name, 'typo')
    self.prepared = True
    return issue_df, typo_rows

  # -------------- identify typos ----------------
  def detect_misspelled(self, column):
    # use a corpus of commonly used words to identify misspelled terms
    term_lookup = self.prepare_term_lookup()
    misspelled_issues = []
    col_name = column.name

    for row_id, row_val in column.items():
      if not isinstance(row_val, str): continue
      if len(row_val) > 128: continue

      if len(row_val.split()) > 1:
        for term in row_val.split():
          if term in term_lookup.keys():
            correct_term = term_lookup[term]
            misspelled_issues.append({'row_id': row_id, 'column_name': col_name, 'original_value': row_val,
              'issue_type': 'typo', 'issue_subtype': 'misspelled', 'revised_term': correct_term })
            break

      elif row_val in term_lookup.keys():
        correct_term = term_lookup[row_val]
        misspelled_issues.append({ 'row_id': row_id, 'column_name': col_name, 'original_value': row_val,
          'issue_type': 'typo', 'issue_subtype': 'misspelled', 'revised_term': correct_term })

    return misspelled_issues

  def prepare_term_lookup(self):
    term_lookup = {}
    for domain, common_typos in typo_corpus.items():
      for correct, incorrect in common_typos.items():
        for term in incorrect:
          term_lookup[term] = correct
    return term_lookup

  def detect_syntactic_similarity(self, column):
    """ For each column, collect candidate terms to store within clusters.
    These clusters have the normalized term as the key rather than the canonical term. """
    similarity_threshold = {'low': 70, 'medium': 80, 'high': 90}
    col_name = column.name

    # Initialize clusters_by_column if not exists
    if not hasattr(self, 'clusters_by_column'):
      self.clusters_by_column = {}

    if column.nunique() > 128: return
    column_subtype = self.tab_properties[col_name]['subtype']
    if column_subtype in ['email', 'phone', 'name']: return

    unique_terms = column.unique()
    col_cluster = defaultdict(set)    # {normalized_term: [similar_terms]}
    token_groups = []

    # Group similar terms with fuzzywuzzy based on character overlap
    for raw_term in unique_terms:
      if not isinstance(raw_term, str): continue
      normalized, current_tokens = normalize_term(raw_term)
      if len(normalized) > 128: continue
      token_groups.append((normalized, current_tokens, raw_term))

      found = False
      for key in col_cluster.keys():
        if fuzz.ratio(normalized, key) > similarity_threshold[self.level]:
          col_cluster[key].add(raw_term)
          found = True
          break
      if not found:
        col_cluster[normalized].add(raw_term)  # store the original term

    # Group similar terms based on token overlap
    for i in range(len(token_groups) - 1):
      norm_term1, token_group1, raw_term = token_groups[i]
      # only consider the remaining terms
      for j in range(i + 1, len(token_groups)):
        norm_term2, token_group2, _ = token_groups[j]
        if self.token_group_overlap(token_group1, token_group2):
          col_cluster[norm_term2].add(raw_term)

    # Remove clusters with only one term and convert the set to a list
    final_clusters = {}
    for key in list(col_cluster.keys()):
      cluster_set = col_cluster[key]
      if len(cluster_set) > 1:
        final_clusters[key] = list(cluster_set)
    self.clusters_by_column[col_name] = final_clusters

  def token_group_overlap(self, group1, group2):
    if len(group1) < len(group2):
      shorter, longer = group1, group2
    else:
      shorter, longer = group2, group1

    # trim tokens that are too short
    shorter = [token for token in shorter if len(token) >= 3]
    # find the number of tokens that overlap
    matches = [token for token in shorter if token in longer]
    num_matches = len(matches)

    # if all tokens match and this makes up at least half of the larger group
    overlap = False
    if num_matches > 0 and num_matches == len(shorter):
      if (float(num_matches) / len(longer)) >= 0.5:
        overlap = True
    return overlap

  def detect_semantic_similarity(self, column):
    """ Use API to check for semantically related terms that should be merged, going beyond spelling errors
    First key is col_name, second key is chosen term, values are a list of sim_terms  """
    col_name = column.name
    # only check columns with a 2 < n =< 16 of unique terms (ie. status or category subtype)
    unique_terms = column.dropna().unique()
    if len(unique_terms) <= 2 or len(unique_terms) > 16: return

    unique_term_str = ', '.join(unique_terms)
    prompt = similar_terms_prompt.format(col_name=col_name, unique_terms=unique_term_str)
    prediction = PromptEngineer.apply_guardrails(self.api.execute(prompt), 'json')

    if prediction == 'error' or not isinstance(prediction, dict):
      print(f"Error finding similar terms for {col_name}")
    else:
      self.groups_by_column[col_name] = prediction

  def merge_clusters_and_groups(self, column):
    """ Since the clusters have normalized terms as the key, we first need to extract the canonical terms
    from the values-list of each cluster. Then, we can merge the clusters with the groups. """
    replacement_issues = []
    col_name = column.name

    if col_name not in getattr(self, 'clusters_by_column', {}):
      return replacement_issues

    cluster = self.clusters_by_column[col_name]
    group = getattr(self, 'groups_by_column', {}).get(col_name, {})

    # assign each cluster to a chosen term
    for terms_list in cluster.values():
      match = False
      for chosen, candidates in group.items():
        if any(term in candidates for term in terms_list):
          match = True  # combine the terms into the existing group
          group[chosen].extend(terms_list)
          break
      if not match:  # create a new group and assign the first term as the chosen term
        group[terms_list[0]] = terms_list

    # deduplicate the similar terms within each group
    for chosen, similar_terms in group.items():
      group[chosen] = list(set(similar_terms))

    # build reverse mapping from similar_terms to chosen_term
    reverse_mapping = {}
    for chosen, similar_terms in group.items():
      for sim_term in similar_terms:   # duplicate terms will automatically get collapsed to a single chosen
        reverse_mapping[sim_term] = chosen

    # Find replacement typos and create issues
    for row_id, row_val in column.items():
      if row_val in reverse_mapping.keys():
        chosen_term = reverse_mapping[row_val]
        replacement_issues.append({
          'row_id': row_id,
          'column_name': col_name,
          'original_value': row_val,
          'issue_type': 'typo',
          'issue_subtype': 'replacement',
          'revised_term': chosen_term
        })

    return replacement_issues

  def print_to_command_line(self, concerns, itype, table):
    issue_rows = []
    for col_issues in concerns.values():
      issue_rows.extend(col_issues)
    print(f"{len(issue_rows)} {itype} found in {self.table_name}")

    if issue_rows:
      for grouping in issue_rows:
        print(grouping)

  def naive_column_assignment(self, df):
    # determine the column types of the dataframe
    numeric_cols, textual_cols, date_cols = [], [], []
    index_keywords = [r'\bindex\b', r'_id$',
                      r'\bid$']  # regex patterns to match 'id' as a standalone word or at the end of a word

    for column in df.columns:
      if any(re.search(keyword, column, re.I) for keyword in index_keywords):
        continue
      if df[column].dtypes == np.object:
        samples = df[column].sample(1000) if len(df[column]) > 1000 else df[column]
        textual_cols.append(column)
      else:
        textual_cols.append(column)

    return numeric_cols, textual_cols, date_cols

  @staticmethod
  def type_to_nl(count, prefix='article'):
    # Converts a group of similar terms to natural language
    if prefix == 'article':
      result = "a " if count == 1 else ""
    elif prefix == 'digit':
      result = f"{count} "
    else:
      result = ""

    result += "group " if count == 1 else "groups "
    result += "of similar terms"
    return result