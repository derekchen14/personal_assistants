# NOTE: 33 of 35 methods trimmed for scaffold reference. See git history for full implementations.
import random
import copy
import numpy as np
import pandas as pd
from collections import defaultdict

from backend.modules.flow import flow_selection
from backend.prompts.mixins.for_transform import *
from backend.prompts.for_nlu import move_element_prompt
from backend.assets.ontology import type_hierarchy, default_limit

from utils.help import dax2flow, flow2dax
from backend.components.engineer import PromptEngineer
from backend.components.frame import Frame
from backend.components.metadata import MetaData
from backend.utilities.manipulations import *

class TransformMixin:
  """ Methods to manipulate or change the structure of the spreadsheet """

  def transform_safety_net(self, frame, snapshot_df, state):
    """ Double check that the error message is not a false positive in the case of NaNs """
    raise NotImplementedError("Trimmed for scaffold reference")

  def insert_action(self, context, state, world):
    # Router for {005} to decide between inserting values with or without issues, also marks flow as completed when done
    flow = state.get_flow(flow_type='insert')

    if flow.is_uncertain:
      self.actions.add('CLARIFY')
      flow.is_uncertain = False
      state.ambiguity.declare('specific')
      frame = Frame(state.current_tab)
      return frame, state

    if state.has_issues:
      frame, state = self.interpolate_issues(flow, context, state, world)
    elif state.has_plan:
      frame, state = self.execute_insert_step(flow, context, state, world)
    else:
      frame, state = self.insert_values(flow, context, state, world)

    if frame.is_successful():
      flow.completed = True
      state, context = check_slice_preferences(context, flow, state)

      unique_tables = set([ent['tab'] for ent in flow.slots['target'].values])
      if len(unique_tables) > 1:
        updated_tabs = list(unique_tables)
        frame.properties['tabs'] = updated_tabs
      else:
        updated_tabs = [state.current_tab]

      self.update_system_prompt(updated_tabs, world, context, flow)
    return frame, state

  def interpolate_issues(self, flow, context, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def insert_values(self, flow, context, state, world):
    """ Supports {005} by deciding what content to insert, then notifies the database accordingly """
    raise NotImplementedError("Trimmed for scaffold reference")

  def delete_action(self, context, state, world):
    # Router for {007} to decide between deleting values or deleting issues, also marks flow as completed when done
    raise NotImplementedError("Trimmed for scaffold reference")

  def execute_insert_step(self, flow, context, state, world):
    """ Supports interjected Insert flows when triggered by plan within a Detect flow """
    raise NotImplementedError("Trimmed for scaffold reference")

  def remove_issues(self, flow, context, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def delete_values(self, flow, context, state, world):
    """ Supports {007} by deciding what content to delete, then notifies the database accordingly """
    raise NotImplementedError("Trimmed for scaffold reference")

  def transpose_action(self, context, state, world):
    # Supports {056} by deciding how to rotate the data, then notifies the database accordingly
    raise NotImplementedError("Trimmed for scaffold reference")

  def cut_and_paste(self, context, state, world):
    # Supports {057} by deciding how to move the data, then notifies the database accordingly
    raise NotImplementedError("Trimmed for scaffold reference")

  def split_column(self, context, state, world):
    """Supports {5CD} by deciding which columns to split, which is generally viewed as text-to-columns """
    raise NotImplementedError("Trimmed for scaffold reference")

  def initialize_merge_frame(self, flow, state, world):
    """Prepare a decision table needed by Transform(join) for picking tabs/cols."""
    raise NotImplementedError("Trimmed for scaffold reference")

  def prepare_conflict_cards(self, frame, flow):
    # Sample a batch of conflict cards from the detector representing potential cross table matches
    raise NotImplementedError("Trimmed for scaffold reference")

  def combine_progress_action(self, frame, flow, cross=False):
    # When cardset_index == 10, all cardsets have been reviewed, so it's time to start learning from the examples
    raise NotImplementedError("Trimmed for scaffold reference")

  def materialize_view(self, context, state, world):
    """ Supports {58A} converting the target derived table into a permanent direct table """
    raise NotImplementedError("Trimmed for scaffold reference")

  def build_table_properties(self, derived_props):
    raise NotImplementedError("Trimmed for scaffold reference")

  def align_connection_columns(self, context, flow, grounding):
    raise NotImplementedError("Trimmed for scaffold reference")

  def complete_table_join(self, context, flow, state, world):
    # Supports {05A} by deciding how to merge two tables together, then notifies the database accordingly
    raise NotImplementedError("Trimmed for scaffold reference")

  def count_overlapping_rows(self, flow, left_df, right_df, left_tab_name, right_tab_name):
    raise NotImplementedError("Trimmed for scaffold reference")

  def prepare_crew_members(self, flow, state, left_tab_name, right_tab_name):
    raise NotImplementedError("Trimmed for scaffold reference")

  def make_join_list(self, indexes, left_df, right_df, keep_columns, side='both'):
    raise NotImplementedError("Trimmed for scaffold reference")

  def rank_merge_methods(self, context, flow, state, valid_col_list):
    # Determine the top merge styles based on context, and store results in 'delimiter' or 'ordering' slot
    raise NotImplementedError("Trimmed for scaffold reference")

  def fill_join_tab_source(self, context, flow, state, world):
    # If the agent has not filled the source slots during NLU, then do so now
    raise NotImplementedError("Trimmed for scaffold reference")

  def fill_coverage_ratio(self, flow, world):
    # Fill the preparation function if it is empty, then use it to calculate the coverage rate
    raise NotImplementedError("Trimmed for scaffold reference")

  def set_default_preparation(self, flow, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def calculate_coverage(self, flow, left_df, right_df, left_columns, right_columns):
    raise NotImplementedError("Trimmed for scaffold reference")

  def rank_checkbox_opt(self, context, flow, frame, valid_col_dict):
    # Model ranks the most likely columns to keep after merging two tables, and store them in the Target slot
    raise NotImplementedError("Trimmed for scaffold reference")

  def generate_target_name(self, context, flow):
    raise NotImplementedError("Trimmed for scaffold reference")

  def join_tables(self, context, state, world):
    """Supports {05A} by deciding which columns within two separate tables should be merged.
    Upon success, we also need to update across the entire world, including prompts and metadata"""
    flow = state.get_flow(flow_type='join')
    frame, state = self.initialize_merge_frame(flow, state, world)

    if flow.slots['source'].is_verified() and not flow.is_uncertain:
      flow, grounding, reroute = self.ground_to_reality(flow, state, world)
      if reroute: return frame, state

      if any([entity['rel'] == '' for entity in flow.slots['source'].values]):
        flow = self.align_connection_columns(context, flow, grounding)

      if flow.slots['target'].check_if_filled():
        if not flow.slots['coverage'].filled:
          flow = self.fill_coverage_ratio(flow, world)

        if flow.slots['coverage'].check_if_filled():
          frame, state = self.complete_table_join(context, flow, state, world)
          if frame.is_successful():
            flow.completed = True
        elif flow.stage == 'proactive-cleaning':
          flow, frame = self.clear_interjected_action(context, flow, state, world)
        elif flow.slots['tag'].check_if_filled():
          flow, state = self.determine_join_preparation(context, flow, grounding, state)
        else:
          flow, state = self.predict_tag_type(context, flow, grounding, state, world)
      else:
        self.actions.add('INTERACT')
        flow.stage = 'checkbox-opt'  # have the user select or deselect checkboxes on the columns they want to keep
        flow, frame = self.rank_checkbox_opt(context, flow, frame, world.valid_columns)

    elif flow.slots['source'].filled:
      flow, frame, state = self.verify_table_join(context, flow, state, world)
    else:
      flow, state = self.fill_join_tab_source(context, flow, state, world)
      if flow.slots['source'].check_if_filled():
        frame, state = self.join_tables(context, state, world)

    # we are dealing with two tables rather than just one, so the alignment check won't set the raw table
    frame.raw_table = state.current_tab  # therefore we set it manually to ensure the data can be fetched
    return frame, state

  def verify_table_join(self, context, flow, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def clear_interjected_action(self, context, flow, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def determine_join_preparation(self, context, flow, grounding, state):
    raise NotImplementedError("Trimmed for scaffold reference")

  def _basic_preparation(self, context, flow, grounding, state, prediction):
    raise NotImplementedError("Trimmed for scaffold reference")

  def _intermediate_preparation(self, flow, state, prediction, valid_col_dict):
    raise NotImplementedError("Trimmed for scaffold reference")

  def _advanced_preparation(self, flow, state, prediction):
    raise NotImplementedError("Trimmed for scaffold reference")

  def frame_state_control(self, flow, state, tab_name, frame):
    raise NotImplementedError("Trimmed for scaffold reference")

  def ground_to_reality(self, flow, state, world):
    """ Make sure we have the correct number of source tables and columns (left and right) """
    raise NotImplementedError("Trimmed for scaffold reference")

  def predict_tag_type(self, context, flow, grounding, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def contains_duplicates(self, source_dict, tab_name1, tab_name2):
    # Returns True if the subset of columns in each table contains duplicates, and False otherwise
    raise NotImplementedError("Trimmed for scaffold reference")

  def review_merge_conflicts(self, frame, flow, data_schema):
    raise NotImplementedError("Trimmed for scaffold reference")

  def append_rows(self, context, state, world):
    """ Supports {05B} where it is possible to concatenate two tables vertically """
    raise NotImplementedError("Trimmed for scaffold reference")

  def verify_source_alignment(self, convo_history, flow, state):
    raise NotImplementedError("Trimmed for scaffold reference")

  def merge_columns(self, context, state, world):
    """Supports {05C} by deciding how to create a new column based on existing ones """
    raise NotImplementedError("Trimmed for scaffold reference")

  def complete_merge_cols(self, context, flow, state):
    # start by unpacking all the information from the flow slots
    raise NotImplementedError("Trimmed for scaffold reference")

  def custom_column_merge(self, flow, state):
    # Handles custom merge actions by executing the user's custom code and updating the database
    raise NotImplementedError("Trimmed for scaffold reference")

  def call_external_api(self, context, state, world):
    # Supports {456} by calling an external API to retrieve a new table and updating the database
    raise NotImplementedError("Trimmed for scaffold reference")
