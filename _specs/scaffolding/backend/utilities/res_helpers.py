import pandas as pd
from backend.components.engineer import PromptEngineer

def gather_relevant_facts(flow, frame, general_schema, state):
  all_facts = []

  tab_schema = general_schema[state.current_tab]
  nrows = tab_schema.general_stats["num_rows"]
  ncols = tab_schema.general_stats["num_cols"]
  all_facts.append(f"the {state.current_tab} table contains {nrows} rows and {ncols} columns")
  all_facts.append(extract_relevant_cols(flow, state, ncols))

  for entity in flow.slots['source'].values:
    if entity['col'] not in tab_schema.tab_properties.keys():
      continue

    type_info = tab_schema.get_type_info(entity['col'])
    datatype_fact = f"the {entity['col']} column is a {type_info['type']} with {type_info['subtype']} subtype"
    all_facts.append(datatype_fact)

    for pertinent_fact in flow.slots['facts'].values:
      match pertinent_fact:
        case 'statistics': statistic = extract_statistics(tab_schema, entity['col'])
        case 'preview': statistic = extract_distribution(tab_schema, entity['col'])
        case 'range': statistic = extract_range_fact(tab_schema, entity['col'])
        case 'count': statistic = extract_count_fact(tab_schema, entity['col'])
        case _: statistic = ''
      if len(statistic) > 0:
        all_facts.append(statistic)

  return all_facts

def extract_relevant_cols(flow, state, num_columns):
  num_entities = len(flow.slots['source'].values)
  if num_entities == num_columns:
    relevant = f"relevant sources include all {num_entities} columns in the {state.current_tab} table"
  else:
    parts = [f"the {entity['col']} column in {entity['tab']}" for entity in flow.slots['source'].values]
    relevant = f"relevant columns include {PromptEngineer.array_to_nl(parts, connector='and')}"
  return relevant

def extract_distribution(tab_schema, col_name):
  distribution_desc = ''
  if col_name in tab_schema.text_stats:
    distribution_desc = tab_schema.text_stats[col_name].get('distribution', '')
  elif col_name in tab_schema.number_stats:
    distribution_desc = tab_schema.number_stats[col_name].get('distribution', '')
  elif col_name in tab_schema.unique_stats:
    distribution_desc = tab_schema.unique_stats[col_name].get('distribution', '')

  if len(distribution_desc) > 0:
    distribution_desc = f"The distribution of the most common values:\n{distribution_desc}"
  return distribution_desc

def extract_statistics(tab_schema, col_name):
  statistics = ''
  if col_name in tab_schema.number_stats.keys():
    col_info = tab_schema.number_stats[col_name]
    mean, median, mode = col_info['average'], col_info['median'], col_info['mode']
    std_dev = col_info['std_dev']

    statistics += f"for the {col_name} column, the mean is {mean}, median is {median},"
    if mode:
      statistics += f" mode is {mode},"
    statistics += f" and standard deviation is {std_dev}"
  elif col_name in tab_schema.text_stats.keys():
    col_info = tab_schema.text_stats[col_name]
    avg_length = col_info["avg_length"]
    statistics += f"for the {col_name} column, the average string length is {avg_length} characters"
  return statistics

def extract_range_fact(tab_schema, col_name):
  range_fact = ''
  if col_name in tab_schema.number_stats:
    col_info = tab_schema.number_stats[col_name]
    range_info, minimum, maximum = col_info['range'], col_info['min'], col_info['max']
    range_fact = f"the {col_name} column goes from {minimum} to {maximum} for a total range of {range_info}"
  elif col_name in tab_schema.datetime_stats:
    col_info = tab_schema.datetime_stats[col_name]
    earliest = col_info.get('earliest', None)
    latest = col_info.get('latest', None)
    if earliest and latest:
      range_fact = f"the {col_name} column goes from {earliest} to {latest}"
  return range_fact

def extract_count_fact(tab_schema, col_name):
  count_fact = ''
  if col_name in tab_schema.unique_stats:
    col_info = tab_schema.unique_stats[col_name]
    count_fact = f"the {col_name} column contains {len(col_info.keys())} unique values"
  elif col_name in tab_schema.datetime_stats:
    col_info = tab_schema.datetime_stats[col_name]
    nunique = col_info["num_uniques"]
    count_fact = f"the {col_name} column contains {nunique} unique datetime values"
  elif col_name in tab_schema.number_stats:
    col_info = tab_schema.number_stats[col_name]
    nunique = col_info["num_uniques"]
    count_fact = f"the {col_name} column contains {nunique} unique numeric-based values"
  elif col_name in tab_schema.location_stats:
    col_info = tab_schema.number_stats[col_name]
    nunique = col_info["num_uniques"]
    count_fact = f"the {col_name} column contains {nunique} unique location-related values"
  elif col_name in tab_schema.text_stats:
    col_info = tab_schema.text_stats[col_name]
    nunique = col_info["num_uniques"]
    count_fact = f"the {col_name} column contains {nunique} unique text-based values"
  return count_fact

"""
all_facts.append(PromptEngineer._build_common_strings(col_info, column))
"""

