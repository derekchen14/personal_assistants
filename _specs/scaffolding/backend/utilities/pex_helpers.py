import re
import pandas as pd
import calendar

from backend.modules.flow import flow_selection
from backend.prompts.mixins.for_analyze import query_to_visual_prompt, proactive_validation_prompt
from backend.components.engineer import PromptEngineer

def count_tab_cols(entities):
  first_tab_name = entities[0]['tab']
  has_one_table = all([ent['tab'] == first_tab_name for ent in entities])
  num_columns = len([ent['col'] for ent in entities if ent['tab'] == first_tab_name])
  return has_one_table, num_columns, first_tab_name

def get_variable_type(var):
  if 'aggregation' in var or 'agg' in var:
    return 'clause'
  if 'relation' in var:
    return 'expression'
  return None

def nl_time_range(frame):
  # Convert time ranges in graphs into natural language for better readability on the graph
  # For example '1' -> 'January', 9.0 -> 'September', or 3 -> 'Wednesday'
  df = frame.get_data()
  use_abbreviation = df.shape[0] > 7

  for col_name in df.columns:
    subtype = frame.properties.get(f'temp.{col_name}', '')

    if subtype == 'month' or (subtype == 'id' and 'month' in col_name.lower()):
      names = calendar.month_abbr if use_abbreviation else calendar.month_name
      df[col_name] = df[col_name].fillna(0).astype(int).apply(lambda x: names[x])
    elif subtype == 'week' or (subtype == 'id' and 'week' in col_name.lower()):
      names = calendar.day_abbr if use_abbreviation else calendar.day_name
      offset = 0 if 0 in df[col_name].unique() else -1
      df[col_name] = df[col_name].fillna(0).astype(int).apply(lambda x: names[x + offset])

  return df

def clauses_match(clause1, clause2):
  agg_match = clause1['agg'] == clause2['agg']
  tab_match = clause1['tab'] == clause2['tab']
  col_match = clause1['col'] == clause2['col']
  return agg_match and tab_match and col_match

def has_placeholder(formula_json):
  def recurse_placeholder(node):
    # Check if current node is a placeholder
    if 'relation' in node and node['relation'] == 'placeholder':
      return True
    # If node has variables and isn't a placeholder, check them recursively
    if 'variables' in node:
      return any(recurse_placeholder(var) for var in node['variables'])
    return False

  return recurse_placeholder(formula_json)

def structural_agreement(vars1, vars2):
  if len(vars1) != len(vars2):
    return False

  for var1, var2 in zip(vars1, vars2):
    type1 = get_variable_type(var1)
    type2 = get_variable_type(var2)
    if type1 is None or type2 is None:
      return False

    # Handle expressions recursively
    if type1 == 'expression' or type2 == 'expression':
      if type1 != 'expression' or type2 != 'expression':
        return False
      if var1['relation'] != var2['relation']:
        return False
      if not structural_agreement(var1['variables'], var2['variables']):
        return False
    # Handle clauses
    else:
      if not clauses_match(var1, var2):
        return False

  return True

def review_formula_agreement(formula1, formula2):
  """ Compare two formulas and determine their level of agreement.
  Returns:
    - 'perfect': Formulas are exactly the same
    - 'imperfect': Formulas have same structure but different names
    - 'disagree': Formulas have different structure
  """
  if not isinstance(formula1, dict) or not isinstance(formula2, dict):
    return 'disagree'
  if 'relation' not in formula1 or 'relation' not in formula2:
    return 'disagree'

  if formula1 == formula2:
    return 'perfect'
  elif formula1['relation'] != formula2['relation']:
    return 'disagree'
  elif structural_agreement(formula1['variables'], formula2['variables']):
    return 'imperfect'
  return 'disagree'

def extract_relevant_entities(formula1, formula2, flow):
  # pull out all entities from the formulas and the entity slot
  def extract_recursive(node):
    entities = []
    # Base case: if node has a table and column, it's a clause
    if 'tab' in node and 'col' in node:
      if node['tab'] != 'N/A' and node['tab'] != 'none':
        entity = {'tab': node['tab'], 'col': node['col']}
        entities.append(entity)

    # Recursive case: if node has 'variables', it's an expression
    elif 'variables' in node:
      for var in node['variables']:
        entities.extend(extract_recursive(var))
    return entities

  relevant_entities = []
  for formula in [formula1, formula2]:
    relevant_entities.extend(extract_recursive(formula))
  for entity in flow.slots['source'].values:
    relevant_entities.append(entity)

  return relevant_entities

def sanitize_entities(entities, valid_col_dict):
  """ Try to fix entities that are not in the valid column dictionary, and remove any that are not valid """
  valid_tables = set(valid_col_dict.keys())

  def clean_value(value, valid_set):
    # Try a series of basic cleaning operations
    candidates = [ value.strip(), value.lower(), value.upper(), value.title(),
                   value.replace('_', ' '), value.replace(' ', '_') ]
    for candidate_change in candidates:
      if candidate_change in valid_set:
        return candidate_change
    return None

  sanitized_entities = []
  for entity in entities:
    if entity['tab'] in valid_tables and entity['col'] in valid_col_dict[entity['tab']]:
      sanitized_entities.append(entity)
    else:
      # Clean the table name
      cleaned_table = clean_value(entity['tab'], valid_tables)
      if cleaned_table is None:
        continue
      entity['tab'] = cleaned_table

      # Clean the column name for the validated table
      cleaned_column = clean_value(entity['col'], valid_col_dict[cleaned_table])
      if cleaned_column is None:
        continue
      entity['col'] = cleaned_column

      sanitized_entities.append(entity)
  return sanitized_entities

def attach_issues_entity(flow, frame, state, world):
  top_flow = state.get_flow(allow_interject=True)
  if top_flow.interjected and top_flow.parent_type == 'Detect':
    flow_name = top_flow.name()
    for entity in flow.slots['source'].values:
      tab_name, col_name = entity['tab'], entity['col']
      tab_metadata = world.metadata[flow_name][tab_name]
      issue_df = world.database.db.shadow.issues[tab_name]
      if tab_metadata.issues_exist(issue_df, [col_name]):
        frame.issues_entity = {'tab': tab_name, 'col': col_name, 'row': {}, 'flow': flow_name}
  return frame

def query_rerouting(flow):
    # Determines if re-routing to a different flow through fallbacks is needed
    operations = flow.slots['operation'].values
    contains_grouping = False
    agg_and_filter = 0

    for operation in operations:
      if operation.startswith('group'):
        contains_grouping = True
        agg_and_filter += 1
      elif operation.startswith('aggregate'):
        if 'top' in operation or 'bottom' in operation:
          # limit the number of rows does not count as a critical operation
          agg_and_filter -= 1
        agg_and_filter += 1
      elif operation.startswith('filter'):
        agg_and_filter += 1

    if contains_grouping and agg_and_filter > 3:
      flow.fall_back = '01A'
      return flow, True
    return flow, False

def query_visualization(api, context, flow, frame, world):
  # Determines if displaying a figure through visualize {003} is more appropriate
  if flow.interjected: return flow, world
  num_rows, num_columns = frame.get_data(form='df').shape

  if num_rows > 1  and (num_columns == 2 or num_columns == 3):  # then these columns can serve as the x and y axis
    preview_md = PromptEngineer.display_preview(frame.get_data(), max_rows=16)
    prompt = query_to_visual_prompt.format(history=context.compile_history(), preview=preview_md)

    prediction = PromptEngineer.apply_guardrails(api.execute(prompt), 'json')
    if prediction['convert']:
      flow.fall_back = '003'
      flow.interjected = True
      frame.properties['do_carry'] = True
      frame.properties['converted'] = True
      world.frames.append(frame)
  return flow, world

def proactive_validation(api, context, flow, frame, state, world):
  # Determines if additional cleaning is needed before proceeding to the next flow
  if flow.interjected: return state, world

  num_columns = len(frame.get_data(form='df').columns)
  source_entities = flow.slots['source'].values
  if num_columns > 1 or len(source_entities) > 1:
    return state, world

  convo_history = context.compile_history(look_back=2)  # just agent and user turn
  if any(trigger in convo_history for trigger in ['unique', 'distinct', 'duplicate', 'typo']):
    preview_md = PromptEngineer.display_preview(frame.get_data(), max_rows=32)
    prompt = proactive_validation_prompt.format(history=context.compile_history(), preview=preview_md)

    prediction = PromptEngineer.apply_guardrails(api.execute(prompt), 'json')
    if prediction['has_invalid']:
      stack_on_flow = flow_selection['36D'](world.valid_columns)
      stack_on_flow.interjected = True
      stack_on_flow.slots['source'].add_one(**source_entities[0])

      state.flow_stack.append(stack_on_flow)
      state.store_dacts(dax='36D')     # correct flow is probably Detect(typo) which is {46E}
      state.keep_going = True

      frame.properties['do_carry'] = True
      frame.properties['respond'] = True
      world.frames.append(frame)

  return state, world

def apply_new_pivot_table(underlying_flow, pivot_tab, table_df, max_cols=8):
  """ Replace the source slot-values in the underlying flow with the newly created staging table """
  if len(table_df.columns) <= max_cols:
    # reset the slots within the underlying Detect flow
    ent_slot = underlying_flow.entity_slot
    underlying_flow.slots[ent_slot].values = []
    underlying_flow.slots[ent_slot].tab_cols = []

    for col_name in table_df.columns:
      underlying_flow.slots[ent_slot].add_one(pivot_tab, col_name)
    underlying_flow.slots[ent_slot].active_tab = pivot_tab
  return underlying_flow

def multi_tab_display(entity_dict, dataframe_tables):
  markdown_tables = []
  for tab_name, col_names in entity_dict.items():
    table_df = dataframe_tables[tab_name]
    md_preview = PromptEngineer.display_preview(table_df, col_names, max_rows=32, signal_limit=False)
    markdown_tables.append(md_preview)

  if len(markdown_tables) > 1:
    # Split each table into lines
    table_lines = [table.strip().split('\n') for table in markdown_tables]

    combined = []
    for row_parts in zip(*table_lines):
      cleaned_parts = [part.strip('| ') for part in row_parts]
      combined.append(f"| {' | '.join(cleaned_parts)} |")
    data_preview = '\n'.join(combined)
  else:
    data_preview = markdown_tables[0]

  return data_preview

def gather_unique_clauses(formula_json) -> set:
  # Counts the number of unique clauses in a formula based on table/column combinations
  unique_combinations = set()

  def extract_recursive(node):
    if 'tab' in node and 'col' in node:
      # skip invalid tab-cols such as constants
      if node['tab'] != 'N/A' and node['tab'] != 'none':
        unique_combinations.add((node['tab'], node['col']))

    elif 'variables' in node:
      for var in node['variables']:
        extract_recursive(var)

  extract_recursive(formula_json)
  return unique_combinations

def build_source_string(entities):
  # prepares a string describing the source data for the segmentation prompt
  unique_tables = set(entity['tab'] for entity in entities)

  if len(unique_tables) >= 2:
    source_tabs = PromptEngineer.array_to_nl(list(unique_tables), connector='and')
    source_str = f"{source_tabs} tables"
  elif len(unique_tables) == 1:
    columns = [entity['col'] for entity in entities]
    if len(columns) == 1:
      source_str = f"{columns[0]} column"
    else:
      source_str = f"{PromptEngineer.array_to_nl(columns)} columns"
  else:
    source_str = "[No data]"

  return source_str

def one_off_col_mismatch(table, predicted_properties):
    """
    Attempts to fix one off mismatches between table column names and predicted property keys.
    If there are more mistakes we will not fix them and leave it to a re-run.
    """
    # Quick return if no properties
    if not predicted_properties:
      return predicted_properties
        
    table_cols = list(table.columns)
    pred_cols = list(predicted_properties.keys())
    
    if len(table_cols) == len(pred_cols):  # Same number of columns
      mismatched = 0
      mismatch_idx = -1
      for i, table_col in enumerate(table_cols):
        if table_col != pred_cols[i]: # Different ordering will result in a mismatch
          mismatched += 1
          mismatch_idx = i

      if mismatched == 1: # Only one column is different
        correct_col = table_cols[mismatch_idx]
        wrong_col = pred_cols[mismatch_idx]
        predicted_properties[correct_col] = predicted_properties.pop(wrong_col)
        return predicted_properties
    
    return predicted_properties

def quote_tables(query:str, tab_names:set):
  # Sort by length descending to avoid partial matches
  for table in sorted(tab_names, key=len, reverse=True):
    query = re.sub(fr'(\s|^){table}(\s|$)', fr'\1"{table}"\2', query)
  return query

def create_new_table_name(metric_name, dimension, valid_tables):
  # make a new table name that follows the same format as the other tables as much as possible
  has_upper = False
  has_underscore = False
  has_space = False
  for table_name in valid_tables:
    if any(char.isupper() for char in table_name):
      has_upper = True
    if '_' in table_name:
      has_underscore = True
    if ' ' in table_name:
      has_space = True

  base_name = metric_name
  if has_upper:
    base_name = base_name.title()
  else:
    base_name = base_name.lower()

  if has_underscore:
    base_name = base_name.replace(' ', '_')
  elif has_space:
    base_name = base_name.replace('_', ' ')
  else:
    base_name = base_name.replace(' ', '')

  if base_name in valid_tables:
    if has_underscore:
      base_name += f'_by_{dimension}'
    else:
      base_name += f' by {dimension}'

  return base_name