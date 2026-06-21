from backend.components.flow_stack.stack import FlowStack
from backend.components.flow_stack.flows import *

flow_classes: dict[str, type] = {
    # Research
    'find': FindFlow, 'browse': BrowseFlow, 'summarize': SummarizeFlow,
    'compare': CompareFlow,
    # Draft
    'brainstorm': BrainstormFlow, 'outline': OutlineFlow, 'refine': RefineFlow,
    'cite': CiteFlow,
    # Revise
    'rework': ReworkFlow, 'polish': PolishFlow, 'audit': AuditFlow,
    'propose': ProposeFlow,
    # Publish
    'release': ReleaseFlow, 'schedule': ScheduleFlow, 'promote': PromoteFlow,
    # Converse
    'chat': ChatFlow,
}
