import re
import json
import random
import pandas as pd
import time as tm
from utils.help import dax2dact, dact2dax

from backend.assets.ontology import generic_responses
from backend.modules.experts.faq import FAQRetrieval
from backend.modules.mixins.for_res import ResponseMixin

class ResponseGeneration(ResponseMixin):
  def __init__(self, args, api, embedder):
    self.verbose = args.verbose
    self.api = api

    self.faq_model = FAQRetrieval(args, api, embedder)
    self.top_panel = None
    self.follow_up_details = {}

  def respond(self, context, flows, frame, state, scheme):
    # generates the message response from the agent
    user_text = context.last_utt('User')
    current_actions = context.last_actions['Agent']
    pred_dact, pred_dax = state.get_dialog_act(form='string'), state.get_dialog_act()

    if len(current_actions) > 0:
      if 'CLARIFY' in current_actions:
        response_output = state.ambiguity.ask(self.api, context, state)
      elif 'STAGING' in current_actions:
        response_output = self.staging_response(frame, flows, pred_dax)
      elif 'COMMAND' in current_actions:
        response_output = random.choice(generic_responses)
      elif 'DETECT' in current_actions or 'ISSUE' in current_actions:
        response_output = self.detect_response(context, frame, flows, state, pred_dax)
      elif 'ANALYZE' in current_actions or 'REPAIR' in current_actions:
        response_output = self.analyze_response(context, frame, flows, scheme, state)
      elif 'VISUALIZE' in current_actions:
        response_output = self.visualize_response(context, frame, flows['issue'], state)
      elif 'TRANSFORM' in current_actions:
        response_output = self.transform_response(frame, flows)
      elif 'CLEAN' in current_actions:
        response_output = self.clean_response(frame, flows)
      else:
        response_output = "Unexpected action of type " + str(current_actions)

    elif pred_dact == 'faq':
      response_output = self.faq_model.help(state, user_text)
    elif pred_dact in ['table', 'row', 'column']:
      response_output = self.noun_response(scheme, user_text)
    else:
      response_output = self.chat_response(context, state)
    return response_output, state

  def pop_completed_flows(self, state):
    # Remove completed flows from the stack, and return the completed and current flows
    active_flow, current_flow, issue_flow = None, None, None
    completed_flows = []    # flows that were just completed

    while state.has_active_flow():
      active_flow = state.get_flow()
      if active_flow.parent_type == 'Issue':
        issue_flow = active_flow

      if active_flow.completed:
        previous_flow = state.flow_stack.pop()
        completed_flows.append(previous_flow)
      else:
        current_flow = active_flow
        break

    if active_flow and active_flow.completed and active_flow.parent_type == 'Analyze':
      if issue_flow and issue_flow.completed and 'query' in issue_flow.follow_up:
        self.follow_up_details = issue_flow.follow_up
    return completed_flows, current_flow, issue_flow

  def ignoring_flow(self, state, context, metadata):
    # check if only converse dacts for too long, which means an active flow is ignored
    flow_type = self.dax2flow.get(state.dax, None)
    if flow_type is None:                 # if not a flow, then consider it a partially ignored
      self.partial_ignore += 1
      if self.partial_ignore >= 3:
        state.flow_stack.pop()
        self.partial_ignore = 0

  def limit_columns(self, frame, state):
    # Create a list of columns to drop, then limit cols until at least 2 remain
    drop_columns = []
    flow = state.get_flow()
    for col in frame.data.columns:
      if frame.data[col].nunique() == 1:
        drop_columns.append(col)
      elif flow and 'operation' in flow.slots and flow.slots['operation'].filled:
        for operation in flow.slots['operation'].values:
          if col in operation and "filter" in operation:
            drop_columns.append(col)

    while frame.data.shape[1] > 2 and drop_columns:
      print(f"  Dropped column {drop_columns[0]} for visualization")
      frame.data = frame.data.drop(drop_columns[0], axis=1)
      drop_columns.pop(0)
    return frame

  def creation(self, response, frame, world):
    response['frame'] = frame.get_data('define')
    response['tabType'] = 'direct'
    response['properties'] = {frame.raw_table: world.get_simplified_schema(frame.raw_table)}
    completion = {'content': 'end', 'format': 'signal', 'show': False}
    self.top_panel = {'interaction': completion}
    return response

  def visualize(self, frame, flows):
    if len(flows['completed']) > 0:
      flow = flows['completed'][0]
      match flow.name():
        case 'plot': report_json = self.set_plotting_panel(frame, flow)
        case 'explain': report_json = self.set_explanation_panel(frame, flow)
        case 'design': report_json = self.design_chart_panel(frame, flow)
        case 'style': report_json = self.style_table_panel(frame, flow)

      report_json['format'] = 'json'
      report_json['flowType'] = flow.name(full=True)
      report_json['show'] = True

    else:
      report_json = {'content': 'end', 'format': 'signal', 'show': False}
    return report_json

  def set_plotting_panel(self, frame, flow):
    fig_json_string = frame.visual.to_json()
    report_json = json.loads(fig_json_string)

    # Transfer the SQL query into the report so we can record it
    if self.top_panel.get('interaction'):
      report_json['content'] = self.top_panel['interaction']['content']
    return report_json

  def interact(self, frame, metadata, state):
    flow = state.get_flow()
    flow_name = flow.name(full=True)
    match flow_name:
      case 'Analyze(measure)': interactive_json = self.set_measure_panel(frame, state, flow)
      case 'Analyze(segment)': interactive_json = self.set_segment_panel(frame, state, flow)
      case 'Clean(dedupe)': interactive_json = self.remove_duplicates_panel(frame, state, flow)
      case 'Clean(validate)': interactive_json = self.set_validate_panel(frame, state, flow)
      case 'Transform(insert)': interactive_json = self.set_insert_panel(frame, state, flow)
      case 'Transform(split)': interactive_json = self.split_column_panel(frame, state, flow)
      case 'Transform(merge)': interactive_json = self.merge_columns_panel(frame, state, flow)
      case 'Transform(join)': interactive_json = self.join_tables_panel(frame, state, flow)

    interactive_json['flowType'] = flow_name
    interactive_json['format'] = 'json'
    interactive_json['show'] = True
    return interactive_json

  def set_interaction(self, state, completed_flows):
    # just completed must come first to ensure that previous_flow is not None
    if not state.natural_birth:
      if any(flow.name() in ['typo', 'measure'] for flow in completed_flows):
        interactive_json = {'content': 'end', 'format': 'signal', 'show': False}
      else:
        interactive_json = {'content': 'next', 'format': 'signal', 'show': False}
      self.top_panel = {'interaction': interactive_json}
    else:
      self.top_panel = {'interaction': {'content': 'end', 'format': 'signal', 'show': False}}

  def _find_likely_entities(self, flow, state):
    slot_type = flow.entity_slot
    top_entities, top_columns = [], []
    for entity in flow.slots[slot_type].values:
      top_entities.append(entity)
      top_columns.append(entity['col'])

    for entity in state.entities:
      if entity['col'].lower() in state.thought.lower() and entity['col'] not in top_columns:
        top_entities.append(entity)
        top_columns.append(entity['col'])
    return top_entities

  def set_measure_panel(self, frame, state, flow):
    metric = flow.slots['metric'].formula

    if flow.stage == 'build-variables':
      top_cols = self._find_likely_entities(flow, state)
      content = {'rankings': top_cols, 'formula': metric.__dict__()}

    elif flow.stage == 'time-range':
      time_unit, time_back = flow.slots['time'].unit, flow.slots['time'].time_len
      preset_options = ['1-day', '0.5-week', '1-week', '2-week', '1-month', '1-year']
      selected_time = f"{time_back}-{time_unit}" if f"{time_back}-{time_unit}" in preset_options else 'all'
      content = {'selected_time': selected_time, 'metric_name': metric.name, 'aliases': metric.aliases}

    elif flow.stage == 'pick-tab-col':
      tabs = list(set([entity['tab'] for entity in flow.slots['source'].values]))
      selected = []
      for ent in flow.slots['source'].values:
        side = 'left' if ent['tab'] == tabs[0] else 'right'
        selected.append({**ent, 'side': side})
      content = { 'selected': selected }

    measure_json = {'stage': flow.stage, 'content': content}
    return measure_json

  def set_segment_panel(self, frame, state, flow):
    metric = flow.slots['metric'].formula

    if flow.stage == 'build-variables':
      top_cols = self._find_likely_entities(flow, state)
      content = {'rankings': top_cols, 'formula': metric.__dict__()}

    elif flow.stage == 'time-range':
      time_unit, time_back = flow.slots['time'].unit, flow.slots['time'].time_len
      preset_options = ['1-day', '0.5-week', '1-week', '2-week', '1-month', '1-year']
      selected_time = f"{time_back}-{time_unit}" if f"{time_back}-{time_unit}" in preset_options else 'all'
      content = {'selected_time': selected_time, 'metric_name': metric.name, 'aliases': metric.aliases}

    elif flow.stage == 'pick-tab-col':
      tabs = list(set([entity['tab'] for entity in flow.slots['source'].values]))
      selected = []
      for ent in flow.slots['source'].values:
        side = 'left' if ent['tab'] == tabs[0] else 'right'
        selected.append({**ent, 'side': side})
      content = { 'selected': selected }

    segment_json = {'stage': flow.stage, 'content': content}
    return segment_json

  def set_insert_panel(self, frame, state, flow):
    if flow.stage == 'pick-tab-col':
      likely_certs = self._find_likely_entities(flow, state)
      content = { 'selected': likely_certs }
    elif flow.stage == 'merge-style':
      content = { 'selected': flow.slots['source'].values,
                  'reference': flow.slots['settings'].value['reference']
                }
    insert_col_json = {'stage': flow.stage, 'content': content}
    return insert_col_json

  def remove_duplicates_panel(self, frame, state, flow):
    if flow.stage == 'pick-tab-col':
      likely_certs = self._find_likely_entities(flow, state)
      content = { 'selected': likely_certs }
    elif flow.stage == 'merge-style':
      content = { 'selected': flow.slots['removal'].values,
                  'styles':  flow.rank_styles(flow.slots['candidate'].values),
                  'reference': flow.slots['settings'].value['reference']
                }
    elif flow.stage.startswith('combine-'):
      content = { 'selected': flow.slots['removal'].values,
                  'cardset_index': flow.tracker.cardset_index,
                  'batch_number': flow.tracker.batch_number,
                  'confidence_level': flow.slots['confidence'].level,
                  'cardsets': frame.active_conflicts,
                  'num_remaining': len(flow.tracker.conflicts)
                }
    duplicates_json = {'stage': flow.stage, 'content': content}
    return duplicates_json

  def set_validate_panel(self, frame, state, flow):
    panel_json = {}

    if flow.stage == 'pick-tab-col':
      likely_certs = self._find_likely_entities(flow, state)
      content = { 'selected': likely_certs }

    elif flow.stage == 'checkbox-opt':
      content = { 'proposed': flow.slots['terms'].values,
                  'possible': flow.unique_values}

    elif flow.stage == 'choose-terms':
      tab_name, col_name = frame.issues_entity['tab'], frame.issues_entity['col']
      column = frame.data[col_name]
      valid_terms = column.fillna('').unique().tolist()

      # TODO: Build content from tracker, rather than issue_df or typo_groups
      issue_df = self.database.db.shadow.issues[tab_name]
      typo_issues = issue_df[(issue_df['column_name'] == col_name) & (issue_df['issue_type'] == 'typo')]

      # Group by revised_term to create the content structure
      content = {}
      for _, row in typo_issues.iterrows():
        revised_term = row['revised_term']
        original_value = row['original_value']
        if revised_term and pd.notna(revised_term):
          if revised_term not in content:
            content[revised_term] = []
          if original_value not in content[revised_term]:
            content[revised_term].append(original_value)
      panel_json = {'table': tab_name, 'column': col_name, 'valid_terms': valid_terms}

    validation_json = {'stage': flow.stage, 'content': content, **panel_json}
    return validation_json

  def merge_columns_panel(self, frame, state, flow):
    if flow.stage == 'pick-tab-col':
      likely_certs = self._find_likely_entities(flow, state)
      content = { 'selected': likely_certs }
    elif flow.stage == 'merge-style':
      content = { 'selected': flow.slots['source'].values,
                  'styles':   flow.rank_styles(flow.slots['candidate'].values),
                  'reference': flow.slots['settings'].value['reference']
                }
    merge_col_json = {'stage': flow.stage, 'content': content}
    return merge_col_json

  def split_column_panel(self, frame, state, flow):
    if flow.stage == 'pick-tab-col':
      likely_certs = self._find_likely_entities(flow, state)
      content = { 'selected': likely_certs }
    elif flow.stage == 'split-style':
      content = { 'source_entity': flow.slots['source'].values[0],  # dict
                  'delimiter': flow.slots['exact'].term,            # string
                  'target_entities': flow.slots['target'].values    # list of dicts
                }
    merge_col_json = {'stage': flow.stage, 'content': content}
    return merge_col_json

  def join_tables_panel(self, frame, state, flow):
    if flow.stage == 'pick-tab-col':
      sides = {}  # Keep track of the sides assigned to each table
      selected = []  # The list to store the modified entities
      for entity in flow.slots['source'].values:
        tab = entity['tab']
        if tab not in sides:
          if len(sides) == 0:
            sides[tab] = 'left'  # Assign the first unique table to the left
          elif len(sides) == 1:
            sides[tab] = 'right'  # Assign the second unique table to the right
          else:
            continue  # If we already have two unique tables, skip any new tables
        # Append the entity with the side information
        selected.append({**entity, 'side': sides[tab]})
      content = { 'selected': selected }

    elif flow.stage == 'checkbox-opt':
      content = { 'entities': {
                    'source': flow.slots['source'].values,
                    'target': flow.slots['target'].values
                  },
                  'proposed': [ent['col'] for ent in flow.slots['target'].values],
                  'possible': flow.options
                }
    elif flow.stage.startswith('combine-'):
      content = { 'selected': flow.slots['source'].values,
                  'cardset_index': flow.tracker.cardset_index,
                  'batch_number': flow.tracker.batch_number,
                  'confidence_level': flow.slots['confidence'].level,
                  'cardsets': frame.active_conflicts,
                  'num_remaining': len(flow.tracker.conflicts)
                }
    integration_json = {'stage': flow.stage, 'content': content}
    return integration_json

  def apply_markdown_format(self, original_utt: str, response: dict) -> dict:
    if original_utt == '':
      return response

    def convert_bullets(match):
      bullet_points = match.group(0).strip().split('\n')
      list_items = []
      for point in bullet_points:
        list_text = point.strip()[2:]
        li = f'  </br>' if len(list_text) == 0 else f'  <li class="ml-4">{list_text}</li>'
        list_items.append(li)
      list_string = ''.join(list_items)
      return f'<ul class="list-disc">\n{list_string}</ul>'

    def convert_numbers(match):
      list_items = []
      for point in match.group(0).strip().split('\n'):
        list_text = re.sub(r'^\s*[1-9]\.\s*', '', point.strip())
        li = f'  </br>' if len(list_text) == 0 else f'  <li class="ml-4">{list_text}</li>'
        list_items.append(li)
      list_string = ''.join(list_items)
      return f'<ol class="list-decimal">\n{list_string}</ol>'

    patterns = [
      (r"(^|\s)\*\*(.*?)\*\*($|\s|:)", r"\1<strong>\2</strong>\3"),   # Convert bold
      (r"(^|\s)\_(.*?)\_($|\s|:)", r"\1<em>\2</em>\3"),               # Convert italic
      (r"\`\`\`sql\n(.*?)\`\`\`", r"<code>\1</code>"),                # Convert SQL
      (r"(^|\s)\`(.*?)\`($|\s|:)", r"\1<code>\2</code>\3"),           # Convert code
      (r"^\n\n+", r"<br>"),                                           # Convert newlines
      (r"(^\s*-\s*.*(\n\s*-\s*.*)*)", convert_bullets),               # Convert bulletpoints
      (r"(?:^\s*[1-9]\.\s+.+$\n?)+", convert_numbers)                 # Convert numbered list
    ]

    for pattern, repl in patterns:
      revised_utt = re.sub(pattern, repl, original_utt, flags=re.MULTILINE)
      if revised_utt != original_utt:
        response['raw_utterance'] = original_utt
      original_utt = revised_utt

    response['message'] = revised_utt
    return response

  def finalize_response(self, agent_utt, response, frame):
    response = self.apply_markdown_format(agent_utt, response)
    response['interaction'] = self.top_panel['interaction'] if self.top_panel else None

    snippet = ''
    if response['interaction'] and response['interaction'].get('content'):
      content = response['interaction']['content']

      if content == 'end' and response['interaction'].get('format') == 'signal' and len(frame.code) > 0:
        snippet = frame.code.replace('self.db.tables', 'df')
      elif isinstance(content, str):
        for prefix in ['<em>SQL Query</em>:<br>', '<em>Pandas Code</em>:<br>']:
          if content.startswith(prefix):
            snippet = content[len(prefix):]
            snippet = re.sub(r'<br>', '\n', snippet)
            snippet = re.sub(r'&nbsp;', ' ', snippet)

    if len(snippet) > 0:
      if 'ANALYZE' in response['actions'] and frame.source == 'sql':
        response['code_snippet'] = { 'source': 'SQL Query', 'snippet': snippet }
      if 'VISUALIZE' in response['actions'] and frame.source == 'plotly':
        response['code_snippet'] = { 'source': 'SQL Query', 'snippet': snippet }
      elif any(action in response['actions'] for action in ['CLEAN', 'TRANSFORM', 'DETECT']) and frame.source == 'pandas':
        response['code_snippet'] = { 'source': 'Python Code', 'snippet': snippet }

    return response

  def generate(self, actions, context, frame, world):
    """ Output is a dictionary with four keys:
    message: text of the agent response
    actions: list of things done by the agent
    uncertainty: dict with belief state uncertainty as ambiguity object
    frame: usually passed in after PEX, rather than being generated here
    interaction: plotly visualization or interactive panel with custom content
    """
    state, schema = world.current_state(), world.current_schema()
    state.ambiguity.gather_active_entities(world.valid_columns, state, actions)
    completed_flows, current_flow, issue_flow = self.pop_completed_flows(state)
    flows = {'completed': completed_flows, 'current': current_flow, 'issue': issue_flow}

    context.store_completed_flows(completed_flows)
    agent_utt, state = self.respond(context, flows, frame, state, schema)
    response = {'actions': actions, 'uncertainty': state.ambiguity.uncertainty}

    if 'VISUALIZE' in actions:
      report_json = self.visualize(frame, flows)
      self.top_panel = {'interaction': report_json}
    if 'INTERACT' in actions:
      interactive_json = self.interact(frame, world.metadata, state)
      self.top_panel = {'interaction': interactive_json}
    if 'SUGGEST' in actions:
      flow = state.get_flow()
      response['suggestions'] = flow.suggest_replies()
    if 'CREATION' in actions:
      response = self.creation(response, frame, world)

    response = self.finalize_response(agent_utt, response, frame)
    return response

