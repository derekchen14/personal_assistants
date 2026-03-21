from backend.components.flow_stack.stack import FlowStack
from backend.components.flow_stack.flows import *

flow_classes: dict[str, type] = {
    # Research
    'browse': BrowseFlow, 'summarize': SummarizeFlow, 'check': CheckFlow,
    'inspect': InspectFlow, 'find': FindFlow, 'compare': CompareFlow,
    'diff': DiffFlow,
    # Draft
    'outline': OutlineFlow, 'refine': RefineFlow, 'cite': CiteFlow,
    'compose': ComposeFlow, 'add': AddFlow, 'create': CreateFlow,
    'brainstorm': BrainstormFlow,
    # Revise
    'rework': ReworkFlow, 'polish': PolishFlow, 'tone': ToneFlow,
    'audit': AuditFlow, 'simplify': SimplifyFlow,
    'remove': RemoveFlow, 'tidy': TidyFlow,
    # Publish
    'release': ReleaseFlow, 'syndicate': SyndicateFlow,
    'schedule': ScheduleFlow, 'preview': PreviewFlow,
    'promote': PromoteFlow, 'cancel': CancelFlow, 'survey': SurveyFlow,
    # Converse
    'explain': ExplainFlow, 'chat': ChatFlow, 'preference': PreferenceFlow,
    'suggest': SuggestFlow, 'undo': UndoFlow, 'endorse': EndorseFlow,
    'dismiss': DismissFlow,
    # Plan
    'blueprint': BlueprintFlow, 'triage': TriageFlow,
    'calendar': CalendarFlow, 'scope': ScopeFlow, 'digest': DigestFlow,
    'remember': RememberFlow,
    # Internal
    'recap': RecapFlow, 'store': StoreFlow, 'recall': RecallFlow,
    'retrieve': RetrieveFlow, 'search': SearchFlow,
    'reference': ReferenceFlow, 'study': StudyFlow,
}
