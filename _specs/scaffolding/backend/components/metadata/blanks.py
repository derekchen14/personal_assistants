import numpy as np
import pandas as pd

from backend.components.metadata import MetaData
from backend.components.metadata.typechecks import NullSubtype, DefaultSubtype, MissingSubtype
from backend.prompts.for_metadata import *
from backend.components.engineer import PromptEngineer

class Blank(MetaData):

  def __init__(self, table_name, table_properties, level, api=None):
    super().__init__(table_properties, table_name, level, api)
    self.name = 'blank'
    self.subtypes = [NullSubtype(), DefaultSubtype(), MissingSubtype()]

  def detect_issues(self, issue_df, column):
    """ Transfers the issues from the shadow table to the metadata, double checks if column contains blanks
      - True nulls are undeniable, but missing and default values are more ambiguous
      - Use the API to determine if the detected blanks are actually issues
      - Returns the updated issue_df and the detected blank rows
    """
    # Get current missing and default issues for this column
    col_name = column.name
    missing_issues = issue_df[(issue_df['column_name'] == col_name) &
                             (issue_df['issue_subtype'] == 'missing')]
    default_issues = issue_df[(issue_df['column_name'] == col_name) &
                             (issue_df['issue_subtype'] == 'default')]

    # Extract the detected terms from the issues
    missing_rows = missing_issues['row_id'].tolist() if not missing_issues.empty else []
    default_rows = default_issues['row_id'].tolist() if not default_issues.empty else []

    # Use API to validate the detected blanks if we have any issues
    if missing_rows or default_rows:
      # Build column data summary similar to sanity_check_blanks
      blanks_column = column.astype('string').fillna('<N/A>')
      occurrence_counts = blanks_column.value_counts()

      # Get unique blank values from the detected issues
      unique_blanks = set()
      if missing_rows:
        unique_blanks.update([blanks_column.iloc[row_id] for row_id in missing_rows])
      if default_rows:
        unique_blanks.update([blanks_column.iloc[row_id] for row_id in default_rows])

      # Build sample data display
      lines = []
      for value, count in occurrence_counts.items():
        if len(value) > 128:
          value = value[:128] + " ..."
        sample_line = f"{value} - {count} instance"
        if count > 1:
          sample_line += "s"
        if value in unique_blanks:
          sample_line += " <--"
        lines.append(sample_line)
        if len(lines) >= 8:
          break

      if len(occurrence_counts) > 8:
        num_remaining = len(occurrence_counts) - 8
        lines.append(f"({num_remaining} other unique values ...)")

      # Create prompt for API validation
      prompt = detect_blank_prompt.format(column=col_name, samples='\n'.join(lines),
        missing_terms=', '.join([str(blanks_column.iloc[row_id]) for row_id in missing_rows[:10]]),
        default_terms=', '.join([str(blanks_column.iloc[row_id]) for row_id in default_rows[:10]])
      )
      raw_output = self.api.execute(prompt)
      prediction = PromptEngineer.apply_guardrails(raw_output, 'json')
      new_missing_terms = prediction.get('missing_terms', [])
      new_default_terms = prediction.get('default_terms', [])

      if not prediction['accept'] and len(new_missing_terms) > 0 or len(new_default_terms) > 0:
        # Remove existing missing/default issues for this column
        issue_df = issue_df[~((issue_df['column_name'] == col_name) &
                             (issue_df['issue_subtype'].isin(['missing', 'default'])))]
        new_issues = []
        for idx, value in enumerate(column):
          if pd.isna(value) or str(value).strip() in new_missing_terms:
            new_issues.append({ 'row_id': idx, 'column_name': col_name, 'original_value': value,
              'issue_type': 'blank', 'issue_subtype': 'missing'
            })
          elif str(value).strip() in new_default_terms:
            new_issues.append({'row_id': idx, 'column_name': col_name, 'original_value': value,
              'issue_type': 'blank', 'issue_subtype': 'default'
            })

        new_issues_df = pd.DataFrame(new_issues)
        issue_df = pd.concat([issue_df, new_issues_df], ignore_index=True)

    blank_rows = self.detected_row_ids(issue_df, col_name, 'blank')
    self.prepared = True
    return issue_df, blank_rows
    
  @staticmethod
  def type_to_nl(blank_type, count, prefix='article'):
    # Converts blank type to natural language
    if prefix == 'article':
      result = "a " if count == 1 else ""
    elif prefix == 'digit':
      result = f"{count} "
    else:
      result = ""

    result += f"{blank_type} value" if count == 1 else f"{blank_type} values"
    return result