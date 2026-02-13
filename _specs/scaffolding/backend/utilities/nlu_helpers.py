import torch
from sentence_transformers import util
import Levenshtein as lev

from backend.assets.ontology import valid_operations
from backend.components.engineer import PromptEngineer
from backend.modules.flow import flow_selection
from backend.prompts.for_nlu import split_symbol_prompt, select_operations_prompt, visualize_operations_prompt

def find_nearest_lexical(candidate, options):
  # Calculate the Levenshtein distance to each valid table
  distances = [(lev.distance(candidate, opt), opt) for opt in options]
  # Find the valid table with the smallest distance
  min_dist, best_match = min(distances, key=lambda x: x[0])
  # if distance exceeds the candidate size, that means there's no overlap
  if min_dist >= len(candidate):
    best_match = None
  return best_match

def find_nearest_semantic(cand_tensor, options, embedder, top_k=-1):
  # Calculate the semantic match to each valid column option
  opt_tensors = embedder.encode(options, convert_to_tensor=True)  
  cos_scores = util.cos_sim(cand_tensor, opt_tensors)[0]

  if top_k > 0:
    top_scores, top_indexes = torch.topk(cos_scores, k=top_k)
    top_options = [options[idx] for idx in top_indexes]
    return top_options, top_scores
  else:
    # just return all of them
    return options, cos_scores

def transfer_slot_values(active_flow, previous_flow):
  for slot_type in ['source', 'removal']:
    if slot_type in previous_flow.slots and slot_type in active_flow.slots:
      for entity in previous_flow.slots[slot_type].values:
        active_flow.slots[slot_type].add_one(**entity)
  return active_flow

def derived_tab_preview(world):
  preview = 'N/A'

  if world.has_data(tab_type='derived'):
    for frame in reversed(world.frames):
      if frame.tab_type == 'derived':
        preview = frame.get_data(form='md', limit=16)
        break
  return preview

def pick_main_tab(state):
  if len(state.entities) > 0:
    all_tables = [ent['tab'] for ent in state.entities]
    if len(set(all_tables)) == 1:
      main_table = all_tables.pop()
    else:
      # pick the entity table that matches in the current table
      for tab in all_tables:
        if tab == state.current_tab:
          return tab
      # if no match, pick the first table
      main_table = all_tables[0]
  else:
    main_table = state.current_tab
  return main_table

def three_party_voting(party_a, party_b, party_c):
  """ compares the three parties to see if they voted the same way
  returns whether there was consensus (boolean) and the party recieving the most votes """
  consensus, top_vote = False, None

  if party_a == party_b:
    consensus = True
    top_vote = party_a
  elif party_b == party_c:
    consensus = True
    top_vote = party_b
  elif party_c == party_a:
    consensus = True
    top_vote = party_c
  return consensus, top_vote

def overlap_consensus(preds):
  # see if the different experts agree enough, returns a boolean and {dax} code
  enough_overlap = False
  top_dax = '000'

  digit_sets = [set(pred) for pred in preds]
  overlap = set.intersection(*digit_sets)
  overlap.discard('0')

  # if all the dax have overlap on exactly one digit, then return that digit as the top dax
  if len(overlap) == 1:
    enough_overlap = True
    top_digit = overlap.pop()
    top_dax = f'00{top_digit}'
  return enough_overlap, top_dax

def transfer_state_metadata(curr_state, last_state, context):
  # transfer metadata from last dialogue state to current dialogue state
  curr_state.flow_stack = last_state.flow_stack.copy()
  curr_state.turn_id = context.recent[-1].turn_id
  curr_state.has_issues = last_state.has_issues
  curr_state.has_staging = last_state.has_staging
  curr_state.has_plan = last_state.has_plan
  curr_state.slices = last_state.slices
  curr_state.errors = last_state.errors
  return curr_state

def user_ignored_issues(state):
  curr_flow = state.flow_stack.pop()
  previous_flow = state.flow_stack.pop()  # the issue flow we are removing

  state.has_issues = False
  flow_name = state.get_flow(return_name=True)  # get the third one down in the stack

  if flow_name != curr_flow.name(full=True):
    state.flow_stack.append(curr_flow) # put current flow back on
  return state

def interject_issue_flow(preference, state, world):
  # Ranking of issue resolution is [problem > concern > blank > typo]. Do not change the order!
  flowtype_to_dax = {'problem': '46F', 'concern': '46C', 'blank': '46B', 'typo': '46E'}    
  main_table = pick_main_tab(state)
  columns = [entity['col'] for entity in state.entities if entity['tab'] == main_table]

  for flow_type, issue_dax in flowtype_to_dax.items():
    # if the user preference is only at a 'warning' level, we will only interject for problems and concerns
    if preference == 'warning' and flow_type in ['blank', 'typo']: continue

    # Check if flow_type exists in metadata before accessing
    if flow_type not in world.metadata:
      continue

    issue_df = world.database.db.shadow.issues[main_table]
    if world.metadata[flow_type][main_table].issues_exist(issue_df, columns):
      issue_flow = flow_selection[issue_dax](world.valid_columns)
      issue_flow.interjected = True
      state.flow_stack.append(issue_flow)
      state.has_issues = True
      break
  return state

def ensure_unique_tab_cols(state):
  if len(state.entities) > 1:   # if there is only one entity, then it's obviously unique
    seen_ents = set()
    unique_entities = []
    for entity in state.entities:
      entity_tuple = (entity['tab'], entity['col'])
      if entity_tuple not in seen_ents:
        seen_ents.add(entity_tuple)
        unique_entities.append(entity)
    state.entities = unique_entities

  return state

def compile_operations_prompt(convo_history, flow, state):
  phrases = {
    'insert': 'creating a new column, potentially for staging intermediate results',
    'move': 'cutting and pasting content, re-arranging column order, or transposing rows and columns',
    'calculate': 'performing a calculation to define a metric such as a CVR, LTV, CTR, AOV, or Retention'
  }
  valid_ops = valid_operations[flow.flow_type]
  additional = ''
  for operation in valid_ops:
    if operation in phrases:
      additional += f"  * {operation} - {phrases[operation]}\n"

  entity_ops_snippet = state.tab_col_rep(with_break=True)
  flow_name = state.get_flow(allow_interject=False, return_name=True)
  if flow_name in ['Analyze(query)', 'Analyze(pivot)', 'Visualize(plot)']:
    entity_ops_snippet += f"\n* Past Operations: {state.slices['operations']}"

  operation_prompt = select_operations_prompt if flow.parent_type == 'Analyze' else visualize_operations_prompt
  prompt = operation_prompt.format(additional_ops=additional, num_valid=len(valid_ops), valid_snippet=valid_ops,
                                                eo_snippet=entity_ops_snippet, history=convo_history)
  return prompt

def compile_delimiter_prompt(col_info, flow, spreadsheet, convo_history):
  tab_name, col_name = col_info['tab'], col_info['col']
  source_md = spreadsheet[tab_name][col_name].dropna().head(5).to_markdown(index=False)
  targets = flow.slots['target'].values if flow.slots['target'].filled else '<unknown>'
  prompt = split_symbol_prompt.format(history=convo_history, source_markdown=source_md, targets=targets)
  return prompt

def compile_state_entities(state, world) -> str:
  temp_columns = world.frames[-1].get_columns() if world.has_data() else []

  if len(state.entities) > 0:
    entity_dict = state.entity_to_dict(state.entities)
  elif len(temp_columns) > 0:
    entity_dict = {'(temporary)': temp_columns}
  else:
    entity_dict = {'(unknown)': []}

  prior_entities = ""
  for tab_name, col_names in entity_dict.items():
    prior_entities += f"{tab_name} - {col_names}\n"
  return prior_entities

def use_validated_entities(state, last_state):
  current_flow = state.get_flow(allow_interject=False)
  if current_flow:
    ent_slot = current_flow.entity_slot
    if current_flow.slots[ent_slot].filled:
      state.entities = current_flow.slots[ent_slot].values.copy()
      current_flow.slots[ent_slot].drop_unverified()
    else:
      broad_entity = {'tab': state.current_tab, 'col': '*', 'ver': False}
      state.entities = [broad_entity]
  else:
    state.entities = last_state.entities.copy()
  return state
