import numpy as np
import pandas as pd
import math
from collections import defaultdict
from typing import List

from backend.components.metadata import MetaData
from backend.components.metadata.typechecks import DateTimeType, LocationType, NumberType, TextType
from backend.components.engineer import PromptEngineer

from backend.utilities.search import sample_from_series
from backend.prompts.for_metadata import *
from backend.prompts.general import subtype_descriptions, type_descriptions

class Problem(MetaData):

  def __init__(self, table_name, table_properties, level, api=None):
    super().__init__(table_properties, table_name, level, api)
    self.name = 'problem'

  def detect_issues(self, issue_df, column):
    """ Transfers the issues from the shadow table to the metadata, double checks if column contains problems
      - Unsupported types are undeniable, but mixed types are more ambiguous
      - Use the API to determine if the detected problems are actually issues
      - Returns the updated issue_df and the detected problematic rows
    """
    col_name = column.name

    # Use existing utility functions to perform API-based sanity checking
    self.exact_col_name(column)
    issue_df = self.abbreviated_content(column, issue_df)

    problematic_rows = self.detected_row_ids(issue_df, col_name, 'problem')
    self.prepared = True
    return issue_df, problematic_rows

  # -------------- detection methods ---------------
  def exact_col_name(self, column):
    """ Checks if a column name directly contains a subtype name (which would be embarrassing to miss)
    if so, use an API call to verify, and then update the subtype to that name if true"""
    datatypes_to_consider = {'id': 'unique', 'timestamp': 'datetime', 'city': 'location', 'state': 'location',
                              'currency': 'number', 'percent': 'number', 'date': 'datetime', 'time': 'datetime'}

    col_name = column.name
    properties = self.tab_properties[col_name]

    for proposed_subtype, parent in datatypes_to_consider.items():
      suspicious = False
      if properties['subtype'] != proposed_subtype:
        if proposed_subtype == 'id' and properties['col_name'].endswith('id'):
          suspicious, contiguous = True, True
        elif proposed_subtype == 'currency' and 'price' in properties['col_name'].lower():
          suspicious, contiguous = True, False
        elif proposed_subtype == 'percent' and 'rate' in properties['col_name'].lower():
          suspicious, contiguous = True, False
        elif proposed_subtype in properties['col_name'].lower():
          suspicious, contiguous = True, False

      if suspicious:
        raw_samples = sample_from_series(column, max_samples=32, sample_rate=1.0, contiguous=contiguous, strict=True)

        samples = [str(sample)[:128] for sample in raw_samples.dropna().tolist()]
        prompt = exact_col_prompt.format(column=col_name, original=properties['subtype'], proposed=proposed_subtype,
                                              orig_parent=properties['type'], prop_parent=parent, samples=samples)
        raw_output = self.api.execute(prompt)
        prediction = PromptEngineer.apply_guardrails(raw_output, 'json')
        prediction = {'answer': 'yes'}
        if prediction['answer'] == proposed_subtype:
          self.tab_properties[col_name]['subtype'] = proposed_subtype
          self.tab_properties[col_name]['type'] = parent

  def abbreviated_content(self, column, issue_df):
    """ Given a potential problem column, calculate the average length of the content. Then, if this is <= 3 characters,
    ask the model if this is a legitimate problem. Intuitively, if the problematic content is very short, TypeChecks had
    very little signal to work with, thereby triggering a false positive. As a result, it is worth double-checking. """

    col_name = column.name

    # Get mixed_type issues for this column
    mixed_type_issues = issue_df[
      (issue_df['column_name'] == col_name) &
      (issue_df['issue_type'] == 'problem') &
      (issue_df['issue_subtype'] == 'mixed_type')
    ]

    if mixed_type_issues.empty:
      return issue_df

    row_ids = mixed_type_issues['row_id'].tolist()
    content = column.iloc[row_ids]
    avg_len = content.apply(lambda x: len(str(x))).mean()

    if avg_len <= 3:
      true_type = self.tab_properties[col_name]['subtype']
      true_description = subtype_descriptions[true_type]
      true_series = column if len(column) <= 64 else column.sample(n=64, replace=False)
      true_samples = true_series.values.tolist()

      # For suspect type, we'll use the most common mixed_type issue
      suspect_type = self.tab_properties[col_name].get('potential_problem', ['unknown'])[0]
      suspect_description = subtype_descriptions.get(suspect_type, 'unknown type')
      suspect_series = content if len(content) <= 64 else content.sample(n=64, replace=False)
      suspect_samples = suspect_series.values.tolist()

      prompt = short_content_prompt.format(col_name=col_name,
                              true_type=true_type, true_desc=true_description, true_data=true_samples,
                              suspect_type=suspect_type, suspect_desc=suspect_description, suspect_data=suspect_samples)

      raw_pred = self.api.execute(prompt)
      predicted_issue = PromptEngineer.apply_guardrails(raw_pred, 'json')
      if predicted_issue and predicted_issue.get('answer') == 'no':
        # Remove the mixed_type issues for this column
        issue_df = issue_df[~(
          (issue_df['column_name'] == col_name) &
          (issue_df['issue_type'] == 'problem') &
          (issue_df['issue_subtype'] == 'mixed_type')
        )]

    return issue_df

  def get_parent_name(self, subtype):
    """ Returns the major parent type, and the names of the minor parent types """
    major_parent = 'text'  # default to text type when no other parent is found
    for parent_type in self.datatypes:
      if any(child_type.name == subtype for child_type in parent_type.subtypes):
        major_parent = parent_type.name
        break
    return major_parent

  def get_children_mapping(self, major):
    """ Returns a mapping of parent type to its children types """
    child_map = defaultdict(list)
    for parent_type in self.datatypes:

      # Since order matters, the first child substype is major
      for subtype in parent_type.subtypes:
        if subtype.name == major:
          child_map[parent_type.name].append(subtype)
      # Followed by other subtypes, which are minors
      for subtype in parent_type.subtypes:
        if subtype.name != major:
          child_map[parent_type.name].append(subtype)

    return child_map

  def detect_problems(self, col_name:str, series:pd.Series, major:str, minors:list):
    parent = self.get_parent_name(major)
    children_of = self.get_children_mapping(major)

    for row_id, value in series.items():
      type_matched = False

      # Check if the row matches a minor parent, which is a mixed datatype problem
      for parent_type in self.datatypes:
        for minor in minors:
          if minor in parent_type.children() and parent_type.name != parent and not type_matched:
            if parent_type.contains(value, self.tab_properties[col_name]):
              self.issues['mix_type'][col_name].append(row_id)
              self.parent_types[col_name].append(parent_type.name)
              type_matched = True
              break

      # Check if the row matches a minor child, then we have a mixed subtype problem
      for child_type in children_of[parent]:
        if child_type.name == major and child_type.contains(value, col_name):
          type_matched = True
          break  # It's the major subtype, so it's fine
        elif child_type.contains(value, col_name):
          self.issues['mix_subtype'][col_name].append(row_id)
          self.child_types[col_name].append(child_type.name)
          type_matched = True

      # If it doesn't match any known type, it's unsupported
      if not type_matched:
        self.issues['unsupported'][col_name].append(row_id)

  @staticmethod
  def type_to_nl(problem_type, extra_detail, count, prefix='article'):
    # Converts problem type to natural language
    if prefix == 'article':
      if count == 1:
        if problem_type == 'unsupported':
          result = "an "
        elif problem_type.startswith('mix'):
          result = "a "
      else:
        result = ""
    elif prefix == 'digit':
      result = f"{count} "
    else:
      result = ""

    if count == 1:
      if problem_type == 'unsupported':
        result += "unsupported value"
      elif problem_type == 'mix_type':
        result += "mixed data type"
      elif problem_type == 'mix_subtype':
        result += "mixed subtype"
    else:
      if problem_type == 'unsupported':
        result += "unsupported values"
      elif problem_type == 'mix_type':
        if len(extra_detail) > 0:
          result += f"rows of {extra_detail} data type"
        else:
          result += f"rows with non-standard data types"
      elif problem_type == 'mix_subtype':
        if len(extra_detail) > 0:
          result += f"rows of {extra_detail} subtype"
        else:
          result += f"rows with non-standard subtypes"

    return result