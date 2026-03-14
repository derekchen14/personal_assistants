from backend.components.flow_stack.stack import FlowStack
from backend.components.flow_stack.flows import *

flow_classes: dict[str, type] = {
    # Explore
    'status': StatusFlow, 'lessons': LessonsFlow, 'browse': BrowseFlow,
    'recommend': RecommendFlow, 'summarize': SummarizeFlow,
    'explain': ExplainFlow, 'inspect': InspectFlow, 'compare': CompareFlow,
    # Gather
    'scope': ScopeFlow, 'teach': TeachFlow, 'intent': IntentFlow,
    'persona': PersonaFlow, 'entity': EntityFlow, 'propose': ProposeFlow,
    # Personalize
    'revise': ReviseFlow, 'remove': RemoveFlow, 'rework': ReworkFlow,
    'approve': ApproveFlow, 'decline': DeclineFlow, 'suggest': SuggestFlow,
    'refine': RefineFlow, 'validate': ValidateFlow,
    # Deliver
    'generate': GenerateFlow, 'package': PackageFlow, 'test': TestFlow,
    'deploy': DeployFlow, 'secure': SecureFlow, 'version': VersionFlow,
    # Converse
    'chat': ChatFlow, 'next': NextFlow, 'feedback': FeedbackFlow,
    'preference': PreferenceFlow, 'style': StyleFlow,
    'endorse': EndorseFlow, 'dismiss': DismissFlow,
    # Plan
    'research': ResearchFlow, 'finalize': FinalizeFlow,
    'onboard': OnboardFlow, 'expand': ExpandFlow, 'redesign': RedesignFlow,
    # Internal
    'recap': RecapFlow, 'recall': RecallFlow, 'retrieve': RetrieveFlow,
    'search': SearchFlow, 'peek': PeekFlow, 'study': StudyFlow,
    'audit': AuditFlow, 'emit': EmitFlow,
}
