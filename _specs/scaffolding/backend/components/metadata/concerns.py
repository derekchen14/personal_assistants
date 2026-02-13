import re
import pandas as pd
import numpy as np
from collections import defaultdict, Counter

from sklearn.ensemble import IsolationForest
from scipy.stats import zscore
from backend.assets.ontology import default_tokens, missing_tokens

from backend.utilities.search import sample_from_series, convert_to_date
from backend.components.metadata import MetaData

class Concern(MetaData):
  def __init__(self, table_name, table_properties, level, api=None):
    super().__init__(table_properties, table_name, level, api)
    self.name = 'concern'

  def detect_issues(self, issue_df, column):
    """ Use the existing functions to detect concerns """
    col_name = column.name

    new_issues = []
    if col_name in self.number_cols:
      outliers = self.detect_outliers(column, col_name)
      for row_id in outliers:
        new_issues.append({'row_id': row_id, 'original_value': column.iloc[row_id], 'issue_subtype': 'outlier'})

    if col_name in self.text_cols:
      anomalies = self.detect_anomalies(column, issue_df)
      for row_id in anomalies:
        new_issues.append({'row_id': row_id, 'original_value': column.iloc[row_id], 'issue_subtype': 'anomaly'})

    if col_name in self.datetime_cols:
      datetime_issues = self.detect_datetime_issues(column, col_name)
      for row_id in datetime_issues:
        new_issues.append({'row_id': row_id, 'original_value': column.iloc[row_id], 'issue_subtype': 'date_issue'})

    if col_name in self.location_cols:
      location_issues = self.detect_location_issues(column, col_name)
      for row_id in location_issues:
        new_issues.append({'row_id': row_id, 'original_value': column.iloc[row_id], 'issue_subtype': 'loc_issue'})

    if new_issues:
      filled_issues = [{**issue, 'column_name': col_name, 'issue_type': 'concern'} for issue in new_issues]
      new_issues_df = pd.DataFrame(filled_issues)
      issue_df = pd.concat([issue_df, new_issues_df], ignore_index=True)

    concerning_rows = self.detected_row_ids(issue_df, col_name, 'concern')
    self.prepared = True
    return issue_df, concerning_rows

  # -------------- outliers ----------------
  def detect_outliers(self, col_series, column_name):
    """ We define 'outlier' as irregular numbers, as opposed to text
    Performs Z-scores, IQR and Isolation Forest outlier detection on each column
    Parameters:
      * col_series - the Pandas column to be checked
      * column_name - the name of the column as a string
    Returns:
      * outliers - list of row ids containing outliers
    """
    outliers = []
    filtered_df = col_series.dropna()

    # a value can only be an outlier if there are enough data points to begin with
    if len(filtered_df) > 8:
      try:
        numeric_df = pd.to_numeric(filtered_df, errors='coerce').dropna()
        zs_outliers, ratio = self.z_score_detection(numeric_df)
        iqr_outliers = self.iqr_detection(numeric_df)
        if_outliers = self.forest_detection(numeric_df, ratio)
        neg_outliers = self.negative_detection(numeric_df)
      except Exception as e:
        print(f"Error in detecting outliers for column {column_name}: {str(e)}")
        return outliers

      if self.level == 'high':
        overlap_all = zs_outliers & iqr_outliers & if_outliers
        outliers = list(overlap_all)
      elif self.level == 'medium':
        majority_vote = (zs_outliers & iqr_outliers) | (zs_outliers & if_outliers) | (iqr_outliers & if_outliers)
        outliers = list(majority_vote | neg_outliers)
      elif self.level == 'low':
        at_least_once = zs_outliers | iqr_outliers | if_outliers
        outliers = list(at_least_once | neg_outliers)

    return outliers

  def negative_detection(self, data):
    # return indices of rows that contain negative values when majority of values are positive
    ratio_positive = len(data[data > 0]) / len(data)
    if ratio_positive > 0.95:
      outlier_ids = set(data[data < 0].index)
    else:
      outlier_ids = set()
    return outlier_ids

  def z_score_detection(self, data):
    outliers_zscore = (zscore(data).abs() > 3.2)
    outlier_ids = data[outliers_zscore].index
    ratio = len(outlier_ids) / len(data)
    return set(outlier_ids), ratio

  def iqr_detection(self, data):
    Q1 = data.quantile(0.25)
    Q3 = data.quantile(0.75)
    quartile_range = Q3 - Q1

    too_big = data > (Q3 + 1.6 * quartile_range)
    too_small = data < (Q1 - 1.6 * quartile_range)
    outliers_iqr = too_big | too_small
    outlier_ids = data[outliers_iqr].index
    return set(outlier_ids)

  def forest_detection(self, data, ratio=0.03):
    if ratio > 0 and len(data) > 32:
      model = IsolationForest(contamination=ratio)
      reshaped_data = data.values.reshape(-1, 1)
      outliers_forest = model.fit_predict(reshaped_data) == -1
      outliers_ids = set(data[outliers_forest].index)
    else:
      outliers_ids = set()
    return outliers_ids

  # -------------- anomalies ----------------
  def detect_anomalies(self, col_series, issue_df):
    """ We define 'anomaly' as irregular text, as opposed to numbers
    Performs three checks
      1. Check for test rows. A test row is one where at least 3 columns have signals of being default values
      2. Check is string length is too long, or otherwise irregular
      3. Check for encoding errors

    Parameters:
      * col_series - the Pandas column to be checked
      * column_name - the name of the column as a string
    Returns
      * anomalies - list of row ids containing anomalies
    """
    anomalies = []
    # anomalies.extend(self.test_row_detection(col_series, main_df))
    anomalies.extend(self.string_length_in_series(col_series))
    anomalies.extend(self.encoding_error_in_series(col_series))
    anomalies = list(set(anomalies))
    return anomalies

  def test_row_detection(self, col_series, main_df):
    anomaly_ids = []
    for primary_id, cell in col_series.items():
      if str(cell).lower() == missing_tokens:
        candidate = primary_id
      if str(cell).lower in default_tokens:
        candidate = primary_id

      row_counts = 1
      if candidate:
        # then check the other rows in the table
        for cell in main_df.loc[primary_id]:
          if str(cell).lower() == missing_tokens:
            row_counts += 1
          if str(cell).lower in default_tokens:
            row_counts += 1

      if row_counts >= 3:
        anomaly_ids.append(primary_id)
    return anomaly_ids

  def string_length_in_series(self, series: pd.Series):
    zscore_thresholds = {'high': 3.2, 'medium': 3.6, 'low': 4.0}
    data_sample = sample_from_series(series)
    str_lengths = data_sample.astype(str).apply(len)
    mean_len, std_dev_len = str_lengths.mean(), str_lengths.std()

    all_lengths = series.astype(str).apply(len)
    all_z_scores = (all_lengths - mean_len) / std_dev_len
    threshold = zscore_thresholds[self.level]
    return all_z_scores[abs(all_z_scores) > threshold].index.tolist()

  def encoding_error_in_series(self, series: pd.Series):
    def has_encoding_errors(s):
      s = str(s)
      return ('\ufffd' in s or  # Unicode replacement character
              '\u0000' in s or  # Null character
              '\u007F' in s)  # Delete character

    has_error = series.apply(has_encoding_errors)
    error_indices = series[has_error].index.tolist()
    return error_indices

  # -------------- date issues ----------------
  def detect_datetime_issues(self, col_series, column_name):
    """ Dates are their own special case, separate from text and numbers
    Computes the same test as 'outlier's, but with functions that are specific to dates """
    datetime_issues = []
    check_functions = ['too_far_past', 'invalid_dates', 'placeholder_dates', 'unusual_timestamp']
    col_subtype = self.tab_properties[column_name]['subtype']

    if col_subtype in ['timestamp', 'date']:
      current_col = col_series.apply(convert_to_date)
      for func_name in check_functions:
        new_issues = getattr(self, func_name)(current_col)  # if the potential 'issues' make up the majority of rows
        if len(new_issues) < 0.5 * len(col_series):  # then it's probably supposed to be that way, so we ignore
          datetime_issues.extend(new_issues)

    elif col_subtype == 'month':
      new_issues = self.out_of_range(col_series, 12)
      if len(new_issues) > 0:
        datetime_issues.extend(new_issues)

    elif col_subtype == 'week':
      new_issues = self.out_of_range(col_series, 7)
      if len(new_issues) > 0:
        datetime_issues.extend(new_issues)

    elif col_subtype == 'day':
      new_issues = self.out_of_range(col_series, 31)
      if len(new_issues) > 0:
        datetime_issues.extend(new_issues)

    return list(set(datetime_issues))

  def out_of_range(self, series: pd.Series, max_val):
    # Check to make sure that the values in a series of dates are within a certain range
    above_range = series > max_val
    above_indices = series[above_range].index.tolist()
    below_range = series < 1
    below_indices = series[below_range].index.tolist()

    beyond_range_indicies = above_indices + below_indices
    return beyond_range_indicies

  def too_far_past(self, series: pd.Series, years=100):
    """ Check a series of dates for dates that are more than 100 years ago """
    # Convert the reference date to date-only to ignore hour/minute components
    past_date = (pd.Timestamp.now() - pd.DateOffset(years=years)).date()

    past_indices = []
    for index, ts in series.items():
      # normalize() sets all times to midnight, then .date() removes time component entirely
      if pd.notna(ts) and ts.normalize().date() < past_date:
        past_indices.append(index)
    return past_indices

  def invalid_dates(self, series: pd.Series):
    # Check a series of dates for entries that are not valid dates
    invalid_mask = series.isna()
    invalid_indices = series[invalid_mask].index.tolist()
    return invalid_indices

  def placeholder_dates(self, series: pd.Series):
    # Check a series of dates for entries that are likely to be placeholder values
    placeholder_dates = ['0000-00-00', '9999-12-31', '1900-01-01', '2000-01-01']
    str_series = series.astype(str)
    placeholder_mask = str_series.isin(placeholder_dates)
    placeholder_indices = series[placeholder_mask].index.tolist()
    return placeholder_indices

  def unusual_timestamp(self, series: pd.Series):
    duplicate_counts = series.value_counts()
    high_counts = duplicate_counts[duplicate_counts >= 10].index
    unusual_indices = series[series.isin(high_counts)].index.tolist()
    return unusual_indices

  # -------------- location issues ----------------
  def detect_location_issues(self, col_series, column_name):
    """ Locations are their own special case, separate from text and numbers """
    location_issues = []

    new_issues = self.too_long(col_series)  # if the potential 'issues' make up the majority of rows
    if len(new_issues) < 0.5 * len(col_series):  # then it's probably supposed to be that way, so we ignore
      location_issues.extend(new_issues)

    new_issues = self.too_short(col_series)
    if len(new_issues) < 0.5 * len(col_series):
      location_issues.extend(new_issues)

    return list(set(location_issues))

  def too_long(self, series: pd.Series):
    # Check a series of locations for items that are much longer than normal
    str_series = series.astype(str)
    median_length = str_series.apply(len).median()
    max_length = median_length * 3
    disproportionately_long = str_series[str_series.apply(len) > max_length].index.tolist()
    return disproportionately_long

  def too_short(self, series: pd.Series):
    # Check a series of locations for items that are much shorter than normal
    str_series = series.astype(str)
    median_length = str_series.apply(len).median()
    min_length = median_length / 3
    disproportionately_short = str_series[str_series.apply(len) < min_length].index.tolist()
    return disproportionately_short

  def print_to_command_line(self, concerns, itype, table):
    issue_rows = []
    for col_issues in concerns.values():
      issue_rows.extend(col_issues)
      issue_rows = set(issue_rows)
    print(f"{len(issue_rows)} {itype} found in {self.table_name}")

    if issue_rows:
      full_row = table[table.index.isin(issue_rows)]
      ckeys = [key for key, vals in concerns.items() if len(vals) > 0]
      print(full_row[ckeys][:10].to_csv(index=False))

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

        # if is_date_time(samples, column):
        #   date_cols.append(column)
        # elif is_number(samples):
        #   numeric_cols.append(column)
        # else:
        textual_cols.append(column)

      elif df[column].dtypes == 'datetime64[ns]':
        date_cols.append(column)
      elif df[column].dtypes in [np.int64, np.float64]:
        numeric_cols.append(column)
      else:
        textual_cols.append(column)

    return numeric_cols, textual_cols, date_cols

  @staticmethod
  def type_to_nl(concern_type, count, prefix='article'):
    # Converts concern type to natural language, prefix options are digit, article, or none
    if prefix == 'article':
      if count == 1:
        if concern_type in ['outlier', 'anomaly']:
          result = 'an '
        elif concern_type in ['date_issue', 'loc_issue']:
          result = 'a '
      else:
        result = ''
    elif prefix == 'digit':
      result = f'{count} '
    else:
      result = ''

    if count == 1:
      if concern_type in ['outlier', 'anomaly']:
        result += concern_type
      elif concern_type == 'date_issue':
        result += 'date issue'
      elif concern_type == 'loc_issue':
        result += 'location issue'
    else:
      if concern_type == 'outlier':
        result += 'numeric outliers'
      elif concern_type == 'anomaly':
        result += 'textual anomalies'
      elif concern_type == 'date_issue':
        result += 'date issues'
      elif concern_type == 'loc_issue':
        result += 'location issues'

    return result