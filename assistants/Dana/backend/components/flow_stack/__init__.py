from backend.components.flow_stack.stack import FlowStack, FlowEntry
from backend.components.flow_stack.flows import *

flow_selection = {
  # Clean
  '006': UpdateFlow,     '06E': DatatypeFlow,   '7BD': DedupeFlow,    '5BD': FillFlow,
  '02B': InterpolateFlow, '04C': ReplaceFlow,   '16E': ValidateFlow,  '06B': FormatFlow,
  # Transform
  '005': InsertFlow,     '007': DeleteFlow,     '05A': JoinFlow,      '05B': AppendFlow,
  '06A': ReshapeFlow,    '56C': MergeFlow,      '5CD': SplitFlow,     '28C': DefineFlow,
  # Analyze
  '001': QueryFlow,      '002': LookupFlow,     '01A': PivotFlow,     '02A': DescribeFlow,
  '12A': CompareFlow,    '14C': ExistFlow,      '12C': SegmentFlow,
  # Report
  '003': PlotFlow,       '023': TrendFlow,      '03A': DashboardFlow, '03D': ExportFlow,
  '019': SummarizeFlow,  '03E': StyleFlow,      '038': DesignFlow,
  # Converse
  '009': ExplainFlow,    '000': ChatFlow,       '048': PreferenceFlow, '049': RecommendFlow,
  '08F': UndoFlow,       '09E': ApproveFlow,    '09F': RejectFlow,
  # Plan
  '146': InsightFlow,    '156': PipelineFlow,   '46B': BlankFlow,     '16F': IssueFlow,
  '16D': OutlineFlow,
  # Internal
  '018': RecapFlow,      '129': CalculateFlow,  '149': SearchFlow,    '189': PeekFlow,
  '489': RecallFlow,     '004': RetrieveFlow,
}
