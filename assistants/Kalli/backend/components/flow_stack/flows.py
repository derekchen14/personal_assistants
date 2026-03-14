from backend.components.flow_stack.slots import *
from backend.components.flow_stack.parents import *


# ── Explore (8 flows) ──────────────────────────────────────────────────────

class StatusFlow(ExploreParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'status'
    self.dax = '{01A}'
    self.goal = 'view current state of the assistant being built'
    self.slots = {
      'source': SourceSlot(1, priority='optional'),
    }
    self.tools = ['read_config', 'check_progress']


class LessonsFlow(ExploreParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'lessons'
    self.dax = '{01B}'
    self.goal = 'browse stored requirements and patterns'
    self.slots = {
      'topic': FreeTextSlot(priority='optional'),
      'count': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['search_lessons', 'list_patterns']


class BrowseFlow(ExploreParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'browse'
    self.dax = '{001}'
    self.goal = 'look up a specific spec file or section'
    self.slots = {
      'source': SourceSlot(1),
      'query': FreeTextSlot(priority='optional'),
    }
    self.tools = ['read_spec', 'search_specs']


class RecommendFlow(ExploreParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recommend'
    self.dax = '{18C}'
    self.goal = "find specs relevant to the user's target domain"
    self.slots = {
      'context': FreeTextSlot(),
    }
    self.tools = ['search_specs', 'suggest_specs']


class SummarizeFlow(ExploreParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'summarize'
    self.dax = '{19A}'
    self.goal = 'summarize overall build progress'
    self.slots = {}
    self.tools = ['read_config', 'check_progress']


class ExplainFlow(ExploreParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'explain'
    self.dax = '{19C}'
    self.goal = 'explain an architecture concept or capability'
    self.slots = {
      'topic': FreeTextSlot(),
    }
    self.tools = ['read_spec', 'search_specs']


class InspectFlow(ExploreParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'inspect'
    self.dax = '{1AD}'
    self.goal = 'inspect a draft assistant section in detail'
    self.slots = {
      'source': SourceSlot(1),
      'detail': CategorySlot(['slots', 'tools', 'dax', 'policy', 'edges', 'full'], priority='optional'),
    }
    self.tools = ['read_config', 'read_spec']


class CompareFlow(ExploreParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'compare'
    self.dax = '{1CD}'
    self.goal = 'compare draft assistant section against spec rules'
    self.slots = {
      'source': SourceSlot(1),
      'reference': FreeTextSlot(priority='optional'),
    }
    self.tools = ['read_config', 'read_spec', 'validate_section']


# ── Gather (6 flows) ──────────────────────────────────────────────────────

class ScopeFlow(GatherParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'scope'
    self.dax = '{002}'
    self.goal = 'define assistant scope: name, task, boundaries'
    self.slots = {
      'name': FreeTextSlot(),
      'task': FreeTextSlot(),
      'boundaries': FreeTextSlot(priority='optional'),
    }
    self.tools = ['save_scope']


class TeachFlow(GatherParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'teach'
    self.dax = '{02B}'
    self.goal = 'share a learning, pattern, or requirement for Kalli to remember'
    self.slots = {
      'pattern': FreeTextSlot(),
      'category': CategorySlot(['architecture', 'flow', 'slot', 'entity', 'policy', 'prompt', 'test'], priority='optional'),
      'context': FreeTextSlot(priority='optional'),
    }
    self.tools = ['save_lesson']


class IntentFlow(GatherParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'intent'
    self.dax = '{005}'
    self.goal = 'define a domain intent for the assistant'
    self.slots = {
      'name': FreeTextSlot(),
      'description': FreeTextSlot(),
    }
    self.tools = ['save_intent']


class PersonaFlow(GatherParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'persona'
    self.dax = '{28A}'
    self.goal = 'define persona preferences: name, tone, style'
    self.slots = {
      'name': FreeTextSlot(),
      'tone': CategorySlot(['formal', 'casual', 'technical', 'friendly', 'neutral'], priority='elective'),
      'style': CategorySlot(['concise', 'detailed', 'conversational', 'structured'], priority='elective'),
    }
    self.tools = ['save_persona']


class EntityFlow(GatherParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'entity'
    self.dax = '{2AC}'
    self.goal = 'define key entities grounded in domain concepts'
    self.slots = {
      'entities': GroupSlot(1),
    }
    self.tools = ['save_entities']


class ProposeFlow(GatherParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'propose'
    self.dax = '{003}'
    self.goal = 'propose core dacts for the domain grammar'
    self.slots = {}
    self.tools = ['generate_dacts', 'search_specs']


# ── Personalize (8 flows) ────────────────────────────────────────────────

class ReviseFlow(PersonalizeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'revise'
    self.dax = '{006}'
    self.goal = 'update a previously defined assistant section'
    self.slots = {
      'source': SourceSlot(1),
      'value': FreeTextSlot(),
    }
    self.tools = ['update_config']


class RemoveFlow(PersonalizeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'remove'
    self.dax = '{007}'
    self.goal = 'remove an assistant section or entry'
    self.slots = {
      'source': SourceSlot(1),
    }
    self.tools = ['delete_config']


class ReworkFlow(PersonalizeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'rework'
    self.dax = '{03D}'
    self.goal = 'revise an existing flow design'
    self.slots = {
      'flow': ExactSlot(),
      'change': FreeTextSlot(),
    }
    self.tools = ['update_flow', 'read_config']


class ApproveFlow(PersonalizeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'approve'
    self.dax = '{0AE}'
    self.goal = 'approve a proposed flow or dact'
    self.slots = {
      'flow': ExactSlot(),
    }
    self.tools = ['approve_proposal']


class DeclineFlow(PersonalizeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'decline'
    self.dax = '{0AF}'
    self.goal = 'reject a proposed flow or dact with reason'
    self.slots = {
      'flow': ExactSlot(),
      'reason': FreeTextSlot(priority='optional'),
    }
    self.tools = ['reject_proposal']


class SuggestFlow(PersonalizeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'suggest'
    self.dax = '{39A}'
    self.goal = 'suggest changes to existing flows'
    self.slots = {
      'filter': CategorySlot(['slots', 'tools', 'edges', 'dax', 'all'], priority='optional'),
      'scope': FreeTextSlot(priority='optional'),
    }
    self.tools = ['analyze_flows', 'search_specs']


class RefineFlow(PersonalizeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'refine'
    self.dax = '{3AD}'
    self.goal = "refine a flow's slot signature or output type"
    self.slots = {
      'flow': ExactSlot(),
      'change': FreeTextSlot(priority='optional'),
    }
    self.tools = ['update_flow', 'read_config']


class ValidateFlow(PersonalizeParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'validate'
    self.dax = '{3AC}'
    self.goal = 'validate current flow catalog against spec rules'
    self.slots = {}
    self.tools = ['validate_catalog', 'read_spec']


# ── Deliver (6 flows) ────────────────────────────────────────────────────

class GenerateFlow(DeliverParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'generate'
    self.dax = '{004}'
    self.goal = 'generate domain config files (ontology, yaml, or all)'
    self.slots = {
      'format': CategorySlot(['ontology', 'yaml', 'all'], priority='optional'),
    }
    self.tools = ['generate_config']


class PackageFlow(DeliverParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'package'
    self.dax = '{48A}'
    self.goal = 'package the full domain for deployment'
    self.slots = {
      'target': FreeTextSlot(priority='optional'),
    }
    self.tools = ['package_domain']


class TestFlow(DeliverParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'test'
    self.dax = '{4BC}'
    self.goal = 'run validation tests against the built assistant'
    self.slots = {
      'scope': CategorySlot(['flows', 'slots', 'policies', 'coverage', 'full'], priority='optional'),
    }
    self.tools = ['run_tests', 'check_coverage']


class DeployFlow(DeliverParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'deploy'
    self.dax = '{4AE}'
    self.goal = 'deploy the assistant to a target environment'
    self.slots = {
      'environment': CategorySlot(['staging', 'production'], priority='required'),
    }
    self.tools = ['deploy_assistant', 'generate_report']


class SecureFlow(DeliverParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'secure'
    self.dax = '{89A}'
    self.goal = 'configure authentication, API keys, and access permissions'
    self.slots = {
      'setting': DictionarySlot(['key', 'value']),
    }
    self.tools = ['update_auth']


class VersionFlow(DeliverParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'version'
    self.dax = '{4AD}'
    self.goal = 'tag a release version with changelog'
    self.slots = {
      'tag': ExactSlot(),
      'notes': FreeTextSlot(priority='optional'),
    }
    self.tools = ['tag_version']


# ── Converse (7 flows) ──────────────────────────────────────────────────

class ChatFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'chat'
    self.dax = '{000}'
    self.goal = 'open-ended conversation about building assistants'
    self.slots = {}
    self.tools = []


class NextFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'next'
    self.dax = '{019}'
    self.goal = 'ask Kalli what to do next'
    self.slots = {}
    self.tools = ['check_progress']


class FeedbackFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'feedback'
    self.dax = '{029}'
    self.goal = "give feedback on the build process or Kalli's behavior"
    self.slots = {}
    self.tools = []


class PreferenceFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'preference'
    self.dax = '{08A}'
    self.goal = 'set a user preference for the build process'
    self.slots = {
      'setting': DictionarySlot(['key', 'value']),
    }
    self.tools = []


class StyleFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'style'
    self.dax = '{08B}'
    self.goal = 'tell Kalli about preferred working style'
    self.slots = {
      'preference': FreeTextSlot(),
    }
    self.tools = []


class EndorseFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'endorse'
    self.dax = '{09E}'
    self.goal = "approve Kalli's unsolicited suggestion"
    self.slots = {
      'action': ExactSlot(),
    }
    self.tools = []


class DismissFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'dismiss'
    self.dax = '{09F}'
    self.goal = "dismiss Kalli's unsolicited suggestion"
    self.slots = {}
    self.tools = []


# ── Plan (5 flows) ──────────────────────────────────────────────────────

class ResearchFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'research'
    self.dax = '{13C}'
    self.goal = 'plan to research specs before design decisions'
    self.slots = {
      'topic': FreeTextSlot(),
      'depth': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['search_specs', 'read_spec']


class FinalizeFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'finalize'
    self.dax = '{24A}'
    self.goal = 'plan the final export sequence'
    self.slots = {}
    self.tools = []


class OnboardFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'onboard'
    self.dax = '{25A}'
    self.goal = 'full onboarding plan: scope, intents, entities, persona'
    self.slots = {
      'context': FreeTextSlot(priority='optional'),
    }
    self.tools = []


class ExpandFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'expand'
    self.dax = '{35A}'
    self.goal = 'plan to add a batch of new flows at once'
    self.slots = {
      'filter': CategorySlot(['explore', 'gather', 'personalize', 'deliver', 'converse', 'plan', 'internal'], priority='optional'),
      'count': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = []


class RedesignFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'redesign'
    self.dax = '{36A}'
    self.goal = 'plan to redesign a section of the assistant'
    self.slots = {
      'source': SourceSlot(1),
      'goal': FreeTextSlot(priority='optional'),
    }
    self.tools = ['read_config', 'read_spec']


# ── Internal (8 flows) ──────────────────────────────────────────────────

class RecapFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recap'
    self.dax = '{018}'
    self.goal = 'pull a snippet from current conversation (scratchpad L1)'
    self.slots = {
      'key': ExactSlot(priority='optional'),
      'turns': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = []


class RecallFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recall'
    self.dax = '{289}'
    self.goal = 'retrieve stored user preferences (L2)'
    self.slots = {
      'key': ExactSlot(priority='optional'),
    }
    self.tools = []


class RetrieveFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'retrieve'
    self.dax = '{19B}'
    self.goal = 'retrieve general business context from memory (L3 unvetted)'
    self.slots = {
      'key': ExactSlot(priority='optional'),
      'scope': CategorySlot(['specs', 'lessons', 'config', 'all'], priority='optional'),
    }
    self.tools = []


class SearchFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'search'
    self.dax = '{1BC}'
    self.goal = 'search vetted FAQs and curated reference content'
    self.slots = {
      'query': ExactSlot(),
    }
    self.tools = ['search_reference']


class PeekFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'peek'
    self.dax = '{09A}'
    self.goal = 'quick internal computation (count flows, check coverage)'
    self.slots = {
      'target': FreeTextSlot(),
    }
    self.tools = ['read_config']


class StudyFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'study'
    self.dax = '{29C}'
    self.goal = 'internally read a spec file to answer a question'
    self.slots = {
      'source': SourceSlot(1),
      'query': FreeTextSlot(priority='optional'),
    }
    self.tools = ['read_spec']


class AuditFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'audit'
    self.dax = '{39D}'
    self.goal = 'internally validate assistant consistency'
    self.slots = {}
    self.tools = ['validate_catalog']


class EmitFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'emit'
    self.dax = '{49A}'
    self.goal = 'internally trigger file generation after approval'
    self.slots = {
      'format': CategorySlot(['ontology', 'yaml', 'all']),
    }
    self.tools = ['generate_config']
