import re
import random
from collections import Counter, defaultdict

from backend.components.engineer import PromptEngineer
from backend.components.metadata import MetaData
from backend.components.metadata.issues import Blank, Concern, Problem, Typo
from backend.modules.flow.slots import *
from backend.modules.flow.parents import *
from backend.modules.experts.detector import DuplicateDetector
from backend.modules.experts.tracker import IssueTracker
from backend.assets.ontology import common_abbreviations, valid_operations, type_hierarchy

# 8 Analyze Flows
class QueryFlow(AnalyzeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    # if asking for a distribution --> relabel as "query + visualize"
    self.flow_type = 'query'    # {001}
    self.goal = 'query the spreadsheet to answer a question'

    ops_phrases = valid_operations[self.flow_type]
    self.slots = {
      'source': SourceSlot(1, 'column'),          # name of table and columns to query
      'operation': FreeTextSlot(ops_phrases),     # operations to help determine filtering, grouping, and sorting
      'time': RangeSlot(options=[]) }             # optional time range for the query

  # fill_slot_values is implemented in the parent class

class MeasureFlow(AnalyzeParentFlow):
  """Calculates a metric, represented by a formula. The structure comes from the Expression stored in the Formula.
  Completed metrics will be stored as slices within the state object, and eventually within the StorageDB as well.
  Notably, all metrics are created on the fly, and do not come with any pre-defined variables or clauses"""
  def __init__(self, valid):
    super().__init__(valid)
    # also, this flow should always reference MetaData to see if a metric has been pre-defined already
    self.flow_type = 'measure'    # {002}
    self.clarify_attempts = 2
    self.goal = 'calculate a specific marketing metric or KPI'

    self.slots = {
      'source': SourceSlot(2, 'column'),          # entities used create clauses, that then build up a metric
      'metric': FormulaSlot(),                    # stores canonical expression object with its variables
      'time': RangeSlot([])                       # optional time range for calculating the metric
    }

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of measure flow output stream is a 'thought' string, without explicit entity labels
    Instead, the entities are identified within the flow thought as columns within angle brackets
    This follow the divide_and_conquer method as described in [0500], see Ticket [0563] for more details
    """
    candidate_metrics = re.findall(r'\(([^)]+)\)', labels['prediction']['full_stream'])
    candidate_columns = re.findall(r'<([^>]+)>', labels['prediction']['full_stream'])

    for metric in candidate_metrics:
      if metric in common_abbreviations:
        acronym, expanded = metric, common_abbreviations[metric]
        self.slots['metric'].assign_metric(acronym, expanded)
        break

    for col_name in candidate_columns:
      # The flow thought doesn't capture table information, so we leave it blank, and hope entity validation can fill it in
      candidate_ent = {'tab': '', 'col': col_name.strip()}
      self.validate_entity(candidate_ent, current_tab)
    return self.is_filled()

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of measure flow contemplation, sets a Formula as the metric slot
    {
      'long': 'Conversion Rate',
      'short': 'CVR'
    }
    """
    if raw_pred['long'] in ['unsure', 'none']:
      self.is_uncertain = True
      if raw_pred['short'] == 'none':
        self.fall_back = '001'
      return False

    acronym, expanded = raw_pred['short'], raw_pred['long']
    self.slots['metric'].assign_metric(acronym, expanded)
    return self.is_filled()

  def fill_expression_variables(self, current_tab, raw_pred):
    """ Fill the variables within the expression that make up the formula.
    {
      'variables': [
        {'conversions': ['PurchaseID']},
        {'visits': ['ActivityID', 'ActivityType', 'ReferrerURL']}
      ]
    }
    """
    self.slots['metric'].formula.drop_unverified()  # we don't trust previously predicted clauses

    for prediction in raw_pred['variables']:
      for var_name, column_names in prediction.items():
        for col_name in column_names:
          if col_name == 'unsure':
            self.is_uncertain = True
            continue
          tab_name = self.column_to_table(col_name, current_tab)
          if len(tab_name) > 0:
            self.slots['metric'].formula.add_clause(var_name, tab_name, col_name)
    return self.slots['metric'].is_populated()

  def is_filled(self):
    for slot in self.slots.values():
      slot.check_if_filled()

    source_filled = self.slots['source'].filled
    metric_verified = self.slots['metric'].is_verified()
    return source_filled and metric_verified

class SegmentFlow(MeasureFlow):
  """ Calculates a metric that often requires multiple steps to complete. Similar to how a PivotFlow builds on top of
  the QueryFlow by requiring grouping, the SegmentFlow builds on top of the MeasureFlow by requiring segmentation.
  When such a complex metric is composed, the assumption is that multiple steps are needed, such as:
    - filtering for specific values or time periods based on supporting columns (time is optional in MeasureFlow)
    - aggregating certain columns to create new segments, which are then inserted as staging columns
    - combining multiple variables to establish the full Expression, representing the final metric
  This flow covers at most one metric because calculations involving more than 1 are routed to InsightFlow instead.
  """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'segment'  # {02D}
    self.clarify_attempts = 4
    self.goal = 'analyze a metric by segmenting along some dimension'
    self.segment_types = ['categorical', 'numeric', 'proximity', 'temporal']

    segment_keys = ['table', 'column', 'type', 'dimension']
    self.slots = {
      'source': SourceSlot(2, 'column'),          # the entities used to calculate the custom metric
      'metric': FormulaSlot(),                    # stores canonical expression object with its variables
      'segment': DictionarySlot(segment_keys),    # dimensions to segment the data, as well as tab and col
      'steps': FreeTextSlot([], 'optional'),      # the steps within the segmentation process
      'time': RangeSlot([], priority='required')  # required time period for filtering the data
    }

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of multi-step flow output stream is a 'thought' string, without explicit entity labels
    Instead, the entities are identified within the flow thought as columns within angle brackets
    """
    candidate_metrics = re.findall(r'\(([^)]+)\)', labels['prediction']['full_stream'])
    candidate_columns = re.findall(r'<([^>]+)>', labels['prediction']['full_stream'])

    for metric in candidate_metrics:
      if metric in common_abbreviations:
        acronym, expanded = metric, common_abbreviations[metric]
        self.slots['metric'].assign_metric(acronym, expanded)
        break

    for col_name in candidate_columns:
      # The flow thought doesn't capture table information, so we leave it blank, and hope entity validation can fill it in
      self.validate_entity({'tab': '', 'col': col_name}, current_tab)
    return self.is_filled()

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of multi-step flow contemplation
    {
      'long': 'Conversion Rate',
      'short': 'CVR'
    }
    """
    if raw_pred['long'] in ['unsure', 'none']:
      self.is_uncertain = True
      if raw_pred['short'] == 'none':
        self.fall_back = '001'
      return False

    acronym, expanded = raw_pred['short'], raw_pred['long']
    return self.slots['metric'].assign_metric(acronym, expanded)

  def fill_segmentation_steps(self, prediction):
    """ Decide on the different dimensions or buckets to create for the multi-step analysis
    {
      "table": "RenderActivity",
      "column": "ErrorHour",
      "steps": [
        "bucket into hourly segments",
        "filter for error_type is not null",
        "convert each fab_timestamp to a format which rounds to the nearest hour"
      ]
    }
    """
    tab_name, col_name = prediction['table'], prediction['column']
    if tab_name == 'unsure' or col_name == 'unsure':
      self.is_uncertain = True
      return False
    else:
      self.slots['segment'].add_one('column', prediction['column'])
      self.slots['segment'].add_one('table', prediction['table'])
    self.slots['segment'].check_if_filled()

    if prediction['column'] in [ent['col'] for ent in self.slots['source'].values]:
      self.slots['steps'].add_one('none')  # use an existing column, so no steps are needed
    else:
      for step in prediction['steps']:
        self.slots['steps'].add_one(step)
    return self.slots['steps'].check_if_filled()

class PivotFlow(AnalyzeParentFlow):
  """Creates variables that are immediately materialized as a permanent, pivot table
  Furthermore, PivotFlow is distinguished from tables created by StagingFlow because pivot tables:
    - must include at least one grouping operation, whereas grouping is optional in StagingFlow
    - must have three additional columns or more that require filtering, aggregation, or further grouping
    - can be called directly by the user, while StagingFlow is only accessible internally by the agent
  """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'pivot'  # {01A}
    self.goal = 'create a pivot table that groups, filters, and aggregates multiple columns to form variables'
    ops_phrases = valid_operations[self.flow_type]

    self.slots = {
      'source': SourceSlot(2, 'column'),      # entities for filtering, grouping, and aggregation
      'target': TargetSlot(1, 'table'),       # name of the new table to create
      'operation': FreeTextSlot(ops_phrases), # operations to help determine each level of grouping
      'time': RangeSlot(options=[]) }         # optional time range for filtering the data

class DescribeFlow(AnalyzeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'describe'   # {014}
    self.goal = 'view descriptive statistics of the contents within the spreadsheet'
    fact_options = ['statistics', 'range', 'preview', 'size', 'count', 'existence']

    self.slots = {
      'source': SourceSlot(1, 'column'),          # the table or column to describe
      'facts': ProposalSlot(fact_options)         # which facts the user wants to know about
    }

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of describe flow contemplation
    {
      "facts": ["existence", "preview"]
    }
    """
    for fact in raw_pred['facts']:
      self.slots['facts'].add_one(fact)
    return self.is_filled()

class ExistFlow(AnalyzeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'exist'      # {14C}
    self.goal = 'check if a specific value or column exists within the spreadsheet'

    self.slots = {
      'source': SourceSlot(1, 'column'),          # the table or column to describe
      'preview': TargetSlot(1, 'column', 'optional')   # entities to peek at to make a decision for 'existence'
    }

class InformFlow(AnalyzeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'inform'     # {248}
    self.goal = 'provide information how a particular metric is calculated'

    self.slots = {
      'source': SourceSlot(2, 'column'),          # columns used to calculate the metric, notably not filled by the user
      'metric': CategorySlot([]),                 # the name of the metric the user wants to know more about
      'settings': DictionarySlot('optional') }    # any additional settings or parameters the user may have specified

class DefineFlow(AnalyzeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'define'     # {268}
    self.goal = 'define a metric based on a formula and save as a user preference'

    self.slots = {
      'source': SourceSlot(2, 'column'),          # columns used to calculate the metric
      'metric': FormulaSlot({}) }                 # the formula to calculate the new metric

# 7 Visualize Flows
class PlotFlow(VisualizeParentFlow):
  """ For graphs, figures, plots and other visualizations """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'plot'       # {003}
    self.entity_slot = 'source'
    self.goal = 'generate a visual representation of the data such as a graph or chart'

    ops_phrases = valid_operations[self.flow_type]
    self.slots = {
      'source': SourceSlot(1, 'column'),          # the columns to visualize
      'operation': FreeTextSlot(ops_phrases),     # operations to help determine the type of visualization
      'time': RangeSlot(options=[]) }             # optional time range to filter the data before plotting

  def fill_slot_values(self, current_tab, raw_pred):
      """Format of pivot flow contemplation
      [
        'group by day and ActivityType', 
        'aggregate count of activities', 
        'plot line chart of daily website traffic by activity type'
      ]
      """
      for pred_op in raw_pred:
          self.slots['operation'].add_one(pred_op)
      return self.is_filled()

class TrendFlow(VisualizeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'trend'    # {023}
    self.goal = 'identify a pattern or trend in the data by running some chart-based analysis'

    options = ['cluster', 'moving_average', 'correlation', 'regression', 'outlier']
    self.slots = {
      'chart': ChartSlot(),                       # holds the unique chart identifier
      'analysis': CategorySlot(options)           # the type of analysis to perform
    }

class ExplainFlow(VisualizeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'explain'    # {038}
    self.goal = 'generate an explanation or summary of the chart or graph'

    self.slots = {
      'chart': ChartSlot('elective'),                 # which chart to explain
      'source': SourceSlot(1, 'table', 'elective'),   # the table the chart is based on
    }

class ReportFlow(VisualizeParentFlow):
  def __init__(self, valid, datetimes):
    super().__init__(valid)
    self.flow_type = 'report'     # {23D}
    self.goal = 'manage dashboard settings, such as recurring reports or data refresh rates'

    self.slots = {
      'chart': ChartSlot(),                           # the chart to add to the dashboard
      'time': RangeSlot(datetimes, recurrence=True),  # the recurrence settings
    }

class SaveFlow(VisualizeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'save'       # {38A}
    self.goal = 'save the current visualization to the dashboard or export to a file'

    self.slots = {
      'chart': ChartSlot(1, 'table'),                     # the chart to save
      'destination': ChartSlot(1, 'table', 'elective'),   # the location in the dashboard to save the chart
      'filepath': ExactSlot('elective')                   # which location to save the chart to
    }

class DesignFlow(VisualizeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'design'     # {136}
    self.goal = 'design the layout and appearance of the dashboard'

    viz_options = ['bar', 'line', 'scatter', 'pie', 'funnel']
    self.slots = {
      'chart': ChartSlot(),                                   # the chart to design
      'type': CategorySlot(viz_options, 'apply', 'elective'), # the type of visualization to use
      'operation': FreeTextSlot(['apply', 'filter']),         # operations to help determine the type of visualization
      'settings': DictionarySlot('optional')                  # additional settings or parameters for the figure
    }

class StyleFlow(VisualizeParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'style'      # {13A}
    self.entity_slot = 'source'
    self.goal = 'style the appearance of a permanent derived table'

    instructions = "what formatting change to apply"
    examples = "often related to text styling such as 'underline', 'center align', 'text wrap', or 'red font'. \
      It may also be related to cell style such as 'top border', 'highlight yellow', or 'smaller column width'. \
      Finally, the target value may be related to format types such 'MM/DD/YYYY date', 'currency', or 'percentage'"

    self.slots = {
      'source': SourceSlot(1, 'table'),                 # the table to style
      'operation': FreeTextSlot(['apply', 'filter']),   # operations to help determine the type of styling
      'settings': DictionarySlot('optional')            # additional settings or parameters for the styling
    }

# 9 Clean Flows
class UpdateFlow(CleanParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    # when using a formula, ask for confirmation since it is more complicated
    self.flow_type = 'update'     # {006}
    self.goal = 'clean up the data within the table'

    self.slots = {
      'source': SourceSlot(1, 'cell'),
      'target': TargetSlot(1, 'column', 'optional'),
      'exact': ExactSlot('elective'),
      'function': FunctionSlot('elective') }

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of clean flow output
    {
      "source": [{"tab": "ProductAnalytics", "col": "product_name", "row": "New Balance - Men's Arrow"}],
      "target": [{"tab": "ProductAnalytics", "col": "price", "row": "= price / 100"}]
    }
    """
    # if labels.get('has_issues', False):
    #   self.fill_issue_rows(current_tab, labels)
    prediction = labels['prediction']
    for source_ent in prediction['source']:
      self.validate_entity(source_ent, current_tab)

    for target_ent in prediction['target']:
      if target_ent['row'].startswith('= '):
        target_ent['row'] = target_ent['row'][2:]
        target_ent['rel'] = 'function'
        self.slots['function'].value = target_ent['row']
      else:
        self.slots['exact'].add_one(target_ent['row'])
      self.slots['target'].add_one(**target_ent)
    return self.is_filled()

  def fill_issue_rows(self, current_tab, labels):
    """ Format of clean flow output [DEPRECATED]
    {
      "method": "some",   // all, some, beyond, ignore, unsure
      "rows": [351, 564, 595]
      "dataframe": "subset_df = issue_df[(issue_df['state'] == 'PA') & (issue_df['name'].isnull())]"
    }
    """
    self.slots['exact'].add_one(labels['prediction']['method'])

    if labels['prediction']['method'] == 'unsure':
      self.is_uncertain = True
    col_name = labels['issues_column']

    if 'dataframe' in labels['prediction']:
      code_snippet = labels['prediction']['dataframe']
      self.slots['source'].add_one(current_tab, col_name, row=code_snippet)
      self.code_generation = True

    elif 'rows' in labels['prediction']:
      if any([row_id < 0 for row_id in labels['prediction']['rows']]):
        self.slots['source'].add_one(current_tab, col_name)
      else:
        for row in labels['prediction']['rows']:
          self.slots['source'].add_one(current_tab, col_name, row)
    else:
      self.is_uncertain = True

  def get_representations(self):
    source_tab = self.slots['source'].values[0]['tab']
    loc_rep = f"Using the {source_tab} table, update "

    source_cols = list(set([entity['col'] for entity in self.slots['source'].values]))
    source_col_str = PromptEngineer.array_to_nl(source_cols, connector='or')
    source_rows = list(set([entity['row'] for entity in self.slots['source'].values]))
    source_row_str = PromptEngineer.array_to_nl(source_rows, connector='or')

    target_cols = list(set([entity['col'] for entity in self.slots['target'].values]))
    target_col_str = PromptEngineer.array_to_nl(target_cols, connector='and')
    target_rows = list(set([entity['row'] for entity in self.slots['target'].values]))
    target_row_str = PromptEngineer.array_to_nl(target_rows, connector='and')

    if target_row_str == 'header':
      target_row_str, target_col_str = target_col_str, target_row_str
      source_row_str, source_col_str = source_col_str, source_row_str

    if len(source_cols) == 1:
      loc_rep += f"{target_col_str}"
    else:
      loc_rep += f"{target_col_str} columns"

    if target_col_str == source_col_str:
      if source_row_str == 'all':
        loc_rep += f". "
      else:
        loc_rep += f" where the value is {source_row_str}. "
    elif source_row_str == 'header':
      loc_rep += f" in the header. "
    elif source_row_str == 'all':
      loc_rep += f" based on {source_col_str}. "
    else:
      loc_rep += f" where {source_col_str} is {source_row_str}. "

    if any([entity['rel'] == 'function' for entity in self.slots['target'].values]):
      loc_rep += "The formula to calculate "
    loc_rep += "the new "

    loc_rep += f"value is {target_row_str}." if len(target_rows) == 1 else f"values are {target_row_str}."
    return loc_rep

class ValidateFlow(CleanParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'validate'   # {36D}
    self.goal = 'validate the data within the column as belonging to a predefined set'
    self.unique_values = []

    self.slots = {
      'source': SourceSlot(1, 'column'),          # the column to validate
      'terms': FreeTextSlot(),                    # the predefined set of valid terms to validate against
      'mapping': DictionarySlot() }               # the mapping of all non-valid terms to an allowed term

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of validation flow slot filling
    {
      "groups": {
        "Free": ["Free user", "free", "free tier"],
        "Basic": ["basic", "standard"],
        "Pro": ["pro", "Pro user"]
    }}
    """
    for valid_term, invalid_terms in raw_pred['groups'].items():
      self.slots['terms'].values.append(valid_term)
      for invalid in invalid_terms:
        self.slots['mapping'].add_one(invalid, valid_term)
    return self.is_filled()

  def suggest_replies(self):
    """ Replies are a list of dictionaries with keys 'dax', 'text', and 'action' """
    positive_reply = {'dax': '36D', 'text': "Yes, looks good", 'action': 'accept'}
    negative_reply = {'dax': '36D', 'text': "No, different terms should be chosen", 'action': 'reject'}
    suggested_replies = [positive_reply, negative_reply]
    return suggested_replies

class FormatFlow(CleanParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'format'     # {36F}
    self.goal = 'standardize the data within the column to conform to a specific format'
    self.is_learning = False

    options = ['date', 'month', 'quarter', 'time', 'timestamp', 'week', 'email', 'phone', 'name', 'url', 'currency']
    self.slots = {
      'source': SourceSlot(1, 'column'),      # the column to standardize
      'format': CategorySlot([]),             # the specific format to standardize to (ie. MM/DD/YYYY)
      'subtype': CategorySlot(options),       # the data type to assign, such as phone, time, or email
      'alignment': FunctionSlot() }           # the function to apply to each row to standardize the format

  def fill_slot_values(self, col_subtype, raw_pred):
    """ Format of format flow contemplation
    {
      "datatype": "date",
      "formats": [ "MM-DD-YYYY", "Month D, YYYY", "MM/DD/YYYY" ]
    }
    """
    formats = raw_pred['formats']
    self.slots['format'].options = formats

    # fill immediately since the model believes the answer is obvious
    if len(formats) == 1:
      self.slots['format'].assign_one(formats[0])

    if raw_pred['datatype'] == 'unsure':
      if col_subtype == 'general':
        self.fall_back = '06E'
      else:
        self.is_uncertain = True
      return False

    self.slots['subtype'].assign_one(raw_pred['datatype'])
    return self.slots['format'].filled

  def is_datetime_subtype(self):
    if self.slots['subtype'].filled:
      subtype = self.slots['subtype'].value
      if subtype in ['date', 'month', 'quarter', 'time', 'timestamp', 'week']:
        return True
    return False

  def suggest_replies(self):
    """ Replies are a list of dictionaries with keys 'dax', 'text', and 'action' """
    suggested_replies = []
    for format_option in self.slots['format'].options:
      reply = {'dax': '36F', 'text': f"{format_option} format", 'action': format_option}
      suggested_replies.append(reply)
    return suggested_replies

class PatternFlow(CleanParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'pattern'     # {0BD}
    self.goal = 'fill the column based on the described pattern'
    self.entity_slot = 'target'

    self.slots = {
      'target': TargetSlot(1, 'column'),              # the main column that holds the repeating pattern
      'source': SourceSlot(1, 'column', 'optional'),  # any relevant columns that might need to be referenced
      'pattern': FreeTextSlot(),                      # description of the pattern to repeat
      'base': ExactSlot(),                            # the base value that serves as the starting point
      'snippet': FreeTextSlot() }                     # code snippet to apply repeatedly on the target column

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of pattern flow output stream
    {
      "table": "CustomerOrders",
      "target": "OrderDate",
      "support": ["OrderID", "CustomerID"],
    }
    """
    prediction = labels['prediction']
    tab_name = prediction['table']
    target_col = prediction['target']

    if target_col == 'unsure':
      self.is_uncertain = True
      return False
    else:
      self.slots['target'].add_one(tab_name, target_col)

    if target_col in self.valid_col_dict[tab_name]:
      self.slots['source'].add_one(tab_name, target_col)
    for support_col in prediction['support']:
      self.slots['source'].add_one(tab_name, support_col)
    return self.is_filled()

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of pattern flow contemplation
    {
      "pattern": "<short description>",
      "base": "2022-07-26",
      "snippet": "= df['Presentation Date'].shift(1) + pd.DateOffset(days=1)"
    }
    """
    for slot_key, slot_val in raw_pred.items():
      if slot_val == 'unsure':
        self.is_uncertain = True
      elif slot_key in self.slots:
        self.slots[slot_key].add_one(slot_val)

    return self.is_filled()

class DedupeFlow(CleanParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    # remove duplicate columns to keep unique user and datetime entries
    self.flow_type = 'dedupe'     # {7BD}
    self.goal = 'remove duplicate entries from the current table'
    self.entity_slot = 'removal'

    self.detector = DuplicateDetector()
    self.is_learning = False

    style_names = ['order', 'length', 'alpha', 'time', 'contains', 'binary', 'size', 'mean', 'question']
    setting_keys = ['detail', 'reference', 'boolean']
    self.slots = {
      'removal': RemovalSlot('column'),           # the column or columns to deduplicate
      'confidence': ProbabilitySlot(),            # confidence score that agent can handle the rest automatically
      'style': CategorySlot(style_names),         # the style used to determine which row to keep
      'settings': DictionarySlot(setting_keys, 'optional'),   # settings to determine exactly how to remove duplicates
      'candidate': ProposalSlot(style_names, 'optional'),     # candidate style used to resolve merge conflicts
      'function': FunctionSlot('optional') }      # the function used to determine how to resolve merge conflicts

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of Remove Duplicate flow output streams
    {"result": [
      {"tab": "CustomerContact", "col": "CustomerName"}
      {"tab": "CustomerContact", "col": "ContactNumber"}
    ]}
    """
    for entity in labels['prediction']['result']:
      self.validate_entity(entity, current_tab)
    if self.entity_values(size=True) == 0:
      self.is_uncertain = True
    return self.is_filled()

  def single_col_merge(self, table_df, col_name):
    # If the user only selects one column, then we can search for exact duplicates in the column
    col_series = table_df[col_name]
    groups_to_merge = []
    duplicates = col_series[col_series.duplicated(keep=False)]

    # Group the duplicates and get their index
    for value, group in duplicates.groupby(duplicates):
      if len(group) > 1:
        groups_to_merge.append(group.index.tolist())
    return groups_to_merge

  def detect_duplicates(self, current_df):
    duplicates = []

    # Use the tracker to find known row ids that should be removed from the dataframe
    for result in self.tracker.results:
      if result['resolution'] == 'merge':
        duplicates.extend(result['retire'])

    # Use the merge style to determine any remaining duplicates in the conflict groups
    merge_style = self.slots['style'].value
    reference_col = self.slots['settings'].value['reference']
    setting_detail = self.slots['settings'].value['detail']  # for text schema
    bool_setting = self.slots['settings'].value['boolean']

    for cardset in self.tracker.conflicts:
      cardset_ids = [card['row_id'] for card in cardset]
      subset = current_df.loc[cardset_ids]
      smc = subset[reference_col] if len(reference_col) > 0 else subset.iloc[:, 0]

      try:
        match merge_style:
          case 'order': keep_row = subset.iloc[0] if bool_setting else subset.iloc[-1]
          case 'time': keep_row = subset.sort_values(by=reference_col, ascending=bool_setting).iloc[0]
          case 'binary': keep_row = subset[smc == bool_setting].iloc[0]
          case 'contains': keep_row = subset[smc.astype(str).str.contains(setting_detail)].iloc[0]
          case 'size': keep_row = subset.iloc[smc.idxmax() if bool_setting else smc.idxmin()]
          case 'length': keep_row = subset.iloc[smc.astype(str).str.len().argmax() if bool_setting else smc.astype(str).str.len().argmin()]
          case 'alpha': keep_row = subset.sort_values(by=reference_col, ascending=bool_setting).iloc[0]
      except IndexError:
        # If there is an index error, then the subset is empty after filtering. For example, there are no True values
        keep_row = subset.iloc[0]

      for row_id in cardset_ids:
        if row_id != keep_row.name:
          duplicates.append(row_id)
    return duplicates

  def assign_default_style(self, finish):
    self.slots['style'].value = 'order'
    self.slots['settings'].value['detail'] = 'first'
    self.slots['settings'].value['boolean'] = True
    if finish:
      self.slots['confidence'].level = 1.0

  def rank_styles(self, current_styles):
    ranked = []
    seen = {'question', 'automatic'}   # initialize with guidance styles to ensure they are not included

    for style in current_styles:
      if style not in seen:
        ranked.append(style)
        seen.add(style)
    for style in self.slots['candidate'].options:
      if style not in seen:
        ranked.append(style)
        seen.add(style)

    flow_guidance_style = 'question' if self.slots['confidence'].level < 0.99 else 'automatic'
    ranked.insert(2, flow_guidance_style)
    return ranked

class DataTypeFlow(CleanParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'datatype'   # {06E}
    self.goal = 'set the data type of the column to a specific subtype from the ontology'
    self.properties = {}
    types = list(type_hierarchy.keys())
    subtypes = [sub for stypes in type_hierarchy.values() for sub in stypes]

    self.slots = {
      'source': SourceSlot(1, 'col'),               # the column to set the data type for
      'datatype': CategorySlot(types),    # the data type to assign
      'subtype': CategorySlot(subtypes)   # the data type to assign
    }

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of clean flow output
    {
      'table': 'Promotions',
      'column': 'ApplicableCode',
      'datatype': 'location'
    }
    """
    self.slots['source'].drop_unverified()
    if labels['has_issues']:
      tab_name = current_tab
      col_name = labels['issues_column']
      row_preds = labels['prediction']['rows']

      # only the 'convert' method makes sense, any of the others means confusion
      if labels['prediction']['method'] != 'convert':
        self.is_uncertain = True
    else:
      tab_name = labels['prediction']['table']
      col_name = labels['prediction']['column']
      row_preds = [-1]

    pred_datatype = labels['prediction'].get('datatype', '')
    if pred_datatype == 'unsure':
      self.is_uncertain = True
    elif len(pred_datatype) > 0:
      self.slots['datatype'].assign_one(pred_datatype)

    if any([row_id < 0 for row_id in row_preds]):
      self.slots['source'].add_one(current_tab, col_name)
    else:
      for row in row_preds:
        self.slots['source'].add_one(current_tab, col_name, row)
    return self.is_filled()

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of datatype flow contemplation
    {
      "datatype": "number", "subtype": ["currency"]
    }
    """
    self.slots['datatype'].assign_one(raw_pred['datatype'])
    self.slots['subtype'].assign_multiple(raw_pred['subtype'])
    return self.is_filled()

  def subtype_to_datatype(self, subtype, fill=True):
    # returns the parent datatype for a given subtype, if fill, then also assign the datatype slot
    datatype = ''
    match subtype:
      case ('boolean'|'id'|'status'|'category'): datatype = 'unique'
      case ('quarter'|'month'|'day'|'year'|'week'|'date'): datatype = 'datetime'
      case ('time'|'hour'|'minute'|'second'|'timestamp'): datatype = 'datetime'
      case ('street'|'city'|'zip'|'state'|'country'|'address'): datatype = 'location'
      case ('currency'|'percent'|'whole'|'decimal'): datatype = 'number'
      case ('email'|'phone'|'name'|'url'): datatype = 'text'

    if fill:
      self.slots['datatype'].assign_one(datatype)
      self.slots['subtype'].assign_one(subtype)
    return datatype

class UndoFlow(CleanParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'undo'       # {06F}
    self.entity_slot = 'position'
    self.goal = 'undo the last action taken on the table'

    self.slots = {
      'position': PositionSlot(),                 # the number of steps back to undo
      'confidence': ProbabilitySlot() }           # the confidence that the user wants to undo, rather than a mis-click

class PersistFlow(CleanParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'persist'    # {068}
    self.entity_slot = 'preference'
    self.goal = 'save or update a user preference'

    pref_options = ['goal', 'timing', 'caution', 'special', 'viz', 'metric', 'sig', 'search']
    self.slots = {
      'preference': CategorySlot(pref_options),   # the preference category that is being updated
      'value': ExactSlot(),                       # the new value of the preference to persist
      'detail': DictionarySlot('optional'),       # additional details or settings for the preference
      'operation': FreeTextSlot([], 'optional')   # operations to help determine the preference
    }

class ImputeFlow(CleanParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'impute'    # {06B}
    self.goal = 'fill the missing values within the column based on the available data'
    self.entity_slot = 'target'

    self.slots = {
      'target': TargetSlot(1, 'column'),                    # the column containing missing values
      'source': SourceSlot(1, 'column'),                    # possible column(s) to pull from for imputation
      'default': ExactSlot('required'),                     # the value that represents a blank
      'mask': FreeTextSlot('optional'),                     # the filter to apply to select the relevant rows
      'mapping': DictionarySlot(priority='elective'),       # mapping of source values to target values
      'function': FunctionSlot(priority='elective')         # formula to fill in the new values
    }

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of impute flow output
    {
      "source": [{"tab": "form_responses", "col": "*"}],
      "target": [{"tab": "form_responses", "col": "city"}]
    }
    """
    for source_ent in labels['prediction']['source']:
      self.validate_entity(source_ent, current_tab, 'source')
    for target_ent in labels['prediction']['target']:
      self.validate_entity(target_ent, current_tab)
    return self.slots['target'].filled

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of impute flow contemplation
    {
      "source_columns": ["Company"],
      "blank_value": "none",
      "row_mask": "(table_df['Industry'].isna() | table_df['Industry'] == 'none') & (table_df['Company'].notna())"
    }
    """
    self.slots['default'].add_one(raw_pred['blank_value'])
    self.slots['mask'].add_one(raw_pred['row_mask'])

    # mark the relevant source columns
    for col_name in raw_pred['source_columns']:
      self.slots['source'].add_one(current_tab, col_name, ver=True)
    return self.slots['source'].filled

  def fill_mapping_slot(self, pred_mapping):
    for source_val, target_val in pred_mapping.items():
      if target_val == '<N/A>' or target_val.endswith('...'):
        conflict = {'source': source_val, 'targets': [], 'resolution': ''}
        self.tracker.conflicts.append(conflict)
        continue
      if target_val.startswith('[') and target_val.endswith(']'):
        target_val = target_val[1:-1]
        conflict = {'source': source_val, 'targets': [target_val], 'resolution': 'uncertain'}
        self.tracker.conflicts.append(conflict)
      if '/' in target_val:
        candidates = target_val.split('/')
        conflict = {'source': source_val, 'targets': candidates, 'resolution': 'multiple'}
        self.tracker.conflicts.append(conflict)
        target_val = candidates[0]

      self.slots['mapping'].value[source_val] = target_val

# 10 Transform Flows
class InsertFlow(TransformParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    # InsertFlow performs calculations or pulls information from the user to create net new values, rather than
    # merely combining data from existing values like MergeColFlow. Therefore, the source slots are optional.
    self.flow_type = 'insert'
    self.goal = 'insert a new column or row into the table'
    self.entity_slot = 'target'

    op_prefixes = ['apply', 'filter', 'insert', 'calculate', 'compare']
    options = ['placeholder', 'snapshot', 'connected']
    self.slots = {
      'target': TargetSlot(1, 'column'),                    # the new column to create
      'operation': FreeTextSlot([], 'optional'),            # operations to help determine the type of calculation
      'function': FunctionSlot('optional'),                 # formula to calculate the new value
      'source': SourceSlot(1, 'column', 'optional')         # possible column(s) to reference for the new value
    }

  def is_filled(self):
    for slot in self.slots.values():
      slot.check_if_filled()

    if self.slots['target'].filled:       # target is always required
      if self.slots['function'].filled:   # if a formula is used, we need to reference at least one source column
        return self.slots['source'].filled
    return False

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of insert flow output
    {
      "table": "Customers"
      "target": "CustomerValue",  # <new column to create>
    }
    """
    prediction = labels['prediction']
    col_name = prediction.get('target', prediction.get('column', 'unsure'))
    if col_name != 'unsure':
      self.validate_entity({'tab': prediction['table'], 'col': col_name}, current_tab)
    return self.is_filled()

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of insert flow contemplation
    [
      {"tab": "Concerts", "col": "sound_pattern", "ver": True},
      {"tab": <table_name>, "col": <column_name>, "ver": <boolean>}
    ]
    """
    if self.slots['target'].filled:
      active_tab = self.slots['target'].values[0]['tab']
    else:
      active_tab = current_tab

    for source_pred in raw_pred['source']:
      self.validate_entity(source_pred, active_tab)
    return self.is_filled()

class DeleteFlow(TransformParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    # need to give model a chance to ask for clarification on the target entity
    # for example, "Let's get rid of the weird ones". But what does "weird" mean, that's kinda subjective
    self.flow_type = 'delete'
    self.goal = "remove data from the table"
    self.entity_slot = 'removal'

    options = ['remove', 'clear', 'hide']
    self.slots = {
      'removal': RemovalSlot('cell'),             # the cells, rows, or columns to remove
      'exact': ExactSlot('optional'),             # hold extra details such as whether to target some, all, or beyond
      'category': CategorySlot(options)           # whether to remove, clear, or hide the data
    }
    self.slots['category'].value = 'remove'       # default to remove since we can't handle the others anyway

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of remove flow output stream
    {
      "result": [
        {"tab": "DeliveryStatus", "col": "SendDate", "row": "all"},
        {"tab": "DeliveryStatus", "col": "ReceiveDate", "row": "all"}
    ]}
    """
    prediction = labels['prediction']
    if len(prediction['result']) == 0:
      self.is_uncertain = True
    else:
      for entity in prediction['result']:
        candidate = {
          'tab': entity['tab'] if entity['tab'] != 'unsure' else '',
          'col': entity['col'] if entity['col'] != 'unsure' else '',
          'row': entity['row'] if entity['row'] != 'all' else '' }
        self.validate_entity(candidate, current_tab)

class TransposeFlow(TransformParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'transpose'
    self.goal = 'rotate data around or stack columns into multiple rows'
    options = ['row2col', 'col2row', 'stack']

    self.slots = {
      'source': SourceSlot(1, 'row'),               # the rows or columns to transpose
      'target': TargetSlot(1, 'row', 'optional'),   # where to transpose the data to
      'direction': CategorySlot(options)            # the type of transpose to perform
    }

  def fill_primary_slot(self, active_table, labels):
    candidate_direction = labels.get('direction', 'none').lower()

    for valid_direction in self.slots['category'].options:
      if candidate_direction == valid_direction:
        self.slots['category'].value = valid_direction

class MoveFlow(TransformParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'move'
    self.goal = "cut and paste data from one location to another"

    options = ['table', 'row', 'column', 'cell']
    self.slots = {
      'source': SourceSlot(1, 'cell'),                # the source of the contents to move
      'target': TargetSlot(1, 'column', 'optional'),  # name of the column if renaming
      'element': CategorySlot(options) }              # which type of element is being moved

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of cut and paste flow output
    {
      "moves": [{
        "source": {"tab": "Promotions", "row": "*", "col": "DiscountPercentage"},
        "destination": 6
      }, {
        "source": {"tab": "Promotions", "row": "*", "col": "ApplicableProducts"},
        "destination": 5
      }]
    }
    """
    if len(labels['prediction']['moves']) == 0:
      self.is_uncertain = True

    unique_tabs = set()
    row_selection, col_selection = False, False
    for move in labels['prediction']['moves']:
      source_entity = move['source']
      if source_entity['row'] != '*':
        row_selection = True
      if source_entity['col'] != '*':
        col_selection = True
      unique_tabs.add(source_entity['tab'])

      new_position = move['destination']
      source_entity['rel'] = new_position
      self.validate_entity(source_entity, current_tab)

    if row_selection:
      if col_selection:
        self.slots['element'].assign_one('cell')
      else:
        self.slots['element'].assign_one('row')
    else:
      if len(unique_tabs) == 1:
        self.slots['element'].assign_one('column')
      else:
        self.slots['element'].assign_one('table')
    return self.is_filled()

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of move flow contemplation
    {
      "movement": "column",
      "do_copy": True/False,
      "new_name": ""
    }
    """
    if raw_pred['do_copy']:
      self.fall_back = '005'

    if len(raw_pred['new_name']) > 0 and self.slots['source'].filled:
      source_tab = self.slots['source'].values[0]['tab']
      for col_name in raw_pred['new_name'].split(';'):
        self.slots['target'].add_one(source_tab, col_name)

    movement = raw_pred['movement']
    if movement == 'unsure':
      self.is_uncertain = True
    else:
      if self.slots['element'].filled:
        if self.slots['element'].value != movement:
          self.is_uncertain = True
      else:
        self.slots['element'].assign_one(movement)

    return self.is_filled()

class SplitFlow(TransformParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'split'    # {5CD}
    self.goal = "split a column into multiple columns (ie. text-to-columns)"
    self.symbol_to_name = {',': 'comma', '-': 'dash', '|': 'bar', ' ': 'space', '/': 'slash', '&': 'ampersand',
                      ';': 'semicolon', ':': 'colon', '.': 'period', '_': 'underscore', '@': 'at-sign' }
    self.slots = {
      'source': SourceSlot(1, 'column'),             # the column to split
      'delimiter': DictionarySlot(),                 # the delimiter to split the column by
      'target': TargetSlot(2, 'column', 'optional')  # the name of the new columns to create
    }

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of text2col flow output
    {
      "source": "email",
      "table": "PardotAutomation",
      "delimiter": "@",
      "targets": ["username", "domain"]
    }
    """
    output = labels['prediction']
    source_ent = {'tab': output['table'], 'col': output['source'], 'ver': False}
    self.validate_entity(source_ent, current_tab)

    if len(output['delimiter']) > 0 and output['delimiter'] != 'unsure':
      symbol_name = self.symbol_to_name.get(output['delimiter'], 'other')
      self.slots['delimiter'].add_one(symbol_name, output['delimiter'])
    for target_col in output['targets']:
      self.slots['target'].add_one(output['table'], target_col)
    return self.is_filled()

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of split flow contemplation
    {
      "symbols": { "slash": "/", "comma": "," }
    }
    """
    for symbol_name, symbol_val in raw_pred['symbols'].items():
      self.slots['delimiter'].add_one(symbol_name, symbol_val)
    return self.is_filled()

class MaterializeFlow(TransformParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'materialize'
    self.goal = "save the temporary derived table as a permanent direct table"

    self.slots = {
      'storage': CategorySlot(['disk', 'memory']),    # whether we are saving the table to disk or memory
      'source': SourceSlot(1, 'table', 'elective'),   # name of existing table we exporting
      'target': TargetSlot(1, 'table', 'elective'),   # name of temporary table we are staging
      'settings': DictionarySlot('optional') }        # additional settings or parameters for saving

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of materialize flow output
    {
      "storage": "memory",
      "table": "monthly_prices"
    }
    """
    prediction = labels['prediction']

    if prediction['storage'] == 'disk':
      self.slots['storage'].assign_one('disk')
      self.slots['source'].add_one(prediction['table'], col='*')
    elif prediction['storage'] == 'memory':
      self.slots['storage'].assign_one('memory')
      self.slots['target'].add_one(prediction['table'], col='*')
    else:
      self.is_uncertain = True

    return self.is_filled()

class JoinTabFlow(TransformParentFlow):
  """ Both tables must contain at least three columns
  If the columns on two tables are exactly the same, then we flow fallback to AppendFlow
  """
  def __init__(self, valid):
    super().__init__(valid)
    # once merged, add a new column to distinguish the source of different rows, for example,
    # if we are merging two CRM databases, this helps keep track of which rows came from which DB
    self.flow_type = 'join'
    self.goal = 'combine data together coming from multiple tables'
    self.group_sizes = {'overlap': 0, 'total': 0}
    self.clarify_attempts = 1
    self.join_type = 'outer'   # can be [inner, left, right, outer]

    # batch number ranges from 1 to n, cardset index ranges from 0 to 10
    self.detector = DuplicateDetector()
    self.tracker = IssueTracker()
    self.is_learning = False
    self.options = []  # list of column options to choose from
    self.tag_mapping = {'PER': 'person', 'DATE': 'date', 'LOC': 'location', 'ORG': 'organization', 'ID': 'exact'}

    ner_tags = list(self.tag_mapping.values())
    self.slots = {
      'source': SourceSlot(2, 'table'),         # the two tables that need to be joined
      'target': TargetSlot(1, 'table'),         # name of the new table to create
      'tag': CategorySlot(ner_tags),            # the named entity tag that is being joined
      'prepare': FunctionSlot(),                # pre-processing rules that prepare the data for joining
      'coverage': ProbabilitySlot(threshold=0.5)  # % of rows that have a match after applying preparation function(s)
    }

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of join flow output stream
    {
      'result': {
        "ID": [ {"tab": "activePromos", "col": "PromoID"}, {"tab": "surveyMonkey", "col": "SurveyID"} ],
        "PER": [ {"tab": "activePromos", "col": "RedeemedBy"}, {"tab": "surveyMonkey", "col": "ContactEmail"} ],
        "DATE": [ {"tab": "activePromos", "col": "StartDate"}, {"tab": "activePromos", "col": "EndDate"},  {"tab": "surveyMonkey", "col": "Date"} ],
        "O": [ {"tab": "activePromos", "col": "ApplicableProducts"}, {"tab": "activePromos", "col": "PromoName"} ]
      }
    }
    """
    prediction = labels['prediction']['result']

    if len(prediction) == 0:
      self.is_uncertain = True
      return False
    else:
      for tag_symbol, entity_list in prediction.items():
        tag_name = self.tag_mapping.get(tag_symbol, 'other')
        entity_list = self.exclusive_primary_keys(entity_list, labels)
        if tag_name != 'other':
          for entity in entity_list:
            self.validate_entity(entity, current_tab)
          self.slots['tag'].assign_one(tag_name)

  def exclusive_primary_keys(self, entity_list, labels):
    # Empty the entity list if they are composed exclusively of primary keys
    if len(entity_list) == 2:
      entity1, entity2 = entity_list
      primary_keys = labels['primary_keys']  # dictionary with table names as keys and column name as values

      different_cols = entity1['col'] != entity2['col'] # if they have the same name, then might be legitimate join keys
      first_is_pkey = primary_keys[entity1['tab']] == entity1['col']
      second_is_pkey = primary_keys[entity2['tab']] == entity2['col']
      if different_cols and first_is_pkey and second_is_pkey:
        entity_list = []
    return entity_list

  def fill_slot_values(self, state, raw_pred):
    """ Format of join flow ner_tags filling
    {
      "type": "ID",   // PER, DATE, LOC, ORG, ID
    }
    """
    tag_name = self.tag_mapping.get(raw_pred['type'], 'other')
    if tag_name == 'other':
      if self.clarify_attempts > 0:
        self.actions.add('CLARIFY')
        self.clarify_attempts -= 1
        self.is_uncertain = True
        state.ambiguity.declare('specific', flow='join', slot='tag')
      else:
        self.completed = True
        state.ambiguity.declare('generic', flow='join')
        state.ambiguity.observation = "I'm not sure we can handle joining by these types of columns. Please try again."
    else:
      self.slots['tag'].assign_one(tag_name)
    return self.slots['tag'].check_if_filled()

class AppendFlow(TransformParentFlow):
  # AppendFlow is a special case of JoinFlow where the tables are concatenated vertically
  # and the columns are matched by name, rather than by a key

  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'append'
    self.goal = 'append data from one table to another'

    self.slots = {
      'source': SourceSlot(2, 'table'),         # where the data will pulled from, all but one will be removed
      'removal': RemovalSlot(1, 'table'),       # the tables that will be deleted after appending
      'target': TargetSlot(1, 'table') }        # the name of the new table and columns to create

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of append flow output stream
    {
      'method': 'append',
      'sources': ['AugustEmails', 'SeptemberEmails', 'OctoberEmails']
    }
    """
    prediction = labels['prediction']
    if prediction['method'] == 'append':
      for source_tab in prediction['sources']:
        if source_tab in self.valid_col_dict:
          self.slots['source'].add_one(source_tab, '*')

    elif prediction['method'] == 'join':
      self.fall_back = '05A'
    else:
      self.is_uncertain = True
    return self.is_filled()

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of append flow contemplation which now has access to data preview
    {
      'alignment': True,
      'ordered_tables': ['august_emails', 'september_emails', 'october_emails']
    }
    """
    if raw_pred['alignment']:
      self.slots['source'].drop_unverified()
      for index, tab_name in enumerate(raw_pred['ordered_tables']):
        if tab_name in self.valid_col_dict:
          self.slots['source'].add_one(tab_name, '*', ver=True)
          if index != 0:
            self.slots['removal'].add_one(tab_name, '*')

    return self.is_filled()

class MergeColFlow(TransformParentFlow):
  """ MergeColFlow target column {05C} is always created by combining or comparing 2 or more text columns,
  Notably, it does not perform any calculations such as average or sum, since that is nonsensical for text """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'merge'    # {05C}
    self.goal = 'merge multiple text columns together into a single column'

    valid_methods = ['concat', 'space', 'underscore', 'period', 'comma', 'separator',   # delimiter
                     'contains', 'order', 'size', 'length', 'alpha']                    # ordering
    setting_keys = ['detail', 'reference', 'boolean']

    # after merge, we still might hold onto the divided columns in ShadowTable since they are useful for querying
    # for example, merge columns to create full name, but still allow querying on first and last name
    self.slots = {
      'source': SourceSlot(2, 'column'),          # the columns to merge together
      'target': TargetSlot(1, 'column'),          # name of the new column to create
      'method': CategorySlot(valid_methods),      # if merging by ordering, which style to use
      'candidate': ProposalSlot(valid_methods, 'optional'),     # if merging with a delimiter, which one to use
      'settings': DictionarySlot(setting_keys, 'optional')      # additional parameters for merging columns
    }
    self.slots['settings'].value['boolean'] = True

  def rank_styles(self, current_methods):
    # Rank the available merge methods to display on in the interactive panel
    valid_methods = self.slots['candidate'].options
    remaining_methods = [method for method in valid_methods if method not in current_methods]
    random.shuffle(remaining_methods)
    ranked = current_methods + remaining_methods
    return ranked

  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of merge_column_confidence output
    {
      'source': [['month', 5], ['day', 5], ['year', 5]],
      'target': [['order_date', 4]]
    }
    """
    for source_candidate, confidence_score in raw_pred['source']:
      if confidence_score == 1:
        self.is_uncertain = True
      elif confidence_score == 5:
        verified = source_candidate in self.valid_col_dict[current_tab]
        self.slots['source'].add_one(current_tab, source_candidate, ver=verified)
      else:
        self.slots['source'].add_one(current_tab, source_candidate, ver=False)

    for target_candidate, confidence_score in raw_pred['target']:
      if confidence_score == 1:
        self.is_uncertain = True
      elif confidence_score > 3:
        self.slots['target'].add_one(current_tab, target_candidate, ver=True)
      else:
        self.slots['target'].add_one(current_tab, target_candidate, ver=False)

    self.slots['source'].drop_unverified(conditional=True)
    self.slots['target'].drop_unverified(conditional=True)
    return self.is_filled()

class CallAPIFlow(TransformParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'call'      # {456}
    self.entity_slot = 'target'
    self.goal = 'call an external API to retrieve a new table'

    self.slots = {
      'target': TargetSlot(1, 'table'),           # the name of the new table to create
      'steps': ChecklistSlot(),                   # required steps to call the API
      'settings': DictionarySlot('optional'),     # additional parameters for the API call
      'direction': CategorySlot(['get', 'post'])  # the type of API call to make
    }

# 7 Detect Flows
class BlankFlow(IssueParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'blank'     # {46B}
    self.MetaIssue = Blank
    self.goal = 'identify missing, default, or null values within the table'
    self.issue_types = ['missing', 'default', 'null']
    self.plan_options = ['update', 'delete', 'ignore', 'impute']

    self.slots = {
      'source': SourceSlot(1, 'column'),        # the column that contains the blanks
      'plan': ChecklistSlot() }                 # holds the steps to resolve the blanks

  def fill_slot_values(self, raw_pred, adjusted=False):
    if 'plan' in raw_pred and isinstance(raw_pred['plan'], list):
      # Store the plan steps in the ChecklistSlot
      self.slots['plan'].steps = raw_pred['plan']
      return True
    return False

class ConcernFlow(IssueParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'concern'   # {46C}
    self.MetaIssue = Concern
    self.goal = 'identify outliers, anomalies, or other issues within the table'
    self.issue_types = ['outlier', 'anomaly', 'date_issue', 'loc_issue']
    self.plan_options = ['update', 'delete', 'ignore', 'insert']

    self.slots = {
      'source': SourceSlot(1, 'column'),        # the column that contains the issues
      'plan': ChecklistSlot() }                 # holds the steps to resolve the concerns

class ConnectFlow(DetectParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'connect'   # {46D}
    self.goal = 'open-ended request to connect or combine two sources of data'
    plan_options = ['join', 'append', 'merge', 'call', 'stage', 'dedupe', 'pivot']

    self.slots = {
      'source': SourceSlot(2, 'column'),          # the selected entities to combine
      'plan': ChecklistSlot(plan_options) }        # holds the candidate entities to combine

class TypoFlow(IssueParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'typo'   # {46E}
    self.chosen_term = ''     # the active term that is currently being resolved
    self.all_terms = []       # list of similar terms connected to the active term
    self.MetaIssue = Typo
    self.goal = 'identify typos or misspelled words in the table'
    # replacement means the word or phrase exists but is likely incorrect based on context
    # misspelled means the word is not in the dictionary, and is likely a standard typo
    self.issue_types = ['replacement', 'misspelled']
    self.plan_options = ['update', 'delete', 'ignore', 'validate', 'format']

    # unlike other Resolve flows, this flow checks a list that fills up rather than an integer that counts down
    self.slots = {
      'source': SourceSlot(1, 'column'),        # the column that contains the typos
      'plan': ChecklistSlot() }                 # holds the steps to resolve the typos

  def describe_issues(self, issue_df, frame):
    col_name = frame.issues_entity['col']
    typo_issues = issue_df[(issue_df['column_name'] == col_name) & (issue_df['issue_type'] == 'typo')]
    all_terms = typo_issues['original_value'].tolist()
    num_unique_terms = len(set(all_terms))
    description = self.MetaIssue.type_to_nl(num_unique_terms, 'digit')
    return description

  def parse_predictions(self, raw_output, issue_keys):
    selected_keys, frame_keys = [], []

    if 'unsure' in raw_output:
      return selected_keys, frame_keys
    elif 'all' in raw_output:
      for issue_index, issue_list in issue_keys.items():
        frame_keys.append(issue_index - 1)
        selected_keys.extend(issue_list)
    else:
      for row_id in raw_output.split(','):
        loc = int(row_id.strip())
        frame_keys.append(loc - 1)  # since the frame is 0-indexed
        issue_list = issue_keys.get(loc, [])
        selected_keys.extend(issue_list)
    return selected_keys, frame_keys

class ProblemFlow(IssueParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'problem'  # {46F}
    self.MetaIssue = Problem
    self.goal = 'identify mixed data types or unsupported data structures within the table'
    self.issue_types = ['mixed_type', 'unsupported']
    self.plan_options = ['update', 'delete', 'ignore', 'format', 'datetype']

    self.slots = {
      'source': SourceSlot(1, 'column'),        # the column that contains the issues
      'plan': ChecklistSlot() }                 # holds the steps to resolve the problems

  def describe_issues(self, frame, issue_df):
    """See the parent for general usage, note 'frame' is used here, so it can't be removed from the signature"""
    col_name = frame.issues_entity['col']
    problem_issues = issue_df[(issue_df['column_name'] == col_name) & (issue_df['issue_type'] == 'problem')]
    issue_counts = Counter(problem_issues['subtype'].tolist())

    issue_lines = []
    for issue_hybrid, count in issue_counts.items():
      if '|' in issue_hybrid:
        issue_type, extra_detail = issue_hybrid.split('|')
      else:
        issue_type, extra_detail = issue_hybrid, ''
      issue_lines.append(self.MetaIssue.type_to_nl(issue_type, extra_detail, count, 'digit'))

    description = PromptEngineer.array_to_nl(issue_lines, connector='and')
    return description

class ResolveFlow(DetectParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'resolve'
    self.goal = 'open-ended request to identify issues within the table'
    plan_options = ['datetype', 'update', 'delete', 'ignore', 'dedupe', 'validate', 'impute', 'format', 'pattern']

    self.slots = {
      'source': SourceSlot(1, 'column'),      # where to look for potential issues
      'plan': ProposalSlot(plan_options) }    # holds the candidate entities to fix

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of Resolve flow output streams
    {
      "table": "Customers",
      "columns": ["Email", "PhoneNumber", "Address"],
      "rows": "*"
    }
    """
    pred_tab = labels['prediction']['table']
    pred_cols = labels['prediction']['columns']
    pred_rows = labels['prediction']['rows']

    if pred_tab == '*':
      self.is_uncertain = True
    elif pred_tab == current_tab:
      self.slots['source'].active_tab = pred_tab

    for col_name in pred_cols:
      if col_name == 'unsure':
        self.is_uncertain = True
        continue

      pred_entity = {'tab': pred_tab, 'col': col_name}
      if pred_rows != '*':
        pred_entity['row'] = pred_rows
      self.validate_entity(pred_entity, current_tab)
    return self.is_filled()

class InsightFlow(DetectParentFlow):
  """ Primary goal is to disambiguate the user's request by figuring out a plan to manage the situation. This
  essentially means breaking apart the task into multiple flows, and then placing those child processes on the
  flow stack in the right order. The flow ends when all detected metrics are calculated. Notably, the InsightFlow
  does *not* run any queries itself. By design, multiple metrics will need to be calculated.
  Secondary goal is when the user has made an extremely generic request. This progresses through automated stages
  rather than a typical back-and-forth conversation because the user is just try to see what the agent can do.
  This flow ends when we have reached the 'finish-up' stage, in addition to the normal flow-stack termination.
  """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'insight'
    self.entity_slot = 'source'
    self.goal = 'open-ended request to find insights or observations in the data'
    self.clarify_attempts = 3

    self.slots = {
      'source': SourceSlot(1, 'table'),           # source table(s) that the user wants to analyze
      'analysis': ExactSlot('required'),          # the type of analysis the user wants to perform
      'plan': ChecklistSlot(),                    # the steps within the analysis process
      'preferences': ProposalSlot(['goals', 'timing', 'granularity'], priority='elective')
    }                                             # holds pointers to user preferences that may be relevant

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of Insight flow output streams
    {
      "table": "Customers",
      "columns": ["*"]
    }
    """
    tab_name, columns = labels['prediction']['table'], labels['prediction']['columns']

    if tab_name == 'unsure' or any([col == 'unsure' for col in columns]):
      self.is_uncertain = True
      return False

    if tab_name == '*':
      all_valid_tables = list(self.valid_col_dict.keys())
      for tab_name in all_valid_tables:
        self.slots['source'].add_one(tab=tab_name, col='*')
      self.stage = 'automatic-proposal'
    elif columns[0] == '*':
      self.slots['source'].add_one(tab=tab_name, col='*')
    else:
      for col_name in columns:
        self.slots['source'].add_one(tab=tab_name, col=col_name)
    return self.is_filled()

  def fill_slot_values(self, raw_pred, adjusted=False):
    """ Format of Insight flow convert_to_flow and adjust_plan output stream
    "plan": [
      { "name": "insert", "description": "calculate revenue from price and quantity", "variables": ["revenue"] },
      { "name": "measure", "description": <desc_text>, "metrics": [{"short": "CVR", "long": "Conversion Rate"}] },
      { "name": "pivot", "description": <desc_text>, "variables": ["top_channel", "channel_clicks"] }
    ]
    """
    flow_mapping = {'peek': '39B', 'insert': '005', 'query': '001', 'pivot': '01A',
                    'measure': '002', 'segment': '02D', 'compute': '129', 'plot': '003'}

    if adjusted:  # only keep completed steps since others will be re-proposed
      self.slots['plan'].steps = [step for step in self.slots['plan'].steps if step['checked']]

    for step in raw_pred['plan']:
      dax_code = flow_mapping.get(step['name'], '9DF')

      if dax_code == '002' or dax_code == '02D':
        for metric in step.get('metrics', []):
          metric_step = {'dax': dax_code}
          metric_step['description'] = step['description'].strip()
          metric_step['name'] = step['name']
          metric_step['acronym'] = metric['short']
          metric_step['expanded'] = metric['long']
          metric_step['checked'] = False
          self.slots['plan'].steps.append(metric_step)

      elif dax_code != '9DF':
        # since we start with the predicted step, it already contains the description and variables
        step['dax'] = dax_code
        step['checked'] = False
        self.slots['plan'].steps.append(step)

    return self.is_filled()

"""
Be pro-active about asking if user wants to analyze, review, or check about a result.
For example, after creating a Salesforce column: Any specific Salesforce metrics you're interested in?

User might also want to (new dacts):
  store temporary values somewhere that is easily accessible
  calculate one-off results, like basic arithmetic or a single aggregation
    User: So what 32 * 7 then?
  use the internet, or external data, to supplement what you already have
    Agent: Of course! They're now displayed as '€50.00'.
    User: Thank you. What's the current exchange rate to USD?

During onboarding, we need to ask users about active campaigns and KPIs, will save us headaches down the road

convo_id:  1168
User: Remove all duplicates in the state column (format + merge)
Agent: Sure, I can do that. How do you want to resolve merge conflicts?
User: Umm, I dunno. I just want to see what unique values there are? (describe)
  >> revise into (ignore + chat + describe)
Agent: Ah, I see. I can just tell you directly. The unique values are: CA, NY, TX, and WA.
User: Oh, ok, that was easy, haha (confirm + chat)
"""