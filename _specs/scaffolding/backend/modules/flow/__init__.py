from backend.modules.flow.ext_flows import *
from backend.modules.flow.int_flows import *

flow_selection = {
  # Analyze Flows
  '001': QueryFlow,     '01A': PivotFlow,    '002': MeasureFlow,   '02D': SegmentFlow, '014': DescribeFlow,
  '14C': ExistFlow,     '248': InformFlow,   '268': DefineFlow,
  # Visualize Flows
  '003': PlotFlow,      '023': TrendFlow,    '038': ExplainFlow,   '23D': ReportFlow,  '38A': SaveFlow,
  '136': DesignFlow,    '13A': StyleFlow,
  # Clean Flows
  '006': UpdateFlow,    '36D': ValidateFlow, '36F': FormatFlow,    '0BD': PatternFlow, '068': PersistFlow,
  '06B': ImputeFlow,    '06E': DataTypeFlow, '06F': UndoFlow,      '7BD': DedupeFlow,
  # Transform Flows
  '005': InsertFlow,    '007': DeleteFlow,   '056': TransposeFlow, '057': MoveFlow,    '5CD': SplitFlow,
  '05A': JoinTabFlow,   '05B': AppendFlow,   '05C': MergeColFlow,  '456': CallAPIFlow, '58A': MaterializeFlow,
  # Detect Flows
  '46B': BlankFlow,     '46C': ConcernFlow,  '46D': ConnectFlow,   '46E': TypoFlow,    '46F': ProblemFlow,
  '468': ResolveFlow,   '146': InsightFlow,
  # Internal Flows
  '089': ThinkFlow,     '39B': PeekFlow,     '129': ComputeFlow,   '149': SearchFlow,  '19A': StageFlow,
  '489': ConsiderFlow,  '9DF': UncertainFlow
}