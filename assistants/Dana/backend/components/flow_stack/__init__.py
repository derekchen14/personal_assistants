from backend.components.flow_stack.stack import FlowStack
from backend.components.flow_stack.flows import *

flow_classes: dict[str, type] = {
    # Clean
    'update': UpdateFlow, 'datatype': DatatypeFlow, 'dedupe': DedupeFlow,
    'fill': FillFlow, 'interpolate': InterpolateFlow, 'replace': ReplaceFlow,
    'validate': ValidateFlow, 'format': FormatFlow,
    # Transform
    'insert': InsertFlow, 'delete': DeleteFlow, 'join': JoinFlow,
    'append': AppendFlow, 'reshape': ReshapeFlow, 'merge': MergeFlow,
    'split': SplitFlow, 'define': DefineFlow,
    # Analyze
    'query': QueryFlow, 'lookup': LookupFlow, 'pivot': PivotFlow,
    'describe': DescribeFlow, 'compare': CompareFlow, 'exist': ExistFlow,
    'segment': SegmentFlow,
    # Report
    'plot': PlotFlow, 'trend': TrendFlow, 'dashboard': DashboardFlow,
    'export': ExportFlow, 'summarize': SummarizeFlow, 'style': StyleFlow,
    'design': DesignFlow,
    # Converse
    'explain': ExplainFlow, 'chat': ChatFlow, 'preference': PreferenceFlow,
    'recommend': RecommendFlow, 'undo': UndoFlow, 'approve': ApproveFlow,
    'reject': RejectFlow,
    # Plan
    'insight': InsightFlow, 'pipeline': PipelineFlow, 'blank': BlankFlow,
    'issue': IssueFlow, 'outline': OutlineFlow,
    # Internal
    'recap': RecapFlow, 'calculate': CalculateFlow, 'search': SearchFlow,
    'peek': PeekFlow, 'recall': RecallFlow, 'retrieve': RetrieveFlow,
}
