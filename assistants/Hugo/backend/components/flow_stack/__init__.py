from backend.components.flow_stack.stack import FlowStack, FlowEntry
from backend.components.flow_stack.flows import *

flow_selection = {
  # Research
  '012': BrowseFlow,     '1AD': ViewFlow,       '0AD': CheckFlow,     '1BD': InspectFlow,
  '1AB': FindFlow,       '18A': CompareFlow,
  # Draft
  '02A': OutlineFlow,     '02B': RefineFlow,   '03A': ExpandFlow,    '03B': WriteFlow,
  '05B': AddFlow,        '05A': CreateFlow,     '29A': BrainstormFlow,
  # Revise
  '03D': ReworkFlow,     '3BD': PolishFlow,     '38A': ToneFlow,      '13A': AuditFlow,
  '3AD': FormatFlow,     '0AF': AmendFlow,      '0BD': DiffFlow,      '3AB': TidyFlow,
  # Publish
  '04A': ReleaseFlow,    '04C': SyndicateFlow,  '4AC': ScheduleFlow,  '4AD': PreviewFlow,
  '4AE': PromoteFlow,    '04F': CancelFlow,     '01C': SurveyFlow,
  # Converse
  '009': ExplainFlow,    '000': ChatFlow,       '08A': PreferenceFlow, '29B': SuggestFlow,
  '08F': UndoFlow,       '09E': EndorseFlow,    '09F': DismissFlow,
  # Plan
  '25A': BlueprintFlow,  '23A': TriageFlow,     '24A': CalendarFlow,  '12A': ScopeFlow,
  '25B': DigestFlow,     '19B': RememberFlow,
  # Internal
  '018': RecapFlow,      '058': StoreFlow,      '289': RecallFlow,    '049': RetrieveFlow,
  '189': SearchFlow,     '139': ReferenceFlow,  '1AC': StudyFlow,
}
