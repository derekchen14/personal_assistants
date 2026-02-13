import random
import numpy as np
import pandas as pd
import re

from collections import Counter, defaultdict
from backend.modules.experts.for_nlu import BaseExpert

class IssueTracker(BaseExpert):
  """ Card (dict) - a row in the table with keys:
    * row_id (int) - the row id in the original column
    * value (str) - the original value before any revisions
  Once they are modified, each card may have additional keys:
    * revision (str) - the current value after any revisions
    * retain (list) - cards to keep
    * retire (list) - cards to remove
    * resolution (str) - the action to take, which is one of: merge, separate, back
    * reviewed (bool) - whether the result has been reviewed by the user
    * revised (bool) - whether we changed the row value, or if it unresolvable instead
  """
  def __init__(self, batch_size=10):
    self.results = []      # each result is a dict with keys: retain, retire, resolution, etc.
    self.conflicts = []    # each conflict is a dict with keys: row_id, value
    self.aligned = set()   # set of strings that represent the desired output format
    
    self.batch_size = batch_size  # number of cards to review in each batch
    self.batch_number = 0
    self.cardset_index = 0        # index of the current cardset within the batch
    self.epsilon = 1e-6

    self.num_issues = -1   # number of issues to resolve at the start
    self.confidence = 0.0
    self.side_to_tab = {'left': '', 'right': ''}
    self.tab_to_cols = defaultdict(list)

  def increment_cardset(self, active_conflicts):
    self.cardset_index += 1
    num_reviewed = len(active_conflicts)
    self.conflicts = self.conflicts[num_reviewed:]

  def increment_batch(self, active_conflicts=None):
    self.batch_number += 1
    self.cardset_index = 0
    if active_conflicts is not None:
      self.conflicts = active_conflicts

    num_remaining = self.num_conflicts()
    print(f"Batch {self.batch_number}: Resolved {len(self.results)} conflicts, "
          f"{sum(1 for res in self.results if not res['revised'])} unresolvable, {num_remaining} remaining.")
    return num_remaining

  def add_aligned_values(self, aligned_values, max_samples=32):
    self.aligned.update(aligned_values)
    if len(self.aligned) > max_samples:
      self.aligned = set(list(self.aligned)[:max_samples])

  def sample_conflicts(self, sample_size=10, as_string=False):
    """ Finds conflicts to resolve, places them at the start of the tracker list, and then returns the batch
    TODO: sample cardset with highest entropy to maximize information gain, rather than random sampling """
    if len(self.conflicts) < sample_size:
      sampled_cards = self.conflicts
    else:
      sampled_cards = random.sample(self.conflicts, sample_size)

    if as_string:
      card_strings = []
      for card in sampled_cards:
        current_value = card.get('revision', card['value'])
        # convert the conflicts to strings with surrounding quotes
        card_strings.append(f"'{current_value}'")
      sampled_cards = '\n'.join(card_strings)
    else:
      # re-order the conflicts so that the sampled cards are at the front
      remaining_cards = [card for card in self.conflicts if card not in sampled_cards]
      self.conflicts = sampled_cards + remaining_cards

    return sampled_cards

  def labeled_cardsets(self):
    positive_cardsets, negative_cardsets = [], []
    for result in self.results:
      retain_id = result['retain'][0]

      if result['resolution'] == 'merge':
        for retire_id in result['retire']:
          pair = (retain_id, retire_id)
          positive_cardsets.append(pair)

      elif result['resolution'] == 'separate':
        for other_id in result['retain'][1:]:
          pair = (retain_id, other_id)
          negative_cardsets.append(pair)

    return positive_cardsets, negative_cardsets

  def combine_cards_action(self, frame):
    if len(frame.active_conflicts) > 0:

      if len(self.results) > 0 and self.results[-1]['resolution'] == 'back':
        self.results = self.results[:-2]  # remove the last two cardsets
        self.cardset_index -= 1
      else:  # either to kickstart the process or to move forward to the next cardset
        self.cardset_index += 1

    frame.properties['cardset_index'] = self.cardset_index - 1
    return frame

  def still_resolving(self) -> bool:
    not_done_with_batch = self.cardset_index < self.batch_size
    going_backward = self.results[-1]['resolution'] == 'back'
    return not_done_with_batch or going_backward
  
  def forward_resolution(self) -> bool:
    positive_results = len(self.results) > 0
    going_forward = self.results[-1]['resolution'] != 'back'
    return positive_results and going_forward

  def still_empty(self) -> bool:
    total_count = len(self.conflicts) + len(self.results)
    return total_count == 0

  def store_cardsets(self, autofixes, conflicts):
    self.results.extend(autofixes)
    self.conflicts.extend(conflicts)

  def apply_mask(self, mask_str, table_df, relevant_cols=[]):
    extra_context = {'table_df': table_df, 'pd': pd, 'np': np, 're': re}
    exec(f"mask = ({mask_str})", extra_context)
    row_mask = extra_context['mask']

    if len(relevant_cols) > 0:
      filtered_df = table_df.loc[row_mask, relevant_cols]
    else:
      filtered_df = table_df.loc[row_mask]
    return filtered_df, row_mask

  def num_conflicts(self) -> int:
    return len(self.conflicts)

  def has_conflicts(self) -> bool:
    return len(self.conflicts) > 0

  def reset(self, new_conflicts=[]):
    self.results = []
    self.issues = []
    self.aligned = set()

    self.batch_number = 0
    self.cardset_index = 0
    self.confidence = 0.0

    if len(new_conflicts) > 0:
      self.conflicts = new_conflicts
      self.num_issues = len(new_conflicts)
    else:
      self.conflicts = []
      self.num_issues = -1