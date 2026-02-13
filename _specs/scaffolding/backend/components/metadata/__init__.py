from backend.utilities.search import select_rows_to_display, select_columns_to_display
from collections import Counter
from typing import List
import pandas as pd

class MetaData(object):

  def __init__(self, tab_properties, table_name, level, api):
    self.level = level
    self.api = api
    self.tab_name = table_name
    self.tab_properties = tab_properties
    self.prepared = False

    self.unique_cols = []
    self.datetime_cols = []
    self.location_cols = []
    self.number_cols = []
    self.text_cols = []
    self.term_cols = []

    for column_name, properties in self.tab_properties.items():
      if properties['type'] == 'unique':
        self.unique_cols.append(column_name)
      elif properties['type'] == 'datetime':
        self.datetime_cols.append(column_name)
      elif properties['type'] == 'location':
        self.location_cols.append(column_name)
      elif properties['type'] == 'number':
        self.number_cols.append(column_name)
      elif properties['type'] == 'text':
        self.text_cols.append(column_name)
      if properties['subtype'] in ['status', 'category']:
        self.term_cols.append(column_name)

  @staticmethod
  def select_data(df, columns, rows, compare=False):
    selected_rows = select_rows_to_display(df, rows) if compare else rows
    selected_cols = select_columns_to_display(df, columns) if compare else columns
    data_to_display = df.loc[selected_rows][selected_cols]
    return data_to_display

  def issues_exist(self, issues, columns, issue_type='') -> bool:
    # Check if there are any issues detected in the specified columns.
    if not self.prepared or issues.empty:
      return False

    # Filter by columns
    column_issues = issues[issues['column_name'].isin(columns)]
    if column_issues.empty:
      return False

    # Filter by issue type if specified
    if issue_type:
      column_issues = column_issues[column_issues['issue_type'] == issue_type]

    return not column_issues.empty

  @staticmethod
  def remove_issues(issue_df, col_name:str, for_removal:list, issue_type:str=''):
    # Remove specific issues from the dataframe
    if issue_df.empty or len(for_removal) == 0:
      return issue_df
    col_mask = issue_df['column_name'] == col_name

    if '*' in for_removal:
      row_mask = pd.Series(True, index=issue_df.index)
    else:
      row_mask = issue_df['row_id'].isin(for_removal)

    if issue_type:
      # Remove specific issues by row_id and issue_type
      removal_mask = col_mask & row_mask & (issue_df['issue_type'] == issue_type)
    else:
      # Remove all issues for the specified column and row_ids
      removal_mask = col_mask & row_mask

    return issue_df[~removal_mask]

  # -------------- access methods ---------------
  @staticmethod
  def detected_row_ids(issues, col_name:str, issue_type:str='') -> List[str]:
    # return the row ids of the detected issues in a specific column
    if issues.empty: return []

    filtered_issues = issues[issues['column_name'] == col_name]
    if issue_type:
      filtered_issues = filtered_issues[filtered_issues['issue_type'] == issue_type]
    return filtered_issues['row_id'].unique().tolist()
  
  @staticmethod
  def detected_issue_types(issues, col_name:str) -> List[str]:
    # return the unique issue types detected in a specific column
    if issues.empty: return []

    filtered_issues = issues[issues['column_name'] == col_name]
    return filtered_issues['issue_type'].unique().tolist()

  @staticmethod
  def num_issue_rows(issues, col_name:str='', issue_type:str='', subtype:str='') -> int:
    # return the number of unique rows with issues detected
    if issues.empty: return 0

    filtered_issues = issues
    if col_name:
      filtered_issues = filtered_issues[filtered_issues['column_name'] == col_name]
    if issue_type:
      filtered_issues = filtered_issues[filtered_issues['issue_type'] == issue_type]
    if subtype:
      filtered_issues = filtered_issues[filtered_issues['issue_subtype'] == subtype]

    return filtered_issues['row_id'].nunique()