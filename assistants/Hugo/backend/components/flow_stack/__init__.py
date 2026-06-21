from backend.components.flow_stack.stack import FlowStack
from backend.components.flow_stack.flows import *

flow_classes: dict[str, type] = {
    # Research
    'find': FindFlow, 'browse': BrowseFlow, 'summarize': SummarizeFlow,
    'compare': CompareFlow,
    # Draft
    'brainstorm': BrainstormFlow, 'outline': OutlineFlow, 'compose': ComposeFlow,
    'refine': RefineFlow,
    # Revise
    'rework': ReworkFlow, 'write': WriteFlow, 'audit': AuditFlow,
    'propose': ProposeFlow,
    # Publish
    'release': ReleaseFlow, 'schedule': ScheduleFlow, 'cite': CiteFlow,
    # Converse
    'chat': ChatFlow,
}
