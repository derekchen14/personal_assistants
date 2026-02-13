# NOTE: 28 of 30 methods trimmed for scaffold reference. See git history for full implementations.
import re
import math
import random
import numpy as np
import pandas as pd
from collections import defaultdict
from utils.help import flow2dax

from backend.prompts.mixins.for_clean import *
from backend.prompts.grounding.clean_prompts import update_flow_prompt
from backend.assets.ontology import style_mapping, common_tlds, NA_string, default_limit
from backend.components.engineer import PromptEngineer
from backend.components.frame import Frame
from backend.components.metadata import MetaData
from backend.utilities.manipulations import *

class CleanMixin:
  """ Methods to update the values or remove errors to clean up the data """

  def update_action(self, context, state, world):
    # Router for {006} to decide between cleaning a table with or without issues, also marks flow as completed when done
    flow = state.get_flow(flow_type='update')

    if flow.is_uncertain:
      self.actions.add('CLARIFY')
      flow.is_uncertain = False
      state.ambiguity.declare('specific')
      frame = Frame(state.current_tab)
      return frame, state

    if flow.is_newborn:
      reroute, flow = self.update_rerouting(context, flow, state, world)
      if reroute: return None, state

    if state.has_issues:
      if state.natural_birth:
        frame, state = self.modify_issues(flow, context, state, world)
      else:
        frame, state = self.interactive_clean(flow, context, state, world)
    else:
      frame, state = self.update_values(context, flow, state, world)

    if frame.is_successful():
      flow.completed = True
      unique_tables = set([ent['tab'] for ent in flow.slots['target'].values])
      if len(unique_tables) > 1:
        updated_tabs = list(unique_tables)
        frame.properties['tabs'] = updated_tabs
      else:
        updated_tabs = [state.current_tab]

      if 'rename' in frame.code:   # column header has likely been renamed
        self.replace_shadow_keys(flow)
        self.update_system_prompt(updated_tabs, world, context, flow)
      else:
        self.database.db.complete_registration(state.current_tab)
    return frame, state

  def update_rerouting(self, context, flow, state, world):
    # first check if the user is trying to trigger a different flow
    raise NotImplementedError("Trimmed for scaffold reference")

  def interactive_clean(self, flow, context, state, world):
    # Deterministically resolve the typos inside inside the similar terms flow
    raise NotImplementedError("Trimmed for scaffold reference")

  def modify_issues(self, flow, context, state, world):
    """ Supports {006} when a Detect Flow is active, so we need to resolve those issues """
    raise NotImplementedError("Trimmed for scaffold reference")

  def update_values(self, context, flow, state, world):
    """ Supports {006} by deciding what content to change, then notifies the database accordingly
    Upon success, we also need to update across the entire world, including prompts and metadata """
    frame = world.frames[-1] if world.has_data() else self.default_frame(state, world.valid_columns)

    if flow.slots['source'].filled:
      convo_history = context.compile_history(look_back=3)

      if flow.slots['target'].filled:
        source_cols, source_tabs = [], []
        for entity in flow.slots['source'].values:
          col_name, tab_name = entity['col'], entity['tab']
          tab_schema = world.metadata['schema'][tab_name]
          col_subtype = tab_schema.get_type_info(col_name)['subtype']
          col_string = f"{col_name} ({col_subtype})"

          source_cols.append(col_string)
          source_tabs.append(tab_name)

        if len(source_cols) == 1:
          loc_rep = f"{source_cols[0]} column in {source_tabs[0]}"
        else:
          tab_list = PromptEngineer.array_to_nl(source_tabs, connector='and')
          col_list = PromptEngineer.array_to_nl(source_cols, connector='and')
          if len(source_cols) == len(world.valid_columns[source_tabs[0]]):
            col_list = "all"
          loc_rep = f"{col_list} columns in {tab_list}"

        table_desc = self.database.table_desc
        tht_rep = "I can update just as the user requested" if len(state.thought) == 0 else state.thought
        prompt = update_prompt.format(df_tables=table_desc, history=convo_history, location=loc_rep, thought=tht_rep)
        db_output, code = self.database.manipulate_data(context, state, prompt, world.valid_tables)
        if code == 'error':
          frame.signal_failure('code_generation', db_output.strip())
        else:
          frame = self.validate_dataframe(db_output, code, 'pandas', state, tab_type='direct')

      else:
        prediction, flow = self.predict_grounding_slots(convo_history, flow, state, world)
        if flow.fill_slot_values(state.current_tab, prediction):
          frame, state = self.update_values(context, flow, state, world)
        else:
          self.actions.add('CLARIFY')
          state.ambiguity.declare('partial', flow='update')
    else:
      self.actions.add("CLARIFY")
      frame.signal_failure('custom', 'it is unclear what the user would like to update')
      state.ambiguity.declare('partial', flow='update')
    return frame, state

  def predict_grounding_slots(self, convo_history, flow, state, world):
    """ Predicts the source and target entities for the update flow when the user has not provided them """
    raise NotImplementedError("Trimmed for scaffold reference")

  def replace_shadow_keys(self, flow):
    raise NotImplementedError("Trimmed for scaffold reference")

  def select_issue_rows(self, flow, previous_frame, issue_col, main_df):
    """ Get all issue rows from ShadowDB to address based on our understanding of the user's intent """
    raise NotImplementedError("Trimmed for scaffold reference")

  def validate_action(self, context, state, world):
    # Supports {36D} by validating the data within the column as belonging to a predefined set
    raise NotImplementedError("Trimmed for scaffold reference")

  def review_validation_results(self, col_name, convo_history, flow):
    raise NotImplementedError("Trimmed for scaffold reference")

  def complete_data_validation(self, column, flow, frame):
    raise NotImplementedError("Trimmed for scaffold reference")

  def backup_verification(self, col_name, convo_history, flow):
    # check the selected terms against other model predictions to see if they match
    raise NotImplementedError("Trimmed for scaffold reference")

  def format_action(self, context, state, world):
    # Supports {36F} by standardizing the data within the column to conform to a specific format
    raise NotImplementedError("Trimmed for scaffold reference")

  def format_rerouting(self, context, flow, frame, state):
    raise NotImplementedError("Trimmed for scaffold reference")

  def initialize_format_tracker(self, column, display_col, tab_name, flow):
    raise NotImplementedError("Trimmed for scaffold reference")

  def ask_conflict_resolution(self, context, flow, state):
    raise NotImplementedError("Trimmed for scaffold reference")

  def initialize_alignment(self, context, col_props, display_column, flow, state, tab_schema):
    """ alignment represents a function that verifies if a row value matches the target format """
    raise NotImplementedError("Trimmed for scaffold reference")

  def reformat_conflicting_rows(self, context, entity, flow, state):
    raise NotImplementedError("Trimmed for scaffold reference")

  def reformat_conflicting_text(self, context, flow, state, col_name, table_df):
    raise NotImplementedError("Trimmed for scaffold reference")

  def reformat_conflicting_datetime(self, context, flow, state, col_name, table_df):
    raise NotImplementedError("Trimmed for scaffold reference")

  def impute_missing_values(self, context, state, world):
    """ Supports {06B} by filling in missing values within the column based on the observed or external data. """
    raise NotImplementedError("Trimmed for scaffold reference")

  def predict_grounding_source(self, context, flow, frame, state, col_name, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def function_imputation(self, context, flow, state, table_df, target_col):
    raise NotImplementedError("Trimmed for scaffold reference")

  def mapping_imputation(self, convo_history, flow, frame, is_blank, target_col, table_df):
    raise NotImplementedError("Trimmed for scaffold reference")

  def identify_blank_rows(self, target_col, table_df):
    raise NotImplementedError("Trimmed for scaffold reference")

  def imputation_rerouting(self, convo_history, flow, state, table_df, data_preview=None):
    raise NotImplementedError("Trimmed for scaffold reference")

  def pattern_fill(self, context, state, world):
    # Supports {0BD} by flash filling the data within the column based on the pattern in the existing data
    raise NotImplementedError("Trimmed for scaffold reference")

  def pattern_rerouting(self, context, flow, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def remove_duplicates(self, context, state, world):
    """Supports {7BD} by merging duplicate rows. If any conflicts arise, signal the Merge Style stage """
    raise NotImplementedError("Trimmed for scaffold reference")

  def prepare_duplicate_cards(self, frame, flow):
    # Sample a batch of conflict cards from the detector representing potential duplicates
    raise NotImplementedError("Trimmed for scaffold reference")

  def complete_duplicate_removal(self, frame, flow, context, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def review_duplicate_rows(self, frame, flow, data_schema):
    """ review duplicates that may have caused conflicts, and decide how to merge them """
    raise NotImplementedError("Trimmed for scaffold reference")

  def merge_rows(self, row_groups, flow):
    # row_groups is a list of lists, where each inner list contains the indices of rows that should be merged
    raise NotImplementedError("Trimmed for scaffold reference")

  def combine_values(self, subset, column, style, bool_setting=True):
    raise NotImplementedError("Trimmed for scaffold reference")

  def combine_content(self, subset, column, sep):
    raise NotImplementedError("Trimmed for scaffold reference")

  def rank_row_merge_styles(self, context, flow, valid_col_list):
    # Determine the top merge styles based on context, and store them in the Style slot
    raise NotImplementedError("Trimmed for scaffold reference")

  def assign_datatype(self, context, state, world):
    # Supports {06E} by setting the data type of the column to a specific format
    raise NotImplementedError("Trimmed for scaffold reference")

  def compile_row_samples(self, rows, table, col_name):
    raise NotImplementedError("Trimmed for scaffold reference")

  def undo_action(self, context, state, world):
    # Supports {06F} by undoing the last action taken on the table
    raise NotImplementedError("Trimmed for scaffold reference")

  def persist_preference(self, context, state, world):
    # Supports {068} by saving or updating a user preference
    raise NotImplementedError("Trimmed for scaffold reference")
