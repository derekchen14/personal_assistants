import re
import pandas as pd
import csv
from collections import Counter
from backend.prompts.general import identify_footer_prompt

class BaseLoader(object):
  """ Base object for loading data """
  def __init__(self, source):
    self.source = source
    self.holding = {}   # temporary holding spot as incremental tables are loaded

  def review_naming(self, ss_name, tab_names, existing_spreadsheets):
    # check on limits of number of spreadsheets
    if len(existing_spreadsheets) >= 5:
      return False, "Maximum of number of spreadsheets reached. Please remove some before adding more, or talk to our sales team for increased capacity."
    # ensure that directory name is unique
    if ss_name in existing_spreadsheets:
      return False, "Spreadsheet with this name already exists"
    # ensure that directory names are long enough
    if len(ss_name) <= 2:
      return False, "Spreadsheet name is too short, must be longer than 2 characters"
    # only allow valid directory names that are alphanumeric or underscore or dashes
    trimmed = ss_name.replace('_', '').replace('-', '').replace(' ', '')
    if not trimmed.isalnum():
      return False, "Spreadsheet name can only contain numbers, letters, underscores, and dashes"

    # ensure that tables are unique
    unique_tables = set([tn.lower() for tn in tab_names])
    if len(unique_tables) != len(tab_names):
      return False, "Duplicate tables found in spreadsheet"
    # 'db.' is a restricted phrase since we use it to name our database
    if any(['db.' in tn.lower() for tn in tab_names]):
      return False, "Table names cannot contain 'db.' as part of the name"
    # '(tab_name)' is the format for temporary, derived tables
    if any([tn.startswith('(') for tn in tab_names]):
      return False, "Table names cannot start with a parentheses since this is a reserved format"
    # ',' is a restricted character since we use it to split table strings, also '.' or '$'
    if any([re.search(r'[^A-Za-z0-9_ -]', tn) for tn in tab_names]):
      return False, "Special characters (eg. periods or commas) are not allowed in table names, please try again."
    # ensure that there are not too many tables
    if len(tab_names) > 16:
      return False, "Too many tables in spreadsheet (max 16). Please reach out to our sales team for increased capacity."

    return True, "success"

  def get_processed(self):
    tab_names = self.holding.keys()
    return list(tab_names)

  def process_details(self, tab_names, all_sheets, details, api):
    """ Input: spreadsheet is a list of table names
    Details is a dict that should contain keys for title, description and globalExtension
    Returns:
      If processing was successful, return:
        1) True (boolean)
        2) Dictionary with keys of 'ss_name', 'ss_goal' and 'ss_data'
          a. ss_name (string) - title of the spreadsheet
          b. ss_goal (string) - description of the user's goal
          c. ss_data (dict) - keys of tab_names, values are pandas dataframes
      Otherwise, return:
        1) False (boolean)
        2) Error message (string)
    """
    pass

  @staticmethod
  def skip_empty_columns(data: list) -> list:
    """Remove any columns where header is empty string"""
    headers = data[0]
    result = []

    for row in data:
      filtered_row = []
      for i, header in enumerate(headers):
        if header:
          filtered_row.append(row[i])
      result.append(filtered_row)
    return result

  @staticmethod
  def skip_footer_rows(data: list, api) -> int:
    """Returns the number of rows to keep based on the presence of 'total' in the last few rows."""
    data_size = len(data)
    num_footer_rows = 0
    tail_rows = data[-min(16, data_size):]  # get the last 16 rows of data

    # Check if any row has "total" in any cell (case-insensitive)
    for row in tail_rows:
      if any('total' in str(cell).lower() for cell in row if cell):
        rows_as_str = []
        for idx, row in enumerate(reversed(tail_rows)):
          cells = [str(cell) if cell else ' ' for cell in row]
          row_num = data_size - idx
          rows_as_str.append(f"Row {row_num}: {' | '.join(cells)}")
        rows_text = "\n".join(rows_as_str[::-1])

        prompt = identify_footer_prompt.format(num_rows=len(tail_rows), rows_text=rows_text)
        prediction = api.execute(prompt, version='reasoning')

        try:
          num_footer_rows = int(prediction.strip())
        except ValueError:
          num_footer_rows = 0  # Default to 0 if prediction is not a valid integer
        break

    num_rows_to_keep = data_size - num_footer_rows
    return num_rows_to_keep

  @staticmethod
  def skip_file_preamble(data: list) -> int:
    """Returns the number of rows to skip from the beginning."""
    filled_counts = Counter()
    for row_idx, row in enumerate(data):
      # Skip empty rows
      if len(row) == 0: continue
      # Count the number of consecutive non-numeric cells
      for cell in row:
        if cell:
          string_cell = str(cell).strip().replace(',', '').replace('.', '')
          if string_cell in ['nan', '', 'null', 'Unnamed: 0', 'Unnamed: 1']:
            break
          elif string_cell.isdigit():
            break
          filled_counts[row_idx] += 1

    num_rows_to_skip = 0
    if filled_counts:
      # Get the maximum count of consecutive non-numeric cells
      max_cells_filled = filled_counts.most_common(1)[0][1]

      for row_idx, row_count in filled_counts.items():
        if row_count == max_cells_filled:
          num_rows_to_skip = row_idx
          break

    return num_rows_to_skip

class SpreadsheetLoader(BaseLoader):
  """ For loading CSVs and Excel files """
  def __init__(self, source, multi_tab=False):
    super().__init__(source)
    self.multi_tab = multi_tab

  def process_details(self, tab_names, all_sheets, details, api):
    ss_name, desc = details['ssName'].strip(), details['description'].strip()
    # returns whether validation passed inspection, and an error message if there was one
    passed_inspection, result = self.review_naming(ss_name, tab_names, all_sheets)

    if passed_inspection:
      # loaded data is a dict with keys of tab_names, values are pandas dataframes
      if self.multi_tab:
        loaded_data = self.holding  # the data is already loaded as a dataframe
      else:
        loaded_data = self.read_data(tab_names, details['globalExtension'])

      cleaned_data = self.preliminary_cleaning(loaded_data, api)
      output = {'ss_name': ss_name, 'ss_goal': desc, 'ss_data': cleaned_data}
      return True, output
    else:
      error_message = result
      return False, error_message

  def read_data(self, table_names, extension):
    loaded_data = {}

    for tab_name in table_names:
      raw_tab = self.holding[tab_name]
      if extension == 'csv':
        table = pd.read_csv(raw_tab, on_bad_lines='warn')
      elif extension == 'tsv':
        table = pd.read_csv(raw_tab, sep='\t')
      elif extension == 'xlsx' or extension == 'ods':
        table = pd.read_excel(raw_tab)
      else:
        raise ValueError(f"File extension {extension} not supported.")

      loaded_data[tab_name] = table
    return loaded_data

  def preliminary_cleaning(self, loaded_data, api):
    cleaned_data = {}
    for tab_name, table in loaded_data.items():
      first_row = table.columns.tolist()
      remaining_rows = table.values.tolist()
      data_list = [first_row] + remaining_rows

      num_preamble_rows = self.skip_file_preamble(data_list)
      data_list = data_list[num_preamble_rows:]
      rows_without_footer = self.skip_footer_rows(data_list, api)
      num_footer_rows = len(data_list) - rows_without_footer
      data_list = data_list[:rows_without_footer]
      print(f"Skipping {num_preamble_rows} preamble rows and {num_footer_rows} footer rows")

      # convert back to dataframe
      cleaned_data[tab_name] = pd.DataFrame(data_list[1:], columns=data_list[0])
    return cleaned_data

class VendorLoader(BaseLoader):

  def process_details(self, tab_names, all_sheets, details, api):
    ss_name = details['ssName']
    desc = details['description'].strip()
    final_tables = {}  # keys are table names, values are pandas dataframes
    passed_inspection, result = self.review_naming(ss_name, tab_names, all_sheets)

    if passed_inspection:
      success = True

      match self.source:
        case 'amplitude': final_tables = self._extract_amplitude_data()
        case 'drive': final_tables = self._extract_google_drive_data(api)
        case 'facebook': final_tables = self._extract_facebook_ads_data()
        case 'ga4': final_tables = self._extract_ga4_data()
        case 'google': final_tables = self._extract_google_ads_data()
        case 'hubspot': final_tables = self._extract_hubspot_data()
        case 'salesforce': final_tables = self._extract_salesforce_data()
        case _: success, result = False, "Unsupported vendor data source"
    else:
      success = False

    if success:
      output = {'ss_name': ss_name, 'ss_goal': desc, 'ss_data': final_tables}
    else:
      output = result
    return success, output

  def inspect_vendor_tabs(self, ss_name, existing_sheets):
    tab_names = self.get_processed()
    passed_inspection, result = self.review_naming(ss_name, tab_names, existing_sheets)

    return passed_inspection
  
  def _extract_salesforce_data(self, tab_name='salesforce'):
    final_tables = {}
    
    for tab_name, json_data in self.holding.items():
      records = json_data.get('records', [])
      rows = []
      headers = set()
      
      for record in records:
        row_data = {}
        record.pop('attributes', None )# Remove metadata
        
        # Flatten nested objects
        for field, value in record.items():
          if isinstance(value, dict):
            for nested_key, nested_value in value.items():
              column_name = f"{field}_{nested_key}"
              row_data[column_name] = nested_value
              headers.add(column_name)
          else:
            row_data[field] = value
            headers.add(field)
        rows.append(row_data)
      final_tables[tab_name] = pd.DataFrame(rows)
    
    return final_tables

  def _extract_amplitude_data(self):
    json_data = self.holding['amplitude_import']
    headers = json_data['data']['series'][0]['data'].keys() if json_data['data']['series'] else []
    rows = []
    for result in json_data['data']['series']:
      values = [result['data'].get(header, None) for header in headers]
      rows.append(values)
    return pd.DataFrame(data=rows, columns=headers)

  def _extract_ga4_data(self, tab_name='ga4_import'):
    json_data = self.holding[tab_name]
    dimension_headers = [header['name'] for header in json_data.get('dimensionHeaders', [])]
    metric_headers = [header['name'] for header in json_data.get('metricHeaders', [])]
    column_headers = dimension_headers + metric_headers

    rows = []
    for row in json_data['rows']:
      combined_values = row['dimensionValues'] + row['metricValues']
      rows.append([cell['value'] for cell in combined_values])
    ga4_df = pd.DataFrame(data=rows, columns=column_headers)
    return {tab_name: ga4_df}

  def _extract_hubspot_data(self):
    final_tables = {}
    for tab_name, json_data in self.holding.items():
      results = json_data.get('results', [])
      if not results: continue
      headers = ['hubspot_id'] + list(results[0]['properties'].keys())

      rows = []
      for result in results:
        combined_values = [result['id']]
        combined_values += list(result['properties'].values())
        rows.append(combined_values)
      final_tables[tab_name] = pd.DataFrame(data=rows, columns=headers)

    return final_tables
  
  def _extract_facebook_ads_data(self, tab_name='facebook_ads'):
    json_data = self.holding[tab_name]
    # For Facebook Ads, the data is a list of dictionaries
    # Each dictionary represents a row in our dataframe
    if not json_data:
        return {tab_name: pd.DataFrame()}
    
    # Convert list of dictionaries directly to DataFrame
    facebook_df = pd.DataFrame(json_data)
    
    return {tab_name: facebook_df}

  def _extract_google_ads_data(self, tab_name='google_ads'):
    json_data = self.holding[tab_name]
    rows, headers = [], []

    for idx, result in enumerate(json_data[0]['results']):
      combined_values = []
      for section, data in result.items():
        for column, value in data.items():
          if idx == 0:
            if section == 'metrics':
              headers.append(column)
            else:
              headers.append(f"{section}{column.title()}")
          combined_values.append(value)
      rows.append(combined_values)

    google_df = pd.DataFrame(data=rows, columns=headers)
    return {tab_name: google_df}

  def _extract_google_drive_data(self, api):
    final_tables = {}
    for tab_name, data_list in self.holding.items():
      num_preamble_rows = self.skip_file_preamble(data_list)
      data_list = data_list[num_preamble_rows:]

      rows_without_footer = self.skip_footer_rows(data_list, api)
      data_list = data_list[:rows_without_footer]

      cleaned_data = self.skip_empty_columns(data_list)
      headers, rows = cleaned_data[0], cleaned_data[1:]
      final_tables[tab_name] = pd.DataFrame(data=rows, columns=headers)
    return final_tables

class PlatformLoader(BaseLoader):
  """ Loads data from Customer Data Platforms """
  def load(self):
    pass

class WarehouseLoader(BaseLoader):
  """ Loads data from Customer Data Platforms """
  def load(self):
    pass


""" WarehouseConnector
# With a Loader, we load the data into our system for transforms and queries
# In contrast, when using a Connector, we perform transforms and queries on their system """
