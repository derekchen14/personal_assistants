import json
import pandas as pd
import difflib
import numpy as np
import json_repair
from backend.assets.ontology import common_abbreviations, NA_string

class PromptEngineer(object):

  def __init__(self, tab_properties, tab_name, api):
    self.tab_name = tab_name
    self.tab_properties = tab_properties
    self.api = api

  @staticmethod
  def array_to_nl(array, connector='or'):
    if len(array) == 0:
      nat_lang_desc = "none"
    elif len(array) == 1:
      nat_lang_desc = array[0]
    elif len(array) == 2:
      nat_lang_desc = f"{array[0]} {connector} {array[1]}"
    elif len(array) == 3:
      nat_lang_desc = f"{array[0]}, {array[1]}, {connector} {array[2]}"
    else:
      nat_lang_desc = ", ".join(array[:-1]) + f", {connector} {array[-1]}"
    return nat_lang_desc

  @staticmethod
  def apply_guardrails(raw_code, language, valid_tabs=[]):
    print(f"  Executing {language.upper()}:")
    skipped_phrases = ["Thought:", "```", "import", "_", "json"]
    
    match language:
      case 'python': skipped_phrases.append("# ")
      case 'sql': skipped_phrases.append("-- ")
      case 'javascript': skipped_phrases.append("// ")

    valid_lines = []
    for line in raw_code.split('\n'):
      if len(line) == 0:
        continue
      should_skip = any([line.startswith(phrase) for phrase in skipped_phrases])
      if should_skip:
        continue
      print(f"  {line}")

      vline = line.rstrip() if language == 'python' else line

      for table_name in valid_tabs:
        vline = vline.replace(f"db.{table_name}", f"self.db.tables['{table_name}']")
        vline = vline.replace(f"db['{table_name}']", f"self.db.tables['{table_name}']")
      valid_lines.append(vline)

    try:
      generated_code = "\n".join(valid_lines)
      result = json_repair.loads(generated_code) if language == 'json' else generated_code.strip()

    except json.JSONDecodeError as ecp:
      generated_code = " ".join(valid_lines)
      try:
        result = json.loads(generated_code)
      except:
        print(f"Error decoding generated JSON - {generated_code}")
        result = {'error': str(ecp)}
    return result

  @staticmethod
  def activate_guardrails(raw_code, trigger_phrase='```python', valid_tabs=[]):
    print(f"  Executing Python:")
    activated = False
    valid_lines = []

    for line in raw_code.split('\n'):
      if not line.startswith("```"):
        print(f"  {line}")    # Print all the lines, including the plan, even if they are ultimately skipped

      if line.strip() == trigger_phrase:
        activated = True
        continue
      elif not activated:
        continue

      if len(line) == 0 or line.startswith("# ") or line.startswith("```"):
        continue

      for table_name in valid_tabs:
        line = line.replace(f"db.{table_name}", f"self.db.tables['{table_name}']")
        line = line.replace(f"db['{table_name}']", f"self.db.tables['{table_name}']")
      valid_lines.append(line.rstrip())

    generated_code = "\n".join(valid_lines)
    return generated_code

  @staticmethod
  def tab_col_rep(world, include_tab=True, with_break=True):
    joint_representation = ""
    if include_tab:
      tab_representation = "; ".join(world.valid_tables)
      joint_representation = f"* Tables: {tab_representation}\n"

    columns_strings = []
    for table, cols in world.valid_columns.items():
      col_str = ", ".join(cols) + f" in {table} table"
      columns_strings.append(col_str)
    if with_break:
      col_representation = ";\n".join(columns_strings)
    else:
      col_representation = "; ".join(columns_strings)

    joint_representation += f"* Columns: {col_representation}"
    return joint_representation

  @staticmethod
  def column_rep(column_dict, with_break=True):
    columns_strings = []
    for table, cols in column_dict.items():
      col_str = ", ".join(cols) + f" in {table} table"
      columns_strings.append(col_str)
    if with_break:
      col_representation = ";\n".join(columns_strings)
    else:
      col_representation = "; ".join(columns_strings)
    return col_representation

  @staticmethod
  def display_preview(df, columns=[], max_rows=64, method='markdown', signal_limit=True):
    """ Returns a preview of the first few rows in a given dataframe
    Since our goal is to maintain a faithful representation of the data, we will never skip null values.
    Format options include markdown, comma, transpose """
    if len(columns) > 0:
      df = df[columns]              # first limit by columns
    df = df.head(max_rows)          # then limit by rows
    df = df.astype('string').fillna(NA_string)  # fill NaNs to prevent markdown errors

    if method == 'markdown':
      result = df.to_markdown(index=False)
    elif method == 'comma':
      lines = [', '.join(row) for row in df.values.tolist()]
      result = "\n".join(lines)
    elif method == 'transpose':
      lines = []
      for col_name, column in df.items():
        col_string = ', '.join(column.tolist())
        lines.append(f"{col_name}: {col_string}")
      result = "\n".join(lines)

    total_rows = len(df)
    if total_rows > max_rows and signal_limit:
      result += f"\n[Truncated: showing {max_rows} of {total_rows:,} rows]"
    return result

  @staticmethod
  def display_samples(df, columns=[], num_samples=32, method='markdown', skip_nulls=False):
    """ Returns a random sample of rows in a given dataframe for a set of columns
    Since our goal is to sample some rows, we already know that the result is a truncated view of the data.
    Format options include markdown, transpose, most_common """
    cols = columns[:8] if len(columns) > 0 else df.columns[:8]
    if skip_nulls:
      df = df.dropna(subset=cols).astype('string')
      is_NA_mask = df[cols].isin([NA_string]).any(axis=1)
      df = df[~is_NA_mask]                        # only keeps rows with valid content
    else:
      df = df.astype('string').fillna(NA_string)  # fill NaNs to prevent markdown errors

    # limit the length of each row to 128 characters
    df = df.map(lambda x: f"{x[:128]}..." if len(str(x)) > 128 else x)

    if method == 'most_common':
      occurence_counts = df[cols].value_counts()
      lines = []
      for value, count in occurence_counts.items():
        sample_line = f"{value} - {count} instance"
        if count > 1:
          sample_line += "s"
        lines.append(sample_line)
        if len(lines) >= num_samples:
          break
      result = "\n".join(lines)

    elif method == 'markdown':
      samples = df.sample(n=min(num_samples, len(df)))[cols]
      result = samples.to_markdown(index=False)

    elif method == 'dataframe':
      result = df.sample(n=min(num_samples, len(df)))[cols]

    elif method == 'transpose':
      samples = df.sample(n=min(num_samples, len(df)))[cols]
      lines = []
      for col_name, column in samples.items():
        col_string = ', '.join(column.tolist())
        lines.append(f"{col_name}: {col_string}")
      result = "\n".join(lines)

    return result

  @staticmethod
  def display_plan(plan:list[dict], join_key:str=''):
    steps = []
    for index, step in enumerate(plan, 1):
      status = " (complete)" if step.get("checked", False) else ""
      reformatted_step = f"{index}. {step['name']}{status} - {step['description']}"
      steps.append(reformatted_step)

    result = join_key.join(steps) if join_key else steps
    return result

  def compile_description(self, table, pkey):
    # parse the table to learn about the columns
    desc = f"The '{self.tab_name}' table contains columns: "
    desc, column_list = self.add_column_names(desc, table)
    desc += f"Primary key is likely to be {pkey}. "

    for col_name in column_list:
      desc = self.expand_abbreviations(desc, col_name)
      properties = self.tab_properties.get(col_name, {})
      if len(properties) > 0:
        desc = self.date_explanations(desc, col_name, table[col_name], properties)
        desc = self.summarize_values(desc, col_name, table[col_name], properties)
    return desc

  def expand_abbreviations(self, desc, col_name):
    if col_name in common_abbreviations:
      expanded = common_abbreviations[col_name]
      desc += f"{col_name} stands for {expanded}. "
    else:
      replacement = False
      parts = []
      for part in col_name.split("_"):
        if part in common_abbreviations:
          expanded = common_abbreviations[part]
          replacement = True
          parts.append(expanded)
        else:
          parts.append(part)

      renamed = " ".join(parts)
      if replacement:
        desc += f"{col_name} likely refers to {renamed}. "

    return desc

  def date_explanations(self, desc, col_name, pd_series, properties):
    if properties['type'] == 'datetime':
      try:
        low, high = pd_series.min(), pd_series.max()
      except(TypeError):
        # the months or days are written as text rather than numbers (ie. February, 1st, Monday)
        return desc

      match properties['subtype']:
        case 'hour': explanation = f"Hours range from {low} to {high}. "
        case 'day': explanation = f"Day is in digits from {low} to {high}. "
        case 'month': explanation = f"Month is in digits from {low} to {high}. "
        case 'year': explanation = f"Year ranges from {low} to {high}. "
        case _: explanation = ""
      desc += explanation
    return desc

  def summarize_values(self, desc, col_name, pd_series, properties):
    subtype = properties['subtype']

    match properties['type']:
      case 'unique': summary = self.summarize_unique_cols(pd_series, col_name, subtype)
      case 'datetime': summary = self.summarize_datetime_cols(pd_series, col_name)
      case 'location': summary = self.summarize_location_cols(col_name)
      case 'number': summary = self.summarize_number_cols(pd_series, col_name)
      case 'text': summary = self.summarize_text_cols(pd_series, col_name, subtype)
      case _: summary = ""

    desc += summary
    return desc

  def summarize_unique_cols(self, pd_series, col_name, subtype):
    if subtype in ['boolean', 'status']:
      unique_df = pd_series.dropna().unique()
      if subtype == 'status':
        unique_df.sort()

      nl_description = self.array_to_nl(unique_df)
      if len(unique_df) == 1:
        summary = f"{col_name} value is always {nl_description}"
      elif len(unique_df) == 2 or len(unique_df) == 3:
        summary = f"{col_name} value is either {nl_description}"
      else:
        summary = f"{col_name} value includes {nl_description}"

      if pd_series.isnull().any():
        summary += ", along with some null values. "
      else:
        summary += ". "

    elif subtype == 'category':
      unique_values = pd_series.unique()
      if len(unique_values) == 1:
        summary = f"{col_name} has only one unique category: {unique_values[0]}. "
      elif len(unique_values) == 2:
        summary = f"{col_name} has two values of either {unique_values[0]} or {unique_values[1]}. "
      else:
        most_common_values = pd_series.value_counts().head(3).index.tolist()
        avg_length = np.mean([len(str(val)) for val in most_common_values])
        mcv = most_common_values if avg_length > 16 else pd_series.value_counts().head(5).index.tolist()
        mcv = [str(value) for value in mcv]
        examples = ", ".join(mcv)[:-1]

        summary = f"{col_name} are categorical values such as {self.array_to_nl(mcv)}. "
          
    elif subtype == 'id':
      summary = f"{col_name} is an ID column serving as a good candidate for joins. "

    return summary

  def summarize_datetime_cols(self, pd_series, col_name):
    time_series = pd_series.dropna()
    earliest = time_series.min()
    most_recent = time_series.max()
    summary = f"{col_name} datetimes range from {earliest} to {most_recent}. "
    return summary

  def summarize_location_cols(self, col_name):
    summary = f"{col_name} is related to locations and addresses. "
    return summary

  def summarize_number_cols(self, pd_series, col_name):
    numeric_series = pd.to_numeric(pd_series, errors='coerce')
    numeric_series = numeric_series.dropna()

    if numeric_series.empty:
      summary = f"{col_name} values should be numbers, but have problems since they are mixed with string data."
    else:
      max_val = numeric_series.max()
      min_val = numeric_series.min()
      summary = f"{col_name} values range from {min_val} to {max_val}. "
    return summary

  def summarize_text_cols(self, pd_series, col_name, subtype):
    pd_series = pd_series.fillna('N/A')
    occurence_counts = pd_series.value_counts().head(3)
    top_count = occurence_counts.iloc[0]
    most_common_values = [val for val in occurence_counts.index.tolist() if isinstance(val, str)]
    mcv_length = np.mean([len(val) for val in most_common_values])

    if mcv_length > 128:
      mcv = most_common_values[:1]
      if len(mcv) > 512:
        mcv = mcv[:512] + "... (truncated)"
      avg_length = round(np.mean([len(val) for val in pd_series if isinstance(val, str)]), 2)
      suffix_desc = f"'{mcv}'. The typical text is quite long though, with an average of {avg_length} characters. "
    elif mcv_length > 16:
      mcv = most_common_values
      suffix_desc = f"{self.array_to_nl(mcv)}. "
    else:
      mcv = [val for val in pd_series.value_counts().head(5).index.tolist() if isinstance(val, str)]
      suffix_desc = f"{self.array_to_nl(mcv)}. "

    if subtype in ['email', 'url', 'name']:
      summary = f"{col_name} are {subtype}s such as "
    elif subtype == 'phone':
      summary = f"{col_name} are phone numbers such as "
    else:
      summary = f"{col_name} are general strings including "

    summary += suffix_desc
    if top_count < 3:
      summary += f"Most values in this column are unique. "
    return summary

  @staticmethod
  def token_overlap(tok1, tok2):
    matcher = difflib.SequenceMatcher(None, tok1, tok2)
    match = matcher.find_longest_match(0, len(tok1), 0, len(tok2))

    clean1 = tok1.replace(" ", "").replace("_", "")
    clean2 = tok2[:-2].replace(" ", "").replace("_", "")  # also remove the "id"
    match_ratio1 = match.size / len(clean1) if len(clean1) > 0 else 0
    match_ratio2 = match.size / len(clean2) if len(clean2) > 0 else 0
    is_overlap = match_ratio1 > 0.7 and match_ratio2 > 0.5
    return is_overlap, match_ratio1

  def add_column_names(self, desc, table):
    column_list = table.columns.to_list()
    # keep columns names that do not start with "Unnamed"
    column_list = [col for col in column_list if not col.startswith("Unnamed")]
    column_names = ', '.join(column_list)
    desc += column_names + ". "
    return desc, column_list

  @staticmethod
  def write_preference_desc(preferences):
    # Input is dictionary of preferences, pre-processed from the world
    description = ""
    for pref_name in ['goal', 'caution', 'recent', 'special', 'sig']:
      pref = preferences.get(pref_name, None)
      if pref and pref.endorsed:
        description += pref.make_prompt_fragment()
    return description