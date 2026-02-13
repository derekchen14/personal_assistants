import random
from collections import Counter

from backend.assets.ontology import agreeable_prefixes
from backend.components.metadata.issues import Concern, metadata_map
from backend.components.engineer import PromptEngineer
from backend.prompts.for_res import insight_response_prompt
from backend.utilities.manipulations import count_to_nl, skip_repeat_token

type_to_string = {'zip': 'zip codes', 'address': 'addresses', 'url': 'URLs', 'general': 'general text',
                    'status': 'statuses', 'phone': 'phone numbers', 'whole': 'whole numbers',
                    'unsupported': 'unsupported values' }
type_to_plural = ['time', 'timestamp', 'day', 'month', 'year', 'street', 'state', 'city', 'currency',
                    'country', 'category', 'decimal', 'email', 'boolean']
concern_map = {'datetime': 'date issues', 'location': 'location issues', 'number': 'numeric outliers', 'text': 'textual anomalies'}

def issue_templates(frame, resolve_flow, world, database):
  # combine the retrieved metadata and use it to fill some templates
  tab_name, col_name = frame.issues_entity['tab'], frame.issues_entity['col']
  col_subtype = frame.properties.get(f"{tab_name}.{col_name}", 'null')

  match resolve_flow.flow_type:
    case 'blank': notification = notify_blanks_available(resolve_flow, col_name, col_subtype)
    case 'concern': notification = notify_concerns_available(resolve_flow, col_name)
    case 'typo': notification = notify_typos_available(resolve_flow, frame, col_name, world, database)
    case 'problem': notification = notify_problems_available(frame, col_name, col_subtype, world, database)

  if len(notification) < 100 and random.random() < 0.4:
    suffix = random.choice(["", " details", " examples"])
    filler = random.choice(["", "the "])
    notification += f" Please see {filler}table for more{suffix}."
  return notification

def no_issues_template(frame, state):
  if len(frame.resolved_rows) > 0:
    col_name, issue_type = frame.issues_entity['col'], frame.issues_entity['flow']
    message = f"I have cleared up all the {issue_type}s in the {col_name} column. "
    message += "Is there anything else you would like to do?"

  else:
    match state.get_dialog_act():
      case '46B': issue_type = 'empty values'
      case '46C': issue_type = 'concerns'
      case '46E': issue_type = 'typos'
      case '46F': issue_type = 'problems'
    message = f"I did not detect any major {issue_type} in the {state.current_tab} table."

  return message

def attach_issue_warning(frame, issue_flow):
  tab_name, col_name = frame.issues_entity['tab'], frame.issues_entity['col']
  col_type = frame.properties[f"{tab_name}.{col_name}"]

  match issue_flow.flow_type:
    case 'concern': issue_type = concern_map.get(col_type, 'issues')
    case 'blank': issue_type = 'nulls or missing values'
    case 'problem': issue_type = 'unsupported data types'
    case 'typo': issue_type = 'possible typos'
  warning = f" However, I did notice some {issue_type} in the {col_name} column which may affect the answer."
  return warning

def notify_concerns_available(flow, col_name):
  counts = {}
  for concern_type in flow.issue_types:
    num_issues = flow.slots[concern_type].level
    if num_issues > 0:
      counts[concern_type] = num_issues

  notification = "There "
  nl_concerns = [size_type_to_nl(count, ctype) for ctype, count in counts.items()]
  notification += PromptEngineer.array_to_nl(nl_concerns, connector='and')

  if len(counts) == 1:  # only one column has concerns
    notification += " in the " + col_name + " column"
  notification += "."
  return notification

def notify_blanks_available(flow, col_name, col_type):
  # I found XX missing emails and YY default emails in the sign_up_email column.
  counts = {}
  for blank_type in flow.issue_types:
    num_issues = flow.slots[blank_type].level
    if num_issues > 0:
      counts[blank_type] = num_issues

  notification = "There "
  parts = []
  for blank_type, size in counts.items():
    nl_size = count_to_nl(size)

    if size == 1:
      parts.append(f"is {nl_size} {blank_type} {col_type}")
    else:
      if col_type in type_to_string:
        parts.append(f"are {nl_size} {blank_type} {type_to_string[col_type]}")
      elif col_type.endswith('y'):
        parts.append(f"are {nl_size} {blank_type} {col_type[:-1]}ies")
      else:
        parts.append(f"are {nl_size} {blank_type} {col_type}s")

  notification += PromptEngineer.array_to_nl(parts, connector='and')
  if len(counts) <= 2:  # only one or two types of blanks
    notification += f" in the {col_name} column."
  else:
    notification += f" for {col_name}."
  return notification

def notify_problems_available(frame, col_name, major, world, database):
  # Get row issues from ShadowDB
  tab_name = frame.issues_entity['tab']
  flow_name = frame.issues_entity['flow']
  issue_df = database.db.shadow.issues[tab_name]
  issue_metadata = world.metadata[flow_name][tab_name]

  # Get issue types for this column
  problem_issues = issue_df[(issue_df['column_name'] == col_name) & (issue_df['issue_type'] == 'problem')]

  minor_counts = Counter()
  for _, row in problem_issues.iterrows():
    subtype = row.get('subtype', '')
    if subtype:
      minor_counts[subtype] += 1
    else:
      minor_counts['problem'] += 1

  if len(minor_counts) == 1:
    minor = list(minor_counts.keys())[0]
    if minor_counts[minor] <= 5:
      notification = f"Most of the entries in the {col_name} column are {type_snippet(major)}, but I also found some {type_snippet(minor)}."
    else:
      notification = f"The {col_name} column is mostly {type_snippet(major)}, but I found some {type_snippet(minor)} too."

  else:
    parts = [f"{count_to_nl(size)} {type_snippet(minor)}" for minor, size in minor_counts.items()]
    notification = "I found "
    notification += PromptEngineer.array_to_nl(parts, connector='and')
    notification += f" in the {col_name} column."

  return skip_repeat_token(notification)

def notify_typos_available(flow, frame, col_name, world, database):
  """ term_count is a dictionary, key is the chosen term, the value is count of similar rows related to that term """
  notification = f"The {col_name} column has "

  # Get typo issues from ShadowDB
  tab_name = frame.issues_entity['tab']
  flow_name = frame.issues_entity['flow']
  issue_df = database.db.shadow.issues[tab_name]

  # Get terms for typo issues in this column
  typo_issues = issue_df[(issue_df['column_name'] == col_name) & (issue_df['issue_type'] == 'typo')]
  term_count = Counter(typo_issues['revised_term'].dropna().values)

  num_groups = len(term_count)
  if num_groups == 1:
    one_term = term_count.keys()[0]
    group_size = term_count[one_term]
    notification += f"one group of potential typos, which contains {group_size} similar terms. "
  else:
    notification += f"{count_to_nl(num_groups)} groups of potential typos. T"
    desc_lines = [f"the '{term}' group contains {count} terms" for term, count in term_count.items()]
    description = PromptEngineer.array_to_nl(desc_lines, connector='and')
    notification += description[1:] + "."

  return notification

def notify_fix_available(flow, col_name):
  notification = f"I can help to fix the {col_name} column. "
  return notification

def notify_connection_available(flow):
  col_desc = PromptEngineer.array_to_nl(flow.slots['target'].values, connector='and')
  notification = f"I can help to connect the {col_desc} columns. "
  return notification

def type_snippet(subtype):
  if subtype in type_to_string:
    return type_to_string[subtype]
  elif subtype in type_to_plural:
    if subtype.endswith('y'):
      return f"{subtype[:-1]}ies"
    else:
      return f"{subtype}s"
  else:
    return f"{subtype} type"

def confirm_identify_issue(frame, context, issue_flow):
  action_turn = context.find_action_by_name('ISSUE')
  technique = action_turn.target
  template = random.choice(agreeable_prefixes)
  IssueClass = metadata_map[issue_flow.flow_type]

  if technique == 'ignore':
    template += "I will ignore "
    timing = random.choice(["moving forward", "in the future"])
    template += f"those {issue_flow.name()}s {timing}."

  elif technique in ['remove', 'modify']:
    template += updating_response(frame, issue_flow, IssueClass, technique)
  else:  # merge similar terms
    template += merging_sim_terms(issue_flow, IssueClass)

  if not issue_flow.completed:
    suffix = random.choice(["would you like to do with the remaining rows", "should we do with the rest"])
    template += f" \nWhat {suffix}?"
  return template

def size_type_to_nl(size, itype):
  nl_size = count_to_nl(size)
  if size == 1:
    template = "is one row with "
  else:
    template = f"are {nl_size} rows with "
  template += Concern.type_to_nl(itype, size, 'article')
  return template

def notify_sparsity_available(issues):
  # To be used when a column is sparsely populated
  column_name, rows_present = issues['empty']
  description = f"The {column_name} column is "

  if rows_present == 0:
    description += random.choice(["completely ", "entirely ", "all "])
    description += "empty."
  else:
    description += "mostly empty, except for "
    if rows_present == 1:
      value = issues['empty'][1]
      description += f"{value}."
    elif rows_present == 2:
      values = issues['empty'][1:]
      description += f"{values[0]} and {values[1]}."
    else:
      description += f"{rows_present} values. "
      description += "Please see table for more details."

  return description

def metric_templates(flow, markdown_df):
  if flow.stage == 'time-range':
    metric_res = "What time range are you interested in?"
  else:
    metric_res = "To Be Implemented"
  return metric_res

def pivot_templates(flow):
  tab_name = flow.slots['target'].values[0]['tab']
  response = f"I have created a new '{tab_name}' table for you. "
  if flow.slots['operation'].filled:
    operations = flow.slots['operation'].values
    response += f"I have {operations[0]}. "

  suffixes = ["What do you think?", "How does that look?", "Please take a look."]
  response += random.choice(suffixes)
  return response

def merging_sim_terms(resolve_flow, IssueClass):
  chosen_term = resolve_flow.chosen_term
  similar_terms = [term for term in resolve_flow.all_terms if term != chosen_term]

  source_nl = PromptEngineer.array_to_nl(similar_terms, connector='and')
  if len(similar_terms) == 1:
    merge_res = f"{source_nl} has been merged into '{chosen_term}'."
  else:
    merge_res = f"{source_nl} have been merged into '{chosen_term}'."
  return merge_res

def updating_response(frame, flow, IssueClass, technique):
  num_changes = len(frame.resolved_rows)
  # Get remaining issues count from ShadowDB
  from backend.components.metadata import MetaData
  tab_name, col_name = frame.issues_entity['tab'], frame.issues_entity['col']
  # Note: This function needs database access to get remaining issues count
  # For now, using 0 as placeholder - this should be passed from calling context
  num_remaining_issues = 0

  if num_changes == 0:
    print(f"Warning: number of resolved {flow.name()}s is empty, but should be positive.")
    itype = flow.issue_types[0]    # just setting a random default
    num_changes = num_remaining_issues  # smoothes over the error
  else:
    itype = frame.issues_entity['flow']

  if technique == 'remove':
    verb = random.choice(["removed", "deleted"])
  elif technique == 'modify':
    verb = random.choice(["updated", "changed", "modified"])
  elif technique == 'interpolate':
    verb = random.choice(["interpolated", "filled in"])
  template = f"I have {verb} "

  nl_changes = count_to_nl(num_changes)
  if num_remaining_issues == 0:
    if flow.turns_taken > 1:
      template += "all the remaining rows "
    else:
      template += "all the rows "
  elif num_changes == 1:
    template += f"the {nl_changes} row "
  else:
    template += f"the {nl_changes} rows "

  template += f"with {itype}s."
  # if num_remaining_issues > 0:
  #   natural_lang_itype = IssueClass.type_to_nl(itype, num_changes, 'article')
  #   template += f"with {natural_lang_itype}."
  return template

def stage_based_templates(flow):
  response = ""   # default response, which means the agent will not say anything

  if flow.stage == 'pick-tab-col':
    if len(flow.slots[flow.entity_slot].values) > 0:
      if len(flow.slots[flow.entity_slot].values[0]['col']) > 0:
        # Full match, we have a table and column
        found_columns = [entity['col'] for entity in flow.slots[flow.entity_slot].values]
        col_string = PromptEngineer.array_to_nl(found_columns, connector='and')
        response = f"I am considering the {col_string} columns for "
        match flow.flow_type:
          case 'dedupe': response += "removing duplicates"
          case 'merge': response += "merging together"
          case 'join': response += "joining the two tables together"
          case 'format': response += "standardization"

      else:
        # Partial match, we have a table but no column
        response = "Which columns would you like to "
        match flow.flow_type:
          case 'dedupe': response += "use to remove duplicates?"
          case 'merge': response += "merge together?"
          case 'join': response += "use to align the two tables together?"
          case 'format': response += "standardize into a single format?"
    else:
      # No match, we have no table nor column
      match flow.flow_type:
        case 'dedupe': response = "Which columns would you like to use to remove duplicates?"
        case 'merge': response = "Which columns would you like to merge together?"
        case 'join': response = "Which columns are most useful for aligning the different entries?"
        case 'format': response = "Which column are you trying to reformat?"

    if flow.flow_type == 'join':
      prefix = "Since there isn't a foreign key for joining the two tables, we need to figure out how to align them. "
      response = prefix + response

  elif flow.stage == 'merge-style':
    column_names = [entity['col'] for entity in flow.slots[flow.entity_slot].values]
    col_string = PromptEngineer.array_to_nl(column_names, connector='and')

    if flow.flow_type == 'dedupe':
      if len(column_names) == 1:
        response = f"While two rows may have the same value in the {col_string} column, "
      else:
        response = f"While two rows may have the same values in the {col_string} columns, "
      response += "they may have conflicting values in the other columns. When this happens, how do you want to determine which row to keep?"
    elif flow.flow_type == 'merge':
      response = f"How would you like to merge the values in the {col_string} columns?"

  elif flow.stage == 'checkbox-opt':
    match flow.flow_type:
      case 'join': response = "Which columns do you want to have in the final, integrated table?"
      case 'validate': response = "Which terms are considered valid in the selected column?"

  elif flow.stage == 'confirm-suggestion':
    # only exists for validate flow at the moment; guaranteed to have 3 to 7 corrections
    response = "I am planning to convert:\n"
    for before, after in flow.slots['mapping'].value.items():
      response += f" - {before} --> {after}\n"
    response += "Do these look right?"
    if flow.interjected:
      col_name = flow.slots['source'].values[0]['col']
      response = f"I have detected some similar terms in '{col_name}' which should be combined. " + response

  elif flow.stage == 'combine-cards':
    if flow.tracker.cardset_index == 1:
      prefixes = ['Great', 'Awesome', 'Wonderful', 'Fantastic']
      prefix = random.choice(prefixes)
      if flow.tracker.batch_number == 1:
        if flow.flow_type == 'dedupe':
          response = f"{prefix}, we found some potential duplicates where the target values line up, but the remaining values may be different. "
          response += "Let me know if these are duplicate rows that should be merged together, or similar but distinct rows that should be kept apart."
        else:  # flow type is table
          response = f"{prefix}, we will now review some potential matches between the two tables. "
          response += "Let me know if these are equivalent entries that should be merged together, or different entries that should be kept apart."
      else:
        response = f"{prefix}, let's go through another batch of potential duplicates. These examples will help teach me how to handle the remaining rows!"

  elif flow.stage == 'combine-progress':
    response = "Thanks for your input! Given my current confidence, "
    response += "would you like me to deal with the remaining conflicts automatically, or would it be better to review a few more?"
  return response

def completion_response(frame, flow):
  response = ''
  num_affected, total_rows = frame.properties.get('row_counts', (0, 0))

  if flow.name() == 'dedupe':
    if num_affected == 0:
      tab_name = flow.slots['removal'].table_name()
      response = f"No duplicate rows were found in the {tab_name} table."
    else:
      response = f"{num_affected} duplicate rows have been successfully removed, leaving {total_rows} unique rows."

  elif flow.name() == 'impute':
    if num_affected == 0:
      tab_name = flow.slots['target'].table_name()
      response = f"No blank rows were found in the {tab_name} table."
    else:
      col_name = flow.slots['target'].values[0]['col']
      response = f"{num_affected} blank rows in the {col_name} column have been successfully filled in."

  elif flow.name() == 'format':
    col_name = flow.slots['source'].values[0]['col']
    response = f"Certainly, the entire {col_name} column has been successfully reformatted."
    # if num_affected < 0:
    #   response = f"Certainly, the entire {col_name} column has been successfully reformatted."
    # elif num_affected == 0:
    #   response = f"We found no rows in the {col_name} column that needed to be reformatted."
    # else:
    #   num_revised = sum(1 for res in flow.tracker.results if res['revised'])
    #   num_unresolved = len(flow.tracker.results) - num_revised
    #   response = f"{num_revised} rows in the {col_name} column have been successfully changed"
    #   response += f" to match the '{flow.slots['format'].value}' format."
    #   if num_unresolved > 0:
    #     response += f" However, {num_unresolved} rows were left unchanged because they could not be resolved."

  elif flow.name() == 'validate':
    response = validate_completion(flow, num_affected, total_rows)

  return response

def validate_completion(flow, num_affected, total_unique_rows):
  # usually 'total_rows' represents total remaining rows, but we use it here to represent total unique values
  col_name = flow.slots['source'].values[0]['col']
  if flow.interjected and total_unique_rows > 0:
    result_terms = f"{total_unique_rows} unique terms"
  else:
    result_terms = "valid terms"
  response = f"{num_affected} rows have been corrected, leaving only {result_terms} in the '{col_name}' column."

  corrections = [f"{before} to {after}" for before, after in flow.slots['mapping'].value.items()]
  num_invalid_terms = len(corrections)
  correction_str = PromptEngineer.array_to_nl(random.sample(corrections, k=min(4, num_invalid_terms)), connector='and')

  if num_invalid_terms > 4:
    response += f" Examples of corrections include changing {correction_str}."
  elif num_invalid_terms > 0:
    response += f" I changed {correction_str}."

  return response

def insert_clarification(flow):
  templates = ["What do you think we should name the new column?",
               "What should the new column be called?",
               "Can you clarify what column I should insert?"]
  return random.choice(templates)

def update_clarification(flow):
  if flow.slots['source'].filled and not flow.slots['target'].filled:
    templates = ["What do you think we should name the new column?",
                 "What should the new value be called?",
                 "Can you clarify what the new value should be?"]
  elif not flow.slots['source'].filled and flow.slots['target'].filled:
    templates = ["Where table and column are we using?",
                 "What column are we basing our changes on?",
                 "Can you clarify what column I should update?"]
  else:
    templates = ["I didn't get that, what are we trying to update?",
                 "What is it that we're trying to clean up here?",
                 "Can you clarify what you want to update?"]
  return random.choice(templates)

def delete_clarification(flow):
  templates = ["What do you think we should delete from the table?",
               "What column or row are you trying to remove?",
               "Can you clarify what column I should delete?"]
  return random.choice(templates)

def insert_action_template(flow):
  prefix = random.choice(agreeable_prefixes)
  col_name = flow.slots['target'].values[0]['col']
  action = random.choice(['created', 'added', 'inserted'])
  response = f"{prefix}I've {action} the {col_name} column."
  return response

def delete_action_template(flow):
  prefix = random.choice(agreeable_prefixes)
  action = random.choice(['deleted', 'removed', 'eliminated'])

  columns = [entity['col'] for entity in flow.slots['removal'].values]
  col_string = PromptEngineer.array_to_nl(columns, connector='and')
  first_row = str(flow.slots['removal'].values[0]['row'])

  if first_row == 'all':
    response = f"{prefix}I've {action} the {col_string} columns."
  elif len(columns) > 3 and "=" not in first_row:
    response = f"{prefix}I've {action} the {first_row} row."
  else:
    response = f"{prefix}content based on {col_string} has been {action}."
  return response

def merge_columns_template(flow):
  tab_name = flow.slots['target'].values[0]['tab']
  col_name = flow.slots['target'].values[0]['col']
  response = f"The {col_name} column has been successfully created in the {tab_name} table."
  return response

def split_column_template(flow):
  first_entity = flow.slots['source'].values[0]
  col_name, tab_name = first_entity['col'], first_entity['tab']
  target_columns = [entity['col'] for entity in flow.slots['target'].values]
  if len(target_columns) > 5:
    num_cols = len(target_columns)
    response = f"The {col_name} column has been successfully split into {num_cols} columns in the {tab_name} table."
  else:
    col_desc = PromptEngineer.array_to_nl(target_columns, connector='and')
    response = f"I have created {col_desc} columns from the {col_name} column. How does that look?"
  return response

def join_tables_template(flow):
  new_tab_name = flow.slots['target'].values[0]['tab']
  source_tabs = [entity['tab'] for entity in flow.slots['source'].values if entity['ver']]
  tab_string = PromptEngineer.array_to_nl(list(set(source_tabs)), connector='and')
  match_size, total_size = flow.group_sizes['overlap'], flow.group_sizes['total']
  response = f"Your data has been successfully integrated! The new {new_tab_name} tab contains {total_size} total rows, "

  if total_size == match_size:
    response += f"containing all the rows from {tab_string}."
  else:
    response += f"where {match_size} of those rows are merged entries from {tab_string}."
  return response

def append_rows_template(flow):
  target_tab = flow.slots['target'].values[0]['tab']
  source_tables = list(set([entity['tab'] for entity in flow.slots['source'].values]))
  source_str = PromptEngineer.array_to_nl(source_tables, connector='and')
  response = f"The {source_str} tables have been successfully appended together to form the {target_tab} table."
  return response

def complete_staging_template(frame):
  tab_name = frame.raw_table
  message = f"I have just created a new '{tab_name}' table for you. "
  suffixes = ["What do you think?", "How does that look?", "What would you like to do next?"]
  message += random.choice(suffixes)
  return message

def create_staging_template(current_flow, dax):
  source_cols = [entity['col'] for entity in current_flow.slots['source'].values]
  target_cols = [entity['col'] for entity in current_flow.slots['target'].values]
  sources = PromptEngineer.array_to_nl(source_cols, connector='and')
  targets = PromptEngineer.array_to_nl(target_cols, connector='and')

  message = "In order to better understand the data, "
  match dax:
    case '005': message += f"I'm going to create a new '{targets}' column based on '{sources}', "
    case '05C': message += f"I'm going to calculate '{targets}' based on the {sources} columns, "
    case '5CD': message += f"I'm going to split the {sources} column into {targets}, "
    case '055': message += f"I want to create the {targets} columns, "

  requests = ['is that okay?', 'is that acceptable?', 'is that alright?', 'does that sound okay?']
  message += random.choice(requests)
  return message

def confirm_plan_template(frame, flow):
  if flow.name() == 'resolve':
    nl_desc = {
      'problem': 'resolve data type problems',
      'blank': 'deal with empty or null values',
      'concern': 'uncover outliers and anomalies',
      'typo': 'highlight potential typos',
      'validate': 'ensure that all terms are valid',
      'format': 'format the values to follow a standard pattern',
      'dedupe': 'remove duplicate entries'
    }
    response = "I can help to "
    phrases = [nl_desc[proposal] for proposal in flow.slots['proposal'].options]
    response += PromptEngineer.array_to_nl(phrases, connector='or')
    if flow.slots['source'].filled and len(flow.slots['source'].values) == 1:
      col_name = flow.slots['source'].values[0]['col']
      response += f" in the {col_name} column. "

  elif flow.name() == 'connect':
    response = "I have crafted a plan to connect the data."
  else:
    response = "I have crafted a plan to analyze the data."

  follow_up = ["What would you like to do?", "How do you want to proceed?",
               "Which one should we start with?", "Can you confirm that this is what you want?"]
  response += random.choice(follow_up)
  return response

def review_insight_proposal(flow, state):
  if flow.stage.startswith('automatic'):
    response = "It sounds like you want me to search for insights in the data. I can do a better job when "
    response += "you provide more details about what you're looking for. Can you please be more specific?"
  else:
    analysis_type = flow.slots['analysis'].value
    verb = 'perform' if 'analysis' in analysis_type.lower() else 'analyze'
    response = f"It sounds like you want me to {verb} {analysis_type}. "
    if state.ambiguity.present():
      response += f"Before I proceed, I want to clarify: {state.ambiguity.observation}"
    else:
      response += "Is that correct?"
  return response

def ask_for_user_approval(flow, state):
  # we are working with the natural language plan rather than the structured, flow-based dicts
  plan = '\n'.join([f"  {step}" for step in flow.scratchpad])

  if flow.stage.startswith('automatic'):
    response = f"These are the types of analysis that I plan to perform: \n{plan}\n"
    response += "This will take some time though. Are you sure you want to proceed?"
  else:
    if state.ambiguity.present():
      response = f"Here's the revised plan based on your feedback: \n{plan}\n"
    else:
      response = f"Here's the first draft of the plan: \n{plan}\n"

    suffixes = ["What do you think?", "Do you approve?", "Does this sound good?", "Anything you would change or add?"]
    response += random.choice(suffixes)
  return response

def insight_completion(context, insight_flow, frame):
  if insight_flow.clarify_attempts < 0:
    response = "I'm sorry, I'm still not sure how you want me to analyze the data and I do not know how to proceed."
    response += "Please restate your request in a different way and possibly prepare the data first."
    return response, ''
  else:
    original_turn = context.find_turn_by_id(clear_bookmark=True)
    user_utt = original_turn.utt(for_api=False, as_dict=True)
    analysis_name=insight_flow.slots['analysis'].value

    summaries = [f"  * {summary['text']}" for summary in insight_flow.scratchpad]
    convo_history = context.compile_history()
    markdown = PromptEngineer.display_preview(frame.get_data())
    prompt = insight_response_prompt.format(analysis_name=analysis_name, utterance=user_utt['text'],
                                            observations='\n'.join(summaries), history=convo_history, table_md=markdown)
    return '', prompt