import pandas as pd
from collections import defaultdict
from backend.assets.ontology import relation_map
from datetime import datetime

from backend.components.engineer import PromptEngineer
from backend.components.state import DialogueState
from backend.modules.flow import flow_selection

def build_query_labels(code_data, valid_col_dict):
  labels = {'intent': 'Analyze', 'dax': '001', 'entities': [], 'operations': []}

  modified_query = code_data.code
  for tab_name, columns in valid_col_dict.items():
    if tab_name in modified_query:
      for col_name in columns:
        if col_name in modified_query:
          labels['entities'].append({'tab': tab_name, 'col': col_name, 'ver': True})

  if 'WHERE' in modified_query:
    labels['operations'].append(f"filter by WHERE clause")
  if 'GROUP BY' in modified_query:
    labels['operations'].append(f"group by GROUP BY clause")
  if 'ORDER BY' in modified_query:
    labels['operations'].append(f"sort by ORDER BY clause")

  labels['language'] = code_data.language
  labels['thought'] = modified_query
  return labels

def build_measure_labels(metric_data, state):
  measure_flow = state.get_flow(flow_type='measure')
  metric = measure_flow.slots['metric'].formula
  operations = []

  if metric_data.stage == 'build-variables':
    verified_vars = metric_data.variables
    # store the verified tables, columns, and relations into the measure flow
    name_str = metric.get_name(case='title') + f" ({metric.name})"
    variables_str = ' and '.join([var.name for var in metric.variables])
    main_op = f"calculate {name_str} which is composed of the {variables_str} variables"
    operations.append(main_op)

    for variable in metric.variables:
      variable_op = f"relevant columns for calculating {variable.name} include the "
      for idx, clause in enumerate(verified_vars[variable.name]):
        match idx:
          case 0: variable_op += f"{clause.col} column"
          case 1: variable_op += f" as well as {relation_map[clause.rel]} the {clause.col} column"
          case _: variable_op += f" and {relation_map[clause.rel]} the {clause.col} column"
        variable.add_clause(clause.tab, clause.col, clause.rel, clause.ver)
      variable_op += f" from the {clause.tab} table"
      operations.append(variable_op)

      variable.verified = True
      for entity in variable.clauses.values():
        measure_flow.slots['source'].add_one(**entity)

  elif metric_data.stage == 'time-range':
    time_info = metric_data.time
    time_slot = measure_flow.slots['time']

    if time_info['selected'] == 'custom':
      from_date = datetime.strptime(time_info['from_date'], '%Y-%m-%d').date()
      to_date = datetime.strptime(time_info['to_date'], '%Y-%m-%d').date()
      time_slot.date_range['from'] = from_date
      time_slot.date_range['to'] = to_date
      time_slot.time_len = abs((from_date - to_date).days)
      time_slot.value = 'day'
    elif time_info['selected'] == 'all':
      time_slot.time_len = -1
      time_slot.value = 'all'
    else:
      time_length, time_unit = time_info['selected'].split('-')
      time_slot.time_len = float(time_length)
      time_slot.value = time_unit
    time_slot.verified = True

    if time_slot.value == 'all':
      time_op = f"calculate the {metric.name} metric over all available data"
    else:
      time_op = f"filter time by {time_slot.range_to_nl()}"
    operations.append(time_op)

  labels = {'intent': 'Analyze', 'dax': '002', 'entities': measure_flow.entity_values(), 'operations': operations}
  labels['metric'] = metric.name
  return labels, state

def build_visualize_labels(figure_data, state):
  if len(state.entities) > 0:
    entities = state.entities
  else:
    entities = [{'tab': state.current_tab, 'col': figure_data.column, 'ver': False}]

  ops = ["plot a new chart or figure"]
  labels = {'intent': 'Visualize', 'dax': '003', 'entities': entities, 'operations': ops}
  return labels, state

def store_merge_settings(style_name, style_setting, flow):
  settings_slot = flow.slots['settings']
  settings_slot.value['detail'] = style_setting

  match style_name:
    case 'order': settings_slot.value['boolean'] = style_setting == 'first' # (vs. 'last')
    case 'time': settings_slot.value['boolean'] = style_setting == 'earlier' # (vs. 'later')
    case 'binary': settings_slot.value['boolean'] = style_setting == 'positive' # (vs. 'negative')
    case 'divide': settings_slot.value['boolean'] = style_setting == 'numerator' # (vs. 'denominator')
    case 'subtract': settings_slot.value['boolean'] = style_setting == 'first' # (vs. 'second')
    case 'size': settings_slot.value['boolean'] = style_setting == 'minimum' # (vs. 'maximum')
    case 'power': settings_slot.value['boolean'] = style_setting == 'base' # (vs. 'exponent')
    case 'log': settings_slot.value['boolean'] = style_setting == 'base' # (vs. 'exponent')
    case 'length': settings_slot.value['boolean'] = style_setting == 'longer' # (vs. 'shorter')
    case 'alpha': settings_slot.value['boolean'] = style_setting == 'A to Z' # (vs. 'Z to A')
  return flow

def build_validate_labels(clean_data, state):
  validate_flow = state.get_flow(flow_type='validate')
  operations = []

  if clean_data.stage == 'pick-tab-col':
    source = clean_data.source_entity
    validate_flow.slots['source'].add_one(source.tab, source.col, ver=True)
    validate_flow.is_uncertain = False
    pick_op = f"apply data validation to the {source.col} column in the {source.tab} table is accurate"
    operations.append(pick_op)

  elif clean_data.stage == 'checkbox-opt':
    valid_terms = [term for term in clean_data.checked]
    validate_flow.slots['terms'].values = valid_terms
    validate_flow.slots['terms'].verified = True
    checkbox_op = f"compare values to ensure all rows only contains valid terms: {', '.join(valid_terms)}"
    operations.append(checkbox_op)

  elif clean_data.stage == 'choose-terms':
    # extract the chosen term and similar terms or typos from the user interaction
    term_group = clean_data.term_group

    validate_flow.chosen_term = term_group.chosen  # string
    validate_flow.all_terms = term_group.similar   # list of strings
    # save the entity where the terms are found and mark them as verified
    entity = term_group.source
    validate_flow.slots['source'].add_one(entity.tab, entity.col, ver=True)

    if len(validate_flow.all_terms) == 0:
      entities = validate_flow.entity_values()
      operations = [f"ignore {term_group.chosen} terms in the {entity.col} column"]
      labels = {'intent': 'Converse', 'dax': '00F', 'entities': entities, 'operations': operations}
      return labels, state
    else:
      simterm_with_quotes = [f"'{term}'" for term in validate_flow.all_terms if term != term_group.chosen]
      similar_desc = PromptEngineer.array_to_nl(simterm_with_quotes, 'and')
      operation = f"update {similar_desc} to '{term_group.chosen}' in {entity.col} column"
    operations.append(operation)

  labels = {'intent': 'Clean', 'dax': '36D', 'entities': validate_flow.entity_values(), 'operations': operations}
  return labels, state

def remove_duplicates_labels(merge_data, state):
  flow = state.get_flow(flow_type='dedupe')
  active_table = None
  operations = []

  if merge_data.stage == 'pick-tab-col':
    for entity in merge_data.selected:
      certificate = {'tab': entity.tab, 'col': entity.col, 'ver': entity.ver}
      flow.slots['removal'].add_one(**certificate)
    if flow.slots['removal'].check_if_filled():
      flow.is_uncertain = False
    flow.slots['removal'].drop_unverified()

    active_table = flow.table_labels(first_only=True)
    col_string = ', '.join(flow.column_labels())
    pick_op = f"merge duplicate rows from {active_table} table based on {col_string} columns"
    operations.append(pick_op)

  elif merge_data.stage == 'merge-style':
    style_name = merge_data.style['name']
    flow.slots['style'].assign_one(style_name)

    style_setting = merge_data.style['setting']
    style_op = f"compare rows using the {style_name} style"
    flow = store_merge_settings(style_name, style_setting, flow)
    if len(style_setting) > 0:
      style_op += f" and {style_setting} setting"
    operations.append(style_op)
    # mark flow as complete when we know the merge style since we aren't doing fuzzy matching
    if style_name != 'question':
      flow.slots['confidence'].level = 1.0

  elif merge_data.stage == 'combine-cards':
    cardset_result = {
      'retain': merge_data.chosen['retain'], 'retire': merge_data.chosen['retire'],
      'resolution': merge_data.resolution, 'reviewed': True
    }
    flow.tracker.results.append(cardset_result)

    if merge_data.resolution == 'merge':
      operation = "merge the rows by removing the duplicates"
    elif merge_data.resolution == 'separate':
      operation = "keep the rows separate since they are not duplicates"
    elif merge_data.resolution == 'back':
      operation = "move back to the previous step"
    operations.append(operation)

  elif merge_data.stage == 'combine-progress':
    if merge_data.method == 'automatic':
      flow.slots['confidence'].level = 1.0
      auto_op = "apply a confidence score of 100%"
      operations.append(auto_op)
    elif merge_data.method == 'manual':
      confidence_level = flow.slots['confidence'].level
      manual_op = f"apply a confidence score of {confidence_level}"
      operations.append(manual_op)

  labels = {'intent': 'Clean', 'dax': '7BD', 'entities': flow.entity_values(), 'operations': operations}
  return labels, state

def merge_columns_labels(merge_data, state):
  flow = state.get_flow(flow_type='merge')
  active_table = None
  operations = []

  if merge_data.stage == 'pick-tab-col':
    flow.slots['source'].drop_unverified()
    for entity in merge_data.selected:
      certificate = {'tab': entity.tab, 'col': entity.col, 'ver': entity.ver}
      flow.slots['source'].add_one(**certificate)
    if flow.slots['source'].check_if_filled():
      flow.is_uncertain = False

    flow.slots['target'].drop_unverified()
    if flow.slots['target'].filled:
      target_col = flow.slots['target'].values[0]['col'] + ' '
    else:
      target_col = ''

    active_table = flow.table_labels(first_only=True)
    col_string = ', '.join(flow.column_labels())
    pick_op = f"merge {col_string} columns together to form a new {target_col}column in the {active_table} table"
    operations.append(pick_op)

  elif merge_data.stage == 'merge-style':
    flow.slots['target'].drop_unverified()

    style_name = merge_data.style['name']
    style_setting = merge_data.style['setting']
    flow.slots['method'].value = style_name  # allows for custom assignment

    style_op = f"merge column together using the {style_name} method"
    if len(style_setting) > 0:
      style_op += f" and {style_setting} setting"
      flow = store_merge_settings(style_name, style_setting, flow)
    operations.append(style_op)

  labels = {'intent': 'Transform', 'dax': '05C', 'entities': flow.entity_values(), 'operations': operations}
  return labels, state

def split_column_labels(merge_data, state):
  split_flow = state.get_flow(flow_type='split')
  operations = []

  if merge_data.stage == 'pick-tab-col':
    source = merge_data.source_entity
    split_flow.slots['source'].add_one(source.tab, source.col, ver=True)
    split_flow.is_uncertain = False
    pick_op = f"split the {source.col} column in the {source.tab} table into multiple columns"
    operations.append(pick_op)

  elif merge_data.stage == 'split-style':
    split_flow.slots['target'].drop_unverified()
    for entity in merge_data.target_entities:
      certificate = {'tab': entity.tab, 'col': entity.col, 'ver': entity.ver}
      split_flow.slots['target'].add_one(**certificate)
    split_flow.slots['exact'].assign_one(merge_data.delimiter)       # string of how to split the columns

    targets = split_flow.column_labels()
    style_name = split_flow.slots['exact'].term
    style_op = f"split into {len(targets)} columns using the {style_name} delimiter"
    operations.append(style_op)

  labels = {'intent': 'Transform', 'dax': '5CD', 'entities': split_flow.entity_values(), 'operations': operations}
  return labels, state

def join_tables_labels(merge_data, state):
  flow = state.get_flow(flow_type='join')
  operations = []

  if merge_data.stage == 'pick-tab-col':
    for entity in merge_data.selected:
      certificate = {'tab': entity.tab, 'col': entity.col, 'ver': entity.ver}
      flow.slots['source'].add_one(**certificate)
    if flow.slots['source'].check_if_filled():       # might not be filled since we need 2+ entities
      flow.is_uncertain = False
    flow.slots['source'].drop_unverified()
    flow.slots['target'].drop_unverified()

    current_tabs = flow.table_labels()
    left_columns = [ent['col'] for ent in flow.slots['source'].values if ent['tab'] == current_tabs[0]]
    right_columns = [ent['col'] for ent in flow.slots['source'].values if ent['tab'] == current_tabs[1]]
    table_op = f"merge data from {current_tabs[0]} and {current_tabs[1]} tables into a new integrated table"
    left_op = f"apply the {', '.join(left_columns)} columns from the {current_tabs[0]} table"
    right_op = f"apply the {', '.join(right_columns)} columns from the {current_tabs[1]} table"
    operations.extend([table_op, left_op, right_op])

  elif merge_data.stage == 'checkbox-opt':
    flow.slots['target'].drop_unverified()
    new_tab_name = merge_data.support
    for col_name in merge_data.checked:
      flow.slots['target'].add_one(new_tab_name, col_name, True)
    checkbox_op = f"move {len(flow.slots['target'].values)} columns into the new {new_tab_name} table"
    operations.append(checkbox_op)

  elif merge_data.stage == 'combine-cards':
    cardset_result = {'retain': [], 'retire': [], 'resolution': merge_data.resolution, 'reviewed': True}
    if merge_data.resolution == 'merge':
      cardset_result['retain'] = merge_data.chosen['left']
      cardset_result['retire'] = merge_data.chosen['right']
      operation = 'merge the right card into the left card'
    elif merge_data.resolution == 'separate':
      cardset_result['retain'] = merge_data.chosen['left'] + merge_data.chosen['right']
      operation = 'split the left and right cards to keep them separate'
    flow.tracker.results.append(cardset_result)
    operations.append(operation)

  elif merge_data.stage == 'combine-progress':
    if merge_data.method == 'automatic':
      flow.slots['confidence'].level = 1.0
      auto_op = "apply a confidence score of 100%"
      operations.append(auto_op)
    elif merge_data.method == 'manual':
      confidence_level = flow.slots['confidence'].level
      manual_op = f"apply a confidence score of {confidence_level}"
      operations.append(manual_op)

  labels = {'intent': 'Transform', 'dax': '05A', 'entities': flow.entity_values(), 'operations': operations}
  return labels, state

def set_state_columns(state, prev_state, payload, valid_col_dict, col_to_tab):
  # update the entities stored in the state with the verified columns
  if state.dax == '002' and payload.stage == 'build-variables':
    state.entities = [entity.dict() for variable in payload.variables.values() for entity in variable]
    state.thought = prev_state.thought

  elif state.dax == '46D':
    current_ent = state.entities[0]
    col_name = payload.column
    if col_name != current_ent['col']:
      state.entities[0]['col'] = col_name
      if col_name in valid_col_dict[current_ent['tab']]:
        state.entities[0]['ver'] = True
      else:
        # use col_to_tab as a backup since it may not be accurate
        target_tab = col_to_tab[col_name]
        state.entities[0]['tab'] = target_tab

  return state

def command_flow(context, labels, last_state, valid_col_dict):
  state = DialogueState.from_dict(labels, last_state.current_tab)
  state.flow_stack = last_state.flow_stack.copy()

  dax = state.get_dialog_act('hex')
  active_flow = flow_selection[dax](valid_col_dict)
  state.flow_stack.append(active_flow)
  state.command_type = labels['language']
  state.thought = labels['thought']

  state.has_issues = last_state.has_issues
  state.has_staging = last_state.has_staging
  state.turn_id = context.recent[-1].turn_id
  state.slices = last_state.slices
  return state
