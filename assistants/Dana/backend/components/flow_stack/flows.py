from backend.components.flow_stack.slots import *
from backend.components.flow_stack.parents import *


# ── Clean (8 flows) ─────────────────────────────────────────────────────────

class UpdateFlow(CleanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'update'
    self.dax = '{006}'
    self.goal = 'modify cell values, column types, or column names in place'
    self.slots = {
      'source': SourceSlot(1),
      'value': FreeTextSlot(),
    }
    self.tools = ['modify_column', 'modify_row', 'modify_cell', 'modify_table', 'execute_python']


class DatatypeFlow(CleanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'datatype'
    self.dax = '{06E}'
    self.goal = 'validate and cast column data types'
    self.slots = {
      'source': SourceSlot(1),
      'type': CategorySlot(['blank', 'unique', 'datetime', 'location', 'number', 'text'], priority='required'),
    }
    self.tools = ['cast_column', 'validate_column']


class DedupeFlow(CleanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'dedupe'
    self.dax = '{7BD}'
    self.goal = 'remove duplicate rows based on key columns'
    self.slots = {
      'source': SourceSlot(1),
    }
    self.tools = ['dedupe_single_col', 'dedupe_columns', 'execute_python']


class FillFlow(CleanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'fill'
    self.dax = '{5BD}'
    self.goal = 'flash fill missing values using row-wise patterns'
    self.slots = {
      'source': SourceSlot(1),
      'strategy': CategorySlot(['forward', 'backward', 'mean', 'median', 'mode', 'zero', 'constant'], priority='optional'),
    }
    self.tools = ['flash_fill', 'execute_python']


class InterpolateFlow(CleanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'interpolate'
    self.dax = '{02B}'
    self.goal = 'estimate missing values using surrounding columns'
    self.slots = {
      'source': SourceSlot(1),
      'method': CategorySlot(['linear', 'spline', 'nearest', 'polynomial', 'pad'], priority='optional'),
    }
    self.tools = ['run_interpolation', 'execute_python']


class ReplaceFlow(CleanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'replace'
    self.dax = '{04C}'
    self.goal = 'find and replace values across a column'
    self.slots = {
      'source': SourceSlot(1),
      'find': ExactSlot(),
      'replacement': ExactSlot(),
    }
    self.tools = ['replace_values', 'cut_n_paste', 'execute_python']


class ValidateFlow(CleanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'validate'
    self.dax = '{16E}'
    self.goal = 'check that values belong to a valid set of options'
    self.slots = {
      'source': SourceSlot(1),
      'rules': GroupSlot(1, priority='optional'),
    }
    self.tools = ['validate_column']

class FormatFlow(CleanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'format'
    self.dax = '{06B}'
    self.goal = 'normalize values into the correct form'
    format_options = ['phone', 'email', 'date', 'currency', 'percentage', 'address', 'zip', 'custom']
    self.slots = {
      'source': SourceSlot(1),
      'pattern': ExactSlot(priority='optional'),  # describes the format type, such as MM/DD/YYYY or YYYY-MM-DD for dates
      'format_type': CategorySlot(format_options, priority='required'),
    }
    self.tools = ['format_column', 'format_custom']

# ── Transform (8 flows) ─────────────────────────────────────────────────────

class InsertFlow(TransformParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'insert'
    self.dax = '{005}'
    self.goal = 'add a new row or column to the table'
    self.slots = {
      'source': SourceSlot(1),
      'column': TargetSlot(1, 'column', priority='elective'),
      'row': TargetSlot(1, 'row', priority='elective'),
      'position': PositionSlot(priority='optional'),
    }
    self.tools = ['insert_rows', 'insert_columns', 'load_dataset']


class DeleteFlow(TransformParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'delete'
    self.dax = '{007}'
    self.goal = 'remove rows or columns from the table'
    self.slots = {
      'source': SourceSlot(1),
      'target': RemovalSlot('columns'),
    }
    self.tools = ['delete_rows', 'delete_columns']


class JoinFlow(TransformParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'join'
    self.dax = '{05A}'
    self.goal = 'combine two tables on a shared key column'
    self.slots = {
      'left': SourceSlot(1, 'table'),
      'right': SourceSlot(1, 'table'),
      'key': SourceSlot(1, 'column'),
      'how': CategorySlot(['inner', 'left', 'right', 'outer', 'cross'], priority='optional'),
    }
    self.tools = ['merge_tables', 'merge_by_key']


class AppendFlow(TransformParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'append'
    self.dax = '{05B}'
    self.goal = 'stack rows from one table onto another vertically'
    self.slots = {
      'source': SourceSlot(1, 'table'),
      'target': SourceSlot(1, 'table'),
    }
    self.tools = ['append_tables']


class ReshapeFlow(TransformParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'reshape'
    self.dax = '{06A}'
    self.goal = 'restructure the table layout (pivot, unpivot, transpose)'
    self.slots = {
      'source': SourceSlot(1),
      'method': CategorySlot(['pivot', 'unpivot', 'transpose'], priority='required'),
    }
    self.tools = ['pivot_tables', 'modify_table', 'cut_n_paste']


class MergeFlow(TransformParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'merge'
    self.dax = '{56C}'
    self.goal = 'combine two or more columns into one'
    self.slots = {
      'source': SourceSlot(2),
      'name': TargetSlot(1, 'column'),
    }
    self.tools = ['merge_columns']


class SplitFlow(TransformParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'split'
    self.dax = '{5CD}'
    self.goal = 'split one column into multiple new columns'
    self.slots = {
      'source': SourceSlot(1),
      'delimiter': ExactSlot(priority='optional'),
    }
    self.tools = ['split_column']


class DefineFlow(TransformParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'define'
    self.dax = '{28C}'
    self.goal = 'create a named, reusable metric formula'
    self.slots = {
      'name': TargetSlot(1, 'column'),
      'formula': FunctionSlot(),
      'source': SourceSlot(1, priority='optional'),
    }
    self.tools = ['define_metric', 'apply_formula']


# ── Analyze (7 flows) ───────────────────────────────────────────────────────

class QueryFlow(AnalyzeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'query'
    self.dax = '{001}'
    self.goal = 'run a SQL-like query against the data'
    self.slots = {
      'source': SourceSlot(1),
      'query': FreeTextSlot(priority='optional'),
    }
    self.tools = ['execute_sql']


class LookupFlow(AnalyzeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'lookup'
    self.dax = '{002}'
    self.goal = 'find the definition of a metric or term in the semantic layer'
    self.slots = {
      'term': FreeTextSlot(),
      'context': FreeTextSlot(priority='optional'),
    }
    self.tools = ['lookup_metric']


class PivotFlow(AnalyzeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'pivot'
    self.dax = '{01A}'
    self.goal = 'cross-tabulate data by two dimensions'
    self.slots = {
      'source': SourceSlot(2),
    }
    self.tools = ['execute_sql', 'pivot_tables']


class DescribeFlow(AnalyzeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'describe'
    self.dax = '{02A}'
    self.goal = 'profile a dataset or column'
    self.slots = {
      'source': SourceSlot(1),
    }
    self.tools = ['execute_sql', 'describe_stats']


class CompareFlow(AnalyzeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'compare'
    self.dax = '{12A}'
    self.goal = 'compare two variables, groups, or time periods side by side'
    self.slots = {
      'source': SourceSlot(2),
      'method': CategorySlot(['correlation', 'difference', 'ratio', 'distribution'], priority='optional'),
    }
    self.tools = ['compare_metrics', 'compute_correlation']


class ExistFlow(AnalyzeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'exist'
    self.dax = '{14C}'
    self.goal = 'check whether specific data exists in the workspace'
    self.slots = {
      'query': FreeTextSlot(),
      'source': SourceSlot(1, priority='optional'),
    }
    self.tools = ['execute_sql', 'describe_stats', 'semantic_layer', 'list_datasets']


class SegmentFlow(AnalyzeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'segment'
    self.dax = '{12C}'
    self.goal = 'break down a single metric by one or more dimension, motivated by drilldown analysis'
    self.slots = {
      'source': SourceSlot(2),
      'dimension': SourceSlot(1, 'column', priority='optional'),
    }
    self.tools = ['execute_sql', 'root_cause_analysis', 'dimension_breakdown']


# ── Report (7 flows) ────────────────────────────────────────────────────────

class PlotFlow(ReportParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'plot'
    self.dax = '{003}'
    self.goal = 'create a chart from data'
    self.slots = {
      'source': SourceSlot(1),
      'x': SourceSlot(1, 'column', priority='optional'),
      'y': SourceSlot(1, 'column', priority='optional'),
      'chart_type': CategorySlot(['bar', 'line', 'pie', 'scatter', 'histogram', 'heatmap', 'box'], priority='optional'),
    }
    self.tools = ['render_chart', 'execute_sql', 'execute_python']


class TrendFlow(ReportParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'trend'
    self.dax = '{023}'
    self.goal = 'visualize values across time'
    self.slots = {
      'source': SourceSlot(2),
      'period': RangeSlot([], priority='optional'),
    }
    self.tools = ['render_chart', 'compare_metrics', 'execute_python']


class DashboardFlow(ReportParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'dashboard'
    self.dax = '{03A}'
    self.goal = 'compose a multi-panel dashboard'
    self.slots = {
      'source': SourceSlot(1),
      'charts': GroupSlot(1, priority='required'),
    }
    self.tools = ['compose_dashboard', 'render_chart', 'modify_chart']


class ExportFlow(ReportParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'export'
    self.dax = '{03D}'
    self.goal = 'export a dataset to a downloadable file'
    self.slots = {
      'source': SourceSlot(1),
      'format': CategorySlot(['csv', 'excel', 'json', 'parquet'], priority='optional'),
    }
    self.tools = ['export_dataset', 'save_dataset']


class SummarizeFlow(ReportParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'summarize'
    self.dax = '{019}'
    self.goal = 'summarize a chart or table in plain language'
    self.slots = {
      'source': SourceSlot(1),
      'chart': ChartSlot(priority='elective'),
      'data': FreeTextSlot(priority='elective'),
    }
    self.tools = ['summarize_content', 'semantic_layer', 'search_reference']


class StyleFlow(ReportParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'style'
    self.dax = '{03E}'
    self.goal = 'apply conditional formatting to a table display'
    self.slots = {
      'source': SourceSlot(1),
      'condition': FreeTextSlot(),
      'format': FreeTextSlot(priority='optional'),
    }
    self.tools = ['apply_style']


class DesignFlow(ReportParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'design'
    self.dax = '{038}'
    self.goal = "adjust an existing chart's visual properties"
    self.slots = {
      'source': SourceSlot(1),
      'chart': ChartSlot(),
      'element': FreeTextSlot(priority='optional'),
    }
    self.tools = ['modify_chart', 'style_chart']


# ── Converse (7 flows) ──────────────────────────────────────────────────────

class ExplainFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'explain'
    self.dax = '{009}'
    self.goal = 'explain what Dana did or plans to do'
    self.slots = {
      'turn_id': PositionSlot(priority='elective'),
      'source': SourceSlot(1, priority='elective'),
      'chart': ChartSlot(priority='elective'),
    }
    self.tools = ['explain_content']


class ChatFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'chat'
    self.dax = '{000}'
    self.goal = 'open-ended conversation'
    self.slots = {}
    self.tools = []


class PreferenceFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'preference'
    self.dax = '{048}'
    self.goal = 'set a persistent analysis preference'
    self.slots = {
      'setting': DictionarySlot(['key', 'value']),
    }
    self.tools = []


class RecommendFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recommend'
    self.dax = '{049}'
    self.goal = 'suggest a next step based on current data context'
    self.slots = {
      'suggestions': ProposalSlot(priority='optional'),
    }
    self.tools = ['execute_sql', 'describe_stats']


class UndoFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'undo'
    self.dax = '{08F}'
    self.goal = 'reverse the most recent data action'
    self.slots = {
      'turn': LevelSlot(priority='elective', threshold=1),
      'action': FreeTextSlot(priority='elective'),
    }
    self.tools = ['rollback_dataset']


class ApproveFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'approve'
    self.dax = '{09E}'
    self.goal = "accept Dana's proactive suggestion"
    self.slots = {
      'action': FreeTextSlot(),
    }
    self.tools = []


class RejectFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'reject'
    self.dax = '{09F}'
    self.goal = "decline Dana's proactive suggestion"
    self.slots = {
      'action': FreeTextSlot(),
      'reason': FreeTextSlot(priority='optional'),
    }
    self.tools = []


# ── Plan (5 flows) ──────────────────────────────────────────────────────────

class InsightFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'insight'
    self.dax = '{146}'
    self.goal = 'plan a multi-step analysis to answer a complex question'
    self.slots = {
      'question': FreeTextSlot(),
      'source': SourceSlot(1),
      'confidence': ProbabilitySlot(priority='optional'),
    }
    self.tools = []


class PipelineFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'pipeline'
    self.dax = '{156}'
    self.goal = 'plan a reusable ETL sequence'
    self.slots = {
      'steps': ChecklistSlot(),
      'source': SourceSlot(1),
    }
    self.tools = ['load_dataset']


class BlankFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'blank'
    self.dax = '{46B}'
    self.goal = 'diagnose null or empty cells across the dataset'
    self.slots = {
      'source': SourceSlot(1),
      'strategy': CategorySlot(['fill', 'interpolate', 'drop', 'flag'], priority='optional'),
    }
    self.tools = ['describe_stats', 'validate_column']


class IssueFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'issue'
    self.dax = '{16F}'
    self.goal = 'diagnose data quality issues'
    self.slots = {
      'source': SourceSlot(1),
      'type': CategorySlot(['outlier', 'missing', 'format', 'duplicate', 'inconsistent', 'type_mismatch'], priority='optional'),
      'severity': ScoreSlot(priority='optional'),
    }
    self.tools = ['describe_stats', 'validate_column']


class OutlineFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'outline'
    self.dax = '{16D}'
    self.goal = 'execute a multi-step plan from instructions'
    self.slots = {
      'instructions': FreeTextSlot(),
      'source': SourceSlot(1, priority='optional'),
    }
    self.tools = ['load_dataset']


# ── Internal (6 flows) ──────────────────────────────────────────────────────

class RecapFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recap'
    self.dax = '{018}'
    self.goal = 'read back a fact from the session scratchpad'
    self.slots = {
      'key': FreeTextSlot(priority='optional'),
    }
    self.tools = []


class CalculateFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'calculate'
    self.dax = '{129}'
    self.goal = 'perform quick arithmetic or comparisons internally'
    self.slots = {
      'expression': FunctionSlot(),
    }
    self.tools = ['execute_python']


class SearchFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'search'
    self.dax = '{149}'
    self.goal = 'look up vetted FAQs and curated reference content'
    self.slots = {
      'query': FreeTextSlot(),
    }
    self.tools = ['search_reference']


class PeekFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'peek'
    self.dax = '{189}'
    self.goal = 'quick internal glance at data state'
    self.slots = {
      'source': SourceSlot(1, priority='optional'),
    }
    self.tools = ['describe_stats', 'heads_or_tails']


class RecallFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recall'
    self.dax = '{489}'
    self.goal = 'look up persistent user preferences'
    self.slots = {
      'key': FreeTextSlot(priority='optional'),
      'scope': CategorySlot(['session', 'user', 'global'], priority='optional'),
    }
    self.tools = []


class RetrieveFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'retrieve'
    self.dax = '{004}'
    self.goal = 'fetch general business context from Memory Manager'
    self.slots = {
      'topic': FreeTextSlot(),
      'context': FreeTextSlot(priority='optional'),
    }
    self.tools = []
