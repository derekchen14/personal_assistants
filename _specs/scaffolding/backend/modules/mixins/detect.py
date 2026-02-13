# NOTE: 22 of 24 methods trimmed for scaffold reference. See git history for full implementations.
import json
import numpy as np

from utils.help import flow2dax
from backend.prompts.mixins.for_detect import *
from backend.utilities.search import transfer_issues_entity_to_state, wrap_up_issues
from backend.utilities.manipulations import unique_value_distribution
from backend.utilities.pex_helpers import count_tab_cols
from backend.components.engineer import PromptEngineer
from backend.components.metadata import MetaData
from backend.components.frame import Frame
from backend.modules.flow import flow_selection

class DetectMixin:
  """ Methods to fix concerns such as outliers, anomalies, problems, and other issues """

  def _extract_source_table(self, flow, state):
    """ Extract the source table from the flow, handling any ambiguity or errors """
    if not flow.slots['source'].filled:
      self.actions.add('CLARIFY')
      slot_desc = 'source table or column'
      state.ambiguity.declare('confirmation', flow=flow.name(), slot=slot_desc, values=[state.current_tab], generate=True)
      return None

    table_name = flow.slots['source'].table_name()

    # Ensure only one unique table is specified
    for entity in flow.slots['source'].values:
      if entity['tab'] != table_name:
        self.actions.add('CLARIFY')
        state.ambiguity.declare('confirmation', flow=flow.name(), values=[table_name, entity['tab']])
        return None

    return table_name

  def generate_issue_plan(self, context, frame, settings, issue_rows, issue_plan_prompt):
    raise NotImplementedError("Trimmed for scaffold reference")

  def _detect_core_issues(self, flow, tab_name, world, issue_type):
    """ Find the rows containing the given issue type, return the column name and the issue rows """
    raise NotImplementedError("Trimmed for scaffold reference")

  def _complete_resolution(self, flow, frame, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def identify_blanks(self, context, state, world):
    # Supports {46B} by resolving missing, default, or null values within the table
    flow = state.get_flow(flow_type='blank')
    previous_frame = world.frames[-1] if world.has_data() else None

    tab_name = self._extract_source_table(flow, state)
    if tab_name is None:
      return previous_frame, state

    if world.has_data() and state.has_issues and len(previous_frame.issues_entity.get('col', '')) > 0:
      # override the default tab_name and col_name if we have an issues_entity
      tab_name, col_name = previous_frame.issues_entity['tab'], previous_frame.issues_entity['col']
      frame = previous_frame
      issue_df = self.database.db.shadow.issues[tab_name]
      blank_rows = issue_df[(issue_df['column_name'] == col_name) & (issue_df['issue_type'] == 'blank')]
    else:
      col_name, blank_rows = self._detect_core_issues(flow, tab_name, world, 'blank')
      if len(blank_rows) == 0:
        flow.clear_all_issues()
        state.has_issues = False
        return previous_frame, state

      frame = Frame(tab_name)
      frame.issues_entity = {'tab': tab_name, 'col': col_name, 'flow': flow.name()}

    state.has_issues = True
    settings = {'include_nulls': True, 'show_nulls_as_count': True, 'show_arrow': True, 'num_values': 32}

    if flow.is_filled():   # either because we created a plan, or because no legitimate issues exist
      flow, state = self._complete_resolution(flow, frame, state, world)

    elif flow.is_newborn:
      flow = self.attach_follow_up(context, flow, frame, state)
      state = transfer_issues_entity_to_state(state, frame)

      if set(blank_rows['issue_subtype']) == {'null'} and len(blank_rows) < 4096:
        # just use imputation directly, no need to craft a plan
        impute_step = {'name': 'impute', 'description': 'fill in the missing values in the column', 'checked': False}
        flow.slots['plan'].steps.append(impute_step)
        flow, state = self._complete_resolution(flow, frame, state, world)

      else:
        prediction = self.generate_issue_plan(context, frame, settings, blank_rows, blank_plan_prompt)
        if flow.fill_slot_values(prediction):
          flow, state = self._complete_resolution(flow, frame, state, world)
        else:
          frame, state = self.clarify_issue_plan(flow, frame, state)

    else:
      prediction = self.revise_issue_plan(context, frame, settings, blank_rows, blank_plan_prompt)
      if flow.fill_slot_values(prediction):
        flow, state = self._complete_resolution(flow, frame, state, world)
      else:
        if flow.interjected:
          state.flow_stack.pop()    # drop the interjected flow
        flow, state = wrap_up_issues(flow, state)

    return frame, state

  def identify_concerns(self, context, state, world):
    # Supports {46C} by resolving concerns such as outliers, anomalies, and other issues
    raise NotImplementedError("Trimmed for scaffold reference")

  def clarify_issue_plan(self, flow, frame, state):
    # either the step was not filled, or the description was unsure
    raise NotImplementedError("Trimmed for scaffold reference")

  def identify_typos(self, context, state, world):
    # Supports {46E} by resolving similar terms or typos within the table
    raise NotImplementedError("Trimmed for scaffold reference")

  def build_resolution_flow(self, active_step, old_flow, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def identify_problems(self, context, state, world):
    # Supports {46F} by resolving problems such as mixed datatypes and unsupported data structures
    raise NotImplementedError("Trimmed for scaffold reference")

  def decide_issue_redirection(self, context, concerns, tab_name, col_name):
    raise NotImplementedError("Trimmed for scaffold reference")

  def attach_follow_up(self, context, flow, frame, state):
    raise NotImplementedError("Trimmed for scaffold reference")

  def display_issues(self, frame, state):
    # Extract the issue rows from ShadowDB for display
    raise NotImplementedError("Trimmed for scaffold reference")

  def drop_resolved_rows(self, selected_rows, frame, state):
    """ Users do not need to resolve all issues at once. """
    raise NotImplementedError("Trimmed for scaffold reference")

  def backfill_issue_flow(self, resolution_flow, issue_flow, state):
    raise NotImplementedError("Trimmed for scaffold reference")

  def connect_information(self, context, state, world):
    # Supports {46D} which is a generic request to combine two data sources together
    raise NotImplementedError("Trimmed for scaffold reference")

  def resolve_issues(self, context, state, world):
    # Supports {468} which is a planning request to identify issues within the table
    raise NotImplementedError("Trimmed for scaffold reference")

  def propose_fix_plan(self, context, flow, state, tab_name, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def collect_issue_option(self, issue, tab_name, flow, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def collect_cleaning_option(self, tab_name, flow, option, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def uncover_insights(self, context, state, world):
    """ Supports {146} as a method for performing advanced analysis requiring multiple metrics and variables. """
    raise NotImplementedError("Trimmed for scaffold reference")

  def insight_routing(self, context, flow, state, tab_col_str):
    raise NotImplementedError("Trimmed for scaffold reference")

  def propose_insight_plan(self, context, flow, state, tab_col_str):
    # generate a natural language plan to present to the user for approval
    raise NotImplementedError("Trimmed for scaffold reference")

  def review_insight_proposal(self, context, flow, state, tab_col_str):
    # propose the type of analysis to run and ask for clarification on any missing information
    raise NotImplementedError("Trimmed for scaffold reference")

  def revise_plan(self, context, flow, state, tab_col_str, restart=False):
    # the user has seen the plan, but has given feedback on how to change it
    raise NotImplementedError("Trimmed for scaffold reference")

  def convert_to_stack_on(self, context, flow, state, world):
    # convert the plan written in natural language into a plan composed of a series of stack_on flows
    raise NotImplementedError("Trimmed for scaffold reference")

  def execute_select_flow(self, context, flow, state, world):
    """ cycle through a battery of analyses to find anything that can be considered interesting """
    raise NotImplementedError("Trimmed for scaffold reference")

  def transfer_metrics_and_entities(self, context, flow, stack_on, next_step):
    # transfer over the source entities to the analyze flow
    raise NotImplementedError("Trimmed for scaffold reference")

  def write_to_scratchpad(self, curr_flow, prev_flow, table_df):
    # use all the information from metric or variable info to summarize results
    raise NotImplementedError("Trimmed for scaffold reference")

  def finish_up(self, context, flow, state, tab_col_str):
    # wrap up the flow by presenting the results to the user
    raise NotImplementedError("Trimmed for scaffold reference")
