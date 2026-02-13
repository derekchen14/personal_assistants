# NOTE: 23 of 25 methods trimmed for scaffold reference. See git history for full implementations.
import json
import pandas as pd
from collections import Counter

from backend.prompts.mixins.for_analyze import *
from backend.prompts.for_executors import combine_cte_prompt
from backend.prompts.for_nlu import metric_name_prompt, segment_metric_prompt
from backend.utilities.pex_helpers import *
from backend.utilities.nlu_helpers import compile_operations_prompt
from backend.utilities.search import metric_name_finder
from backend.utilities.manipulations import get_row_limit

from utils.help import flow2dax
from backend.modules.flow.formulas import Formula, Expression, Clause
from backend.components.engineer import PromptEngineer
from backend.components.frame import Frame

class AnalyzeMixin:
  """ Methods that calculate metrics or KPI without changing the underlying data """

  def query_action(self, context, state, world):
    # generates a SQL query for the user's request based on Analyze(query) Flow
    flow = state.get_flow(flow_type='query')

    if flow.slots['source'].filled and not flow.is_uncertain:
      # passing state.entities (instead of setting error=True) preserves the state.thought
      frame = self.default_frame(state, state.entities)

      if flow.slots['operation'].filled:
        flow, reroute = query_rerouting(flow)
        if reroute: return frame, state
        flow = self.decide_time_range(context, flow, state, world, required=False)
        db_output, sql_query = self.database.query_data(context, flow, state, world)

        if sql_query == 'error':
          frame.signal_failure('code_generation', db_output.strip()) # db_output is the error message
        else:
          frame = self.validate_dataframe(db_output, sql_query, 'sql', state)
          state = self.backfill_underlying_flow(context, flow, frame, state)

      elif flow.is_uncertain:
        self.actions.add('CLARIFY')
        state.ambiguity.declare('specific', flow='query', slot='what exactly needs to be calculated')
      else:
        prompt = compile_operations_prompt(context.compile_history(), flow, state)
        raw_output = self.api.execute(prompt, version='claude-sonnet')
        prediction = PromptEngineer.apply_guardrails(raw_output, 'json')
        if flow.fill_slot_values(state.current_tab, prediction):
          frame, state = self.query_action(context, state, world)
        else:
          self.actions.add('CLARIFY')
          state.ambiguity.declare('specific', flow='query', slot='what aggregation operations are needed')

    else:
      self.actions.add('CLARIFY')
      state.ambiguity.declare('partial')
      frame = self.default_frame(state, state.entities)

    if frame.is_successful() and not state.ambiguity.present():
      if flow.slots['operation'].filled:
        state.slices['operations'] = flow.slots['operation'].values
      if state.has_issues:
        frame = attach_issues_entity(flow, frame, state, world)
      flow, world = query_visualization(self.api, context, flow, frame, world)
      state, world = proactive_validation(self.api, context, flow, frame, state, world)
      flow.completed = True
    return frame, state

  def measure_action(self, context, state, world):
    """ generates a complex SQL query for the users's request based on Analyze(measure) Flow {002}
    When the metric is:
      * initialized - metric will have a name and Formula, but expression is empty and variables == None
      * filled - expression present, first level of variables are named, clauses are empty
      * populated - expression present, all variables are filled down to clauses, which have predicted values
      * verified - expression present, variables are verified, clauses have verified values
    It is the job of NLU or the referring flow to initialize and fill the metric.
      * `contemplate` or `measure_action` is reponsible for populating the metric variables with entities
      * Metric Builder, materialized views, or other user interaction is necessary to verify the metric
      * `complete_measurement` is responsible for querying the database and returning the final result
    """
    raise NotImplementedError("Trimmed for scaffold reference")

  def all_columns_ambiguity(self, flow, state):
    # we simply grabbed all columns from   the table, without actually checking which ones are relevant
    raise NotImplementedError("Trimmed for scaffold reference")

  def full_formula_naming(self, flow):
    # make sure that the formula name includes a full name (expanded) and short name (acronym)
    raise NotImplementedError("Trimmed for scaffold reference")

  def fully_populate_variables(self, context, flow, state):
    # populate the remaining variables in Expression all the way down to the Clauses
    raise NotImplementedError("Trimmed for scaffold reference")

  def refill_source_slot(self, flow, formula_json):
    # refill the source slot with the populated formula clauses
    raise NotImplementedError("Trimmed for scaffold reference")

  def verify_formula_variables(self, context, flow, state, tab_col_str):
    # review the user's utterance to see if they have explicitly verified the predicted clauses
    raise NotImplementedError("Trimmed for scaffold reference")

  def revise_metric_expression(self, context, flow, state, world):
    # revise the metric expression based on the user's utterance
    raise NotImplementedError("Trimmed for scaffold reference")

  def predict_new_expression(self, context, flow, state, templates, world):
    # generate the variables within the metric expression, all the way down to the clause entities if possible
    raise NotImplementedError("Trimmed for scaffold reference")

  def complete_segmentation(self, context, flow, frame, state, tab_col_str, world):
    # start by unpacking the slot information to build up the prompts
    raise NotImplementedError("Trimmed for scaffold reference")

  def complete_measurement(self, context, flow, state, tab_col_str):
    raise NotImplementedError("Trimmed for scaffold reference")

  def parse_generated_variable(self, raw_code):
    # parse the raw output from the variable generation prompt to extract the alias and SQL code
    raise NotImplementedError("Trimmed for scaffold reference")

  def clarify_latest_formula(self, context, flow, formula, state):
    # ask the user for feedback about the latest formula expression and what to do next
    raise NotImplementedError("Trimmed for scaffold reference")

  def measure_rerouting(self, context, flow, state, world):
    """ Determines whether the metric is a simple query, a basic metric, a segmentation process, or insight detection
    based on the number of predicted metrics to calculate. """
    raise NotImplementedError("Trimmed for scaffold reference")

  def segment_rerouting(self, context, flow, state, world):
    # See measure_rerouting method for more details
    raise NotImplementedError("Trimmed for scaffold reference")

  def build_variables_stage(self, flow, state):
    raise NotImplementedError("Trimmed for scaffold reference")

  def pivot_table(self, context, state, world):
    """ Supports {01A} by creating a direct table (not a derived table like the Query flow) composed of
    at least one grouping and at least two columns involving aggregations, filters, or additional grouping """
    raise NotImplementedError("Trimmed for scaffold reference")

  def fill_pivot_target(self, context, flow, world):
    # decide whether a new table is needed, and if so, what an appropriate name should be
    raise NotImplementedError("Trimmed for scaffold reference")

  def backfill_underlying_flow(self, context, flow, frame, state):
    """ When we create a pivot table, we also need to backfill the underlying flow that created it """
    if flow.interjected:
      prev_flow = state.get_flow(allow_interject=False)

      match flow.name():
        case 'plot': state = self.backfill_from_plot(context, flow, prev_flow, state)
        case 'segment': state = self.backfill_from_segment(context, flow, prev_flow, state)
        case 'pivot': state = self.backfill_from_pivot(context, flow, prev_flow, frame, state)
        case _: self.write_to_scratchpad(flow, prev_flow, frame.get_data())

      self.actions.clear()
      underlying_dax = flow2dax(prev_flow.name())

      state.flow_stack.pop()  # remove the stack_on flow
      state.store_dacts(dax=underlying_dax)  # point back to the underlying flow
      state.keep_going = True
    return state

  def backfill_from_pivot(self, context, curr_flow, prev_flow, frame, state):
    raise NotImplementedError("Trimmed for scaffold reference")

  def segment_analysis(self, context, state, world):
    """ Supports {02D} by creating a custom metric that requires additional segmentation to calculate """
    raise NotImplementedError("Trimmed for scaffold reference")

  def establish_metric_expression(self, context, flow, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def pred_to_expression(self, formula_json):
    # Convert a JSON formula into an Expression object with nested Expressions and Clauses.
    raise NotImplementedError("Trimmed for scaffold reference")

  def breakdown_into_buckets(self, context, flow, state, tab_col_str):
    # figure out the target columns stored in segmentation slot, and also the steps to bucket or categorize the segments
    raise NotImplementedError("Trimmed for scaffold reference")

  def identify_segmentation(self, context, flow, state, world):
    # figure out the source column(s) for segmentation, as well as the type of segmentation
    raise NotImplementedError("Trimmed for scaffold reference")

  def handle_segment_clarify(self, context, flow, state, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def contains_time_triggers(self, context, flow):
    # Determines if time range analysis is needed based on conversation context.
    raise NotImplementedError("Trimmed for scaffold reference")

  def exist_time_columns(self, world):
    raise NotImplementedError("Trimmed for scaffold reference")

  def decide_time_range(self, context, flow, state, world, required=True):
    raise NotImplementedError("Trimmed for scaffold reference")

  def describe_action(self, context, state, world):
    # Supports {014} by preparing a preview of the data
    raise NotImplementedError("Trimmed for scaffold reference")

  def check_existence(self, context, state, world):
    # Supports {14C} by helping user answer the question, "Is there a column for X?"
    raise NotImplementedError("Trimmed for scaffold reference")

  def recommend_action(self, context, state, world):
    # Generates a recommendation for the user about what to do next
    raise NotImplementedError("Trimmed for scaffold reference")

  def inform_metric(self, context, state, world):
    # Provides information about how a particular metric is calculated
    raise NotImplementedError("Trimmed for scaffold reference")

  def define_metric(self, context, state, world):
    # Defines a metric based on a formula and saves it as a user preference
    raise NotImplementedError("Trimmed for scaffold reference")
