from backend.components.flow_stack.stack import FlowStack
from backend.components.flow_stack.flows import *

flow_classes: dict[str, type] = {
    # Research
    'browse': BrowseFlow, 'view': ViewFlow, 'check': CheckFlow,
    'inspect': InspectFlow, 'find': FindFlow, 'compare': CompareFlow,
    # Draft
    'outline': OutlineFlow, 'refine': RefineFlow, 'expand': ExpandFlow,
    'compose': ComposeFlow, 'add': AddFlow, 'create': CreateFlow,
    'brainstorm': BrainstormFlow,
    # Revise
    'rework': ReworkFlow, 'polish': PolishFlow, 'tone': ToneFlow,
    'audit': AuditFlow, 'format': FormatFlow,
    'remove': RemoveFlow, 'diff': DiffFlow, 'tidy': TidyFlow,
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
