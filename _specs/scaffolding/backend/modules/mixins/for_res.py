from backend.assets.ontology import generic_responses, clean_responses, visualize_responses, transform_responses
from backend.prompts.for_res import *
from backend.prompts.general import safety_guide
from backend.utilities.templates import *
from backend.utilities.res_helpers import gather_relevant_facts
from backend.components.engineer import PromptEngineer
from utils.help import flow2dax, dax2intent

class ResponseMixin:
  """ Methods to generate responses for the different dialog acts """

  def noun_response(self, scheme, utterance):
    # Responses for when the user is simply calling attention to a specific tab, row, or col
    tab_content = []
    for table in scheme.keys():
      col_names = ', '.join(scheme[table].general_stats["column_names"])
      tab_content.append(f"  * {col_names} in the {table} table")
    valid_content = '\n'.join(tab_content)

    prompt = noun_prompt.format(valid_content=valid_content, utterance=utterance)
    response_output = self.api.execute(prompt, prefix='Response:')
    response_output = response_output[9:].strip()
    return response_output

  def chat_response(self, context, state):
    convo = context.full_conversation(for_api=True, keep_system=True)
    if state.command_type == 'direct_response' and len(state.thought) > 0:
      response_output = state.thought
    else:
      final_utt = state.thought if len(state.thought) > 0 else safety_guide
      raw_output = self.api.execute(final_utt, convo, prefix='Response:')
      response_output = raw_output[9:].strip()
    return response_output

  def analyze_response(self, context, frame, flows, scheme, state):
    # Responses for the Analyze flow, which covers {001}, {01A}, {002}, {014} and {02D}
    completed_flows, current_flow, issue_flow = flows['completed'], flows['current'], flows['issue']

    if current_flow:
      main_flow = state.get_flow(allow_interject=False) if current_flow.interjected else current_flow
    elif len(completed_flows) > 0:
      main_flow = completed_flows[-1]
    else:
      main_flow = None

    if main_flow:
      num_rows = frame.preview_row_count(main_flow)
      markdown = PromptEngineer.display_preview(frame.get_data(), max_rows=num_rows)
      dialog_act = main_flow.name()
    else:
      markdown = frame.get_data(form='md')
      dialog_act = 'none'

    match dialog_act:
      case 'measure': response_output = self.metric_response(context, main_flow, markdown, state)
      case 'describe': response_output = self.describe_response(context, main_flow, frame, scheme, state)
      case 'exist': response_output = self.exist_response(context, main_flow, frame)
      case 'segment': response_output = self.metric_response(context, main_flow, markdown, state)
      case 'pivot': response_output = self.pivot_response(context, main_flow, markdown, state.thought)
      case _: response_output = self.query_response(context, markdown, state.thought)

    if frame.is_successful() and state.has_issues and issue_flow and issue_flow.interjected:
      response_output += attach_issue_warning(frame, issue_flow)
    return response_output

  def metric_response(self, context, flow, markdown, state):
    if flow and len(flow.stage) > 0 and flow.stage != 'completed':
      response_output = metric_templates(flow, markdown)
    else:
      response_output = self.query_response(context, markdown, state.thought)
    return response_output

  def pivot_response(self, context, flow, markdown, thought):
    if flow and flow.interjected:
      response_output = pivot_templates(flow)
    else:
      response_output = self.query_response(context, markdown, thought)
    return response_output

  def visualize_response(self, context, frame, issue_flow, state):
    # Set a default response based on templates, which is very cheap to run
    options = generic_responses + visualize_responses
    response_output = random.choice(options)

    # Upgrade to a generated response if the situation calls for it
    user_utt = context.last_utt('User')
    if len(frame.get_columns()) >= 4 or len(user_utt) > 64 or frame.properties.get('converted', False):
      markdown = PromptEngineer.display_preview(frame.get_data())
      convo_history = context.compile_history(look_back=3)
      prompt = query_response_prompt.format(history=convo_history, thought=state.thought, frame=markdown)
      raw_output = self.api.execute(prompt, prefix='Answer:')
      response_output = raw_output[7:].strip()
    frame.properties.pop('converted', None)  # reset the converted attribute

    if frame.is_successful() and state.has_issues and issue_flow and issue_flow.interjected:
      response_output += attach_issue_warning(frame, issue_flow)
    return response_output

  def clean_response(self, frame, flows):
    current_flow, completed_flows, just_completed = flows['current'], flows['completed'], False

    response_output = ''
    if current_flow and len(current_flow.stage) > 0:
      response_output = stage_based_templates(current_flow)
    elif len(completed_flows) > 0:
      clean_flow = [flow for flow in completed_flows if dax2intent(flow2dax(flow.name())) == 'Clean'][0]
      just_completed = True
      response_output = completion_response(frame, clean_flow)

    if len(response_output) == 0:
      options = generic_responses + clean_responses
      response_output = random.choice(options)
    if just_completed:
      interactive_json = {'content': 'end', 'format': 'signal', 'show': False}
      self.top_panel = {'interaction': interactive_json}
    return response_output

  def transform_response(self, frame, flows):
    active_flow, completed_flows = flows['current'], flows['completed']
    if active_flow and active_flow.parent_type == 'Transform':  # if the current flow is still active
      response = stage_based_templates(active_flow)
    else:
      prev_flow = completed_flows[-1]
      match prev_flow.name():
        case 'insert': response = insert_action_template(prev_flow)
        case 'delete': response = delete_action_template(prev_flow)
        case 'split': response = split_column_template(prev_flow)
        case 'join': response = join_tables_template(prev_flow)
        case 'append': response = append_rows_template(prev_flow)
        case 'merge': response = merge_columns_template(prev_flow)
        case _: response = random.choice(generic_responses + transform_responses)

    if len(completed_flows) > 0:
      interactive_json = {'content': 'end', 'format': 'signal', 'show': False}
      self.top_panel = {'interaction': interactive_json}
    return response

  def describe_response(self, context, flow, frame, scheme, state):
    # Responses for the describe dact, which is largely template based
    all_facts = gather_relevant_facts(flow, frame, scheme, state)
    pertinent_details = '\n'.join([f"  - {fact}" for fact in all_facts])
    data_preview = frame.get_data(form='md')
    convo_history = context.compile_history(look_back=3)

    prompt = describe_response_prompt.format(details=pertinent_details, preview=data_preview, history=convo_history)
    response_output = self.api.execute(prompt, prefix='Answer:', version='claude-sonnet')
    response_output = response_output[7:].strip()
    return response_output

  def exist_response(self, context, flow, frame):
    valid_cols = PromptEngineer.column_rep(flow.valid_col_dict, with_break=True)
    column_md = frame.get_data(form='md', limit=10)
    convo_history = context.compile_history(look_back=3)
    prompt = exist_response_prompt.format(columns=valid_cols, preview=column_md, history=convo_history)
    response_output = self.api.execute(prompt, prefix='Answer:')
    response_output = response_output[7:].strip()
    return response_output

  def command_response(self, current_flow, context, curr_frame, prev_frame):
    # Current_flow and frame get the derived data, the state is used to write a thought of the code that was changed
    markdown = PromptEngineer.display_preview(curr_frame.get_data(), max_rows=32)
    history = context.compile_history(look_back=3)

    history += f"\nAgent: The query I used for this analysis was: \n{prev_frame.code}"
    history += f"\nUser: Please modify the SQL Query to: \n{curr_frame.code}"
    thought = "I should first identify the change in the SQL Query, then give an intrepretation of the dataframe results given this change."
    response_output = self.query_response(context, markdown, thought)
    return response_output

  def query_response(self, context, markdown, thought):
    convo_history = context.compile_history(look_back=3)
    prompt = query_response_prompt.format(history=convo_history, thought=thought, frame=markdown)
    raw_output = self.api.execute(prompt, prefix='Answer:')
    response_output = raw_output[7:].strip()
    return response_output

  def detect_response(self, context, frame, flows, state, dax):
    current_actions = context.last_actions['Agent']
    completed_flows, current_flow, issue_flow = flows['completed'], flows['current'], flows['issue']

    if issue_flow:
      if 'ISSUE' in current_actions:                                  # We are resolving an issue
        response_output = confirm_identify_issue(frame, context, issue_flow)
        self.set_interaction(state, completed_flows)
      elif state.has_issues:
        response_output = issue_templates(frame, issue_flow)          # We have detected new issues
      else:
        response_output = no_issues_template(frame, state)            # We have not detected any issues

    elif dax == '146':
      response_output = self.insight_response(context, state, completed_flows, current_flow, frame)
    elif dax == '468':
      response_output = self.resolve_response(frame, state, context, current_flow)
    elif dax == '46D':
      response_output = self.connect_response(frame, state, context, current_flow)
    return response_output

  def insight_response(self, context, state, completed_flows, current_flow, frame):
    if len(completed_flows) > 0:
      response, prompt = insight_completion(context, completed_flows[-1], frame)
      if prompt != '':
        raw_output = self.api.execute(prompt, prefix='_Thoughts_')  # finish-up
        response = raw_output.split('_Output_')[1].strip()
    elif state.has_plan:
      response = ask_for_user_approval(current_flow, state)      # time-warning
    else:
      response = review_insight_proposal(current_flow, state)    # show-me-something
    return response

  def resolve_response(self, frame, state, context, current_flow):
    if state.has_plan:
      response = confirm_plan_template(frame, current_flow)
    else:
      response = notify_fix_available(frame, current_flow)
    return response

  def connect_response(self, frame, state, context, current_flow):
    if state.has_plan:
      response = confirm_plan_template(frame, current_flow)
    else:
      response = notify_connection_available(current_flow)
    return response

  def staging_response(self, frame, flows, pred_dax):
    completed_flows, current_flow = flows['completed'], flows['current']
    if len(completed_flows) > 0:
      response_output = complete_staging_template(frame)
    else:   # ask for permission to create a staging table
      response_output = create_staging_template(current_flow, pred_dax)
    return response_output