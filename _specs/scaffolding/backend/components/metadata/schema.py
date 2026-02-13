import math
import pandas as pd
from backend.components.metadata import MetaData
from backend.utilities.search import sample_from_series
from backend.utilities.manipulations import unique_value_distribution

class Schema(MetaData):

  def __init__(self, table, tab_name, tab_properties, level, api=None):
    super().__init__(tab_properties, tab_name, level, api)
    self.types = {}
    self.subtypes = {}
    self.supplements = {}
    self.level = level

    for column_name, properties in self.tab_properties.items():
      self.types[column_name] = properties['type']
      self.subtypes[column_name] = properties['subtype']
      self.supplements[column_name] = properties.get('supplement', {})

    self.set_general_statistics(table)
    self.set_unique_statistics(table)
    self.set_datetime_statistics(table)
    self.set_location_statistics(table)
    self.set_number_statistics(table)
    self.set_text_statistics(table)

    for schema_type in ['unique', 'datetime', 'location', 'number', 'text']:
      columns = getattr(self, f"{schema_type}_cols")
      print(f"> {schema_type}: ", [(col, self.subtypes[col]) for col in columns])

  def __str__(self):
    output = []
    output.append(f"Schema with {self.general_stats['num_rows']} rows, {self.general_stats['num_cols']} columns")
    
    for schema_type in ['unique', 'datetime', 'location', 'number', 'text']:
      columns = getattr(self, f"{schema_type}_cols")
      column_info = [(col, self.subtypes[col]) for col in columns]
      output.append(f"> {schema_type}: {column_info}")

    return "\n".join(output)

  def get_type_info(self, col_name, include_supplement=True):
    if col_name == '*':
      col_name = self.general_stats['column_names'][0]
    if col_name not in self.tab_properties:
      print(f"WARNING: {col_name} not found in schema!")

    results = {
      'tab_name': self.tab_name,
      'col_name': col_name,
      'type': self.types.get(col_name, 'unknown'),
      'subtype': self.subtypes.get(col_name, 'unknown'),
    }
    if include_supplement:
      results['supplement'] = self.supplements.get(col_name, {})
    return results

  def set_type_info(self, col_name, main_type, sub_type, supplement={}):
    self.types[col_name] = main_type
    self.subtypes[col_name] = sub_type
    self.supplements[col_name] = supplement

  def set_general_statistics(self, table):
    num_rows, num_cols = table.shape
    self.general_stats = {
      'num_rows': num_rows,
      'num_cols': num_cols,
      'column_names': list(table.columns)
    }

  # -------------- Unique ----------------
  def set_unique_statistics(self, table):
    """ {column_name: {value: ratio}} """
    self.unique_stats = {}
    for column_name in self.unique_cols:
      if self.subtypes[column_name] == 'id':
        continue
      self.unique_stats[column_name] = {}
      data = table[column_name]
      for unique_val in data.unique():
        if pd.isna(unique_val):
          continue
        self.unique_stats[column_name][unique_val] = round(data.value_counts(normalize=True)[unique_val], 2)

      settings = {'include_nulls': True, 'show_nulls_as_count': False, 'show_arrow': False}
      if self.subtypes[column_name] in ['boolean', 'status', 'category']:
        distribution_desc = unique_value_distribution(data, settings, suffix=' instance')
        self.unique_stats[column_name]['distribution'] = distribution_desc

  # -------------- Datetime --------------
  def set_datetime_statistics(self, table):
    """ {column_name: with keys for [earliest, latest]} """
    self.datetime_stats = {}
    for col_name in self.datetime_cols:
      self.datetime_stats[col_name] = {}
      self.datetime_stats[col_name]["num_uniques"] = table[col_name].nunique()
      try:
        time_series = table[col_name].dropna()
        self.datetime_stats[col_name]['earliest'] = time_series.min()
        self.datetime_stats[col_name]['latest'] = time_series.max()
      except Exception as e:
        print(f"ERROR in Schema get datetime statistics for column ({col_name}): ", e)
        continue

  # -------------- Location --------------
  def set_location_statistics(self, table):
    """ {column_name: with keys for [earliest, latest]} """
    self.location_stats = {}
    for col_name in self.location_cols:
      self.location_stats[col_name] = {}
      self.location_stats[col_name]["num_uniques"] = table[col_name].nunique()

  # -------------- Number --------------
  def set_number_statistics(self, table):
    """ {column_name: with keys of [min, max, mean, median, stddev, variance]} """
    self.number_stats = {}
    for column_name in self.number_cols:
      pd_series = table[column_name]
      clean = pd.Series([x for x in pd_series if not isinstance(x, str)])
      column_info = {"num_uniques": clean.nunique()}
      self.number_stats[column_name] = self.handle_numbers(clean, column_info)

  def handle_numbers(self, series, column_info={}):
    # calculate common statistics for numeric related columns
    column_info['range'] = series.max() - series.min()
    column_info['average'] = round(series.mean(), 3)
    column_info['min'] = series.min()
    column_info['max'] = series.max()
    column_info['std_dev'] = round(series.std(), 2)
    column_info['median'] = series.median()

    mode = series.mode()
    column_info['mode'] = mode[0] if len(mode) == 1 else None
    column_info = self.handle_sum(series, column_info)

    settings = {'include_nulls': True, 'show_nulls_as_count': False, 'show_arrow': False}
    column_info['distribution'] = unique_value_distribution(series, settings, suffix=' instance')
    return column_info

  def handle_sum(self, series, column_info):
    samples = sample_from_series(series)
    sample_sum = samples.sum()
    sample_avg = samples.mean()

    # calculate sum if sum is not too large
    if sample_avg < 1000000 and sample_sum < 1000000000000:
      if sample_avg < 0 or sample_sum < 0:
        column_info['sum'] = -1
      else:
        column_info['sum'] = round(series.sum(), 3)
    else:
      column_info['sum'] = -1
    return column_info

  # -------------- Text ------------------
  def set_text_statistics(self, table):
    """ {column_name: {avg_length: float, most_common: list}} """
    self.text_stats = {}
    for column_name in self.text_cols:
      column_info = {"num_uniques": table[column_name].nunique()}
      self.text_stats[column_name] = self.handle_strings(table[column_name], column_info)

  def handle_strings(self, series, column_info={}):
    # calculate common statistics for string related columns
    column_info['avg_length'] = round(series.astype(str).str.len().mean(), 3)

    ratio = series.nunique() / float(len(series))
    if ratio < 0.5:
      common_df = series.value_counts().head(3)
      common_list = [(x[0], x[1]) for x in common_df.items()]
      column_info['most_common'] = common_list
    else:
      column_info['most_common'] = []

    settings = {'include_nulls': True, 'show_nulls_as_count': True, 'show_arrow': False}
    column_info['distribution'] = unique_value_distribution(series, settings, suffix=' instance')
    return column_info