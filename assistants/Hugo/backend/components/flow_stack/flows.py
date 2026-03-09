from backend.components.flow_stack.slots import *
from backend.components.flow_stack.parents import *


# ── Research (6 flows) ──────────────────────────────────────────────────────

class BrowseFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'browse'
    self.dax = '{012}'
    self.goal = 'browse available topic ideas'
    self.slots = {
      'category': CategorySlot(['technology', 'business', 'lifestyle', 'tutorial', 'opinion', 'review', 'news'], priority='optional'),
    }
    self.tools = ['browse_topics', 'search_posts', 'suggest_keywords', 'search_by_time', 'search_inspiration']


class ViewFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'view'
    self.dax = '{1AD}'
    self.goal = 'view a specific post or draft in full'
    self.slots = {
      'source': SourceSlot(1),
    }
    self.tools = ['read_post']


class CheckFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'check'
    self.dax = '{0AD}'
    self.goal = 'check workflow status of posts'
    self.slots = {
      'source': SourceSlot(1, priority='optional'),
    }
    self.tools = ['search_posts', 'check_platform', 'search_by_time']


class InspectFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'inspect'
    self.dax = '{1BD}'
    self.goal = 'analyze content metrics and completeness'
    self.slots = {
      'source': SourceSlot(1),
      'aspect': CategorySlot(['readability', 'seo', 'structure', 'completeness', 'links', 'media'], priority='optional'),
      'threshold': ScoreSlot(priority='optional'),
    }
    self.tools = ['get_post', 'analyze_content', 'check_readability', 'analyze_seo', 'check_links', 'heads_or_tails']


class FindFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'find'
    self.dax = '{1AB}'
    self.goal = 'search previous posts by keyword or topic'
    self.slots = {
      'query': FreeTextSlot(),
      'count': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['search_posts', 'search_by_time']


class CompareFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'compare'
    self.dax = '{18A}'
    self.goal = 'compare style or structure across two or more posts'
    self.slots = {
      'source': SourceSlot(2),
    }
    self.tools = ['compare_posts', 'read_post']


# ── Draft (7 flows) ─────────────────────────────────────────────────────────

class OutlineFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'outline'
    self.dax = '{02A}'
    self.goal = 'generate outline options for a topic'
    self.slots = {
      'topic': FreeTextSlot(),
      'depth': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['generate_outline', 'suggest_keywords', 'search_inspiration']


class RefineFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'refine'
    self.dax = '{02B}'
    self.goal = 'refine a specific section of the outline'
    self.slots = {
      'source': SourceSlot(1),
      'feedback': FreeTextSlot(priority='elective'),
      'steps': ChecklistSlot(priority='elective'),
    }
    self.tools = ['search_posts', 'get_post', 'read_post', 'read_outline', 'revise_content', 'update_section']


class ExpandFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'expand'
    self.dax = '{03A}'
    self.goal = 'expand existing content into full prose'
    self.slots = {
      'source': SourceSlot(1),
    }
    self.tools = ['read_post', 'expand_content', 'update_section', 'insert_media']


class WriteFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'write'
    self.dax = '{03B}'
    self.goal = 'write a section from scratch based on instructions'
    self.slots = {
      'source': SourceSlot(1),
      'steps': ChecklistSlot(priority='elective'),
      'instructions': FreeTextSlot(priority='elective')
    }
    self.tools = ['search_posts', 'get_post', 'generate_prose', 'draft_content', 'write_section', 'update_section', 'insert_media', 'search_sources', 'search_evidence']


class AddFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'add'
    self.dax = '{05B}'
    self.goal = 'add a new section to the post'
    self.slots = {
      'source': SourceSlot(1),
      'title': FreeTextSlot(),
      'position': PositionSlot(priority='optional'),
    }
    self.tools = ['search_posts', 'get_post', 'insert_section']


class CreateFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'create'
    self.dax = '{05A}'
    self.goal = 'start a new post from scratch. finalizes title and theme if the user is not clear enough'
    self.slots = {
      'topic': FreeTextSlot(priority='required'),
      'title': FreeTextSlot(priority='optional'),
    }
    self.tools = ['create_post']


class BrainstormFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'brainstorm'
    self.dax = '{29A}'
    self.goal = 'brainstorm ideas for a topic'
    self.slots = {
      'topic': FreeTextSlot(),
      'ideas': ProposalSlot(priority='optional'),
    }
    self.tools = ['brainstorm_ideas', 'search_inspiration']


# ── Revise (8 flows) ────────────────────────────────────────────────────────

class ReworkFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'rework'
    self.dax = '{03D}'
    self.goal = 'major revision of draft content'
    self.slots = {
      'source': SourceSlot(1),
      'remove': RemovalSlot('section', priority='optional'),
    }
    self.tools = ['read_post', 'read_outline', 'revise_content', 'write_section', 'update_section', 'delete_section', 'reorder_sections']


class PolishFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'polish'
    self.dax = '{3BD}'
    self.goal = 'light editing of a specific section'
    self.slots = {
      'source': SourceSlot(1),
      'style_notes': FreeTextSlot(priority='optional'),
    }
    self.tools = ['search_posts', 'get_post', 'read_post', 'revise_content', 'update_section', 'check_grammar', 'detect_issues']


class ToneFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'tone'
    self.dax = '{38A}'
    self.goal = 'adjust tone or voice across the entire post'
    tone_options = ['formal', 'casual', 'technical', 'academic', 'witty', 'natural']
    self.slots = {
      'source': SourceSlot(1),
      'custom_tone': ExactSlot(priority='elective'),
      'chosen_tone': CategorySlot(tone_options, priority='elective'),
    }
    self.tone_mapping_defaults = {
      'linkedin': ['formal', 'academic'],
      'twitter': ['casual', 'witty'],
      'github': ['technical'],
      'arxiv': ['academic'],
      'medium': ['natural', 'formal', 'witty'],
      'substack': ['natural', 'casual', 'technical'],
    }
    self.tools = ['read_post', 'adjust_tone', 'update_section', 'check_platform']


class AuditFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'audit'
    self.dax = '{13A}'
    self.goal = "check consistency with the user's published history"
    self.slots = {
      'source': SourceSlot(1),
      'reference_count': LevelSlot(priority='optional', threshold=1),
      'consistency': ProbabilitySlot(priority='optional'),
    }
    self.tools = ['read_post', 'audit_style']


class FormatFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'format'
    self.dax = '{3AD}'
    self.goal = 'apply platform-specific formatting for publication'
    self.slots = {
      'source': SourceSlot(1),
      'format': CategorySlot(['markdown', 'html', 'plaintext'], priority='required'),
    }
    self.tools = ['get_post', 'format_content', 'update_metadata', 'analyze_seo', 'insert_media']


class AmendFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'amend'
    self.dax = '{0AF}'
    self.goal = "push back on Hugo's last revision with specific notes"
    self.slots = {
      'feedback': FreeTextSlot(),
      'source': SourceSlot(1),
    }
    self.tools = ['read_post', 'revise_content', 'update_section']


class DiffFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'diff'
    self.dax = '{0BD}'
    self.goal = 'compare two versions of a section side by side'
    self.slots = {
      'source': SourceSlot(2),
    }
    self.tools = ['search_posts', 'get_post', 'diff_versions']


class TidyFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'tidy'
    self.dax = '{3AB}'
    self.goal = 'normalize structural formatting across the post'
    self.slots = {
      'source': SourceSlot(1),
      'settings': DictionarySlot(),
    }
    self.tools = ['get_post', 'normalize_structure', 'update_section', 'update_metadata', 'check_grammar', 'check_links']


# ── Publish (7 flows) ───────────────────────────────────────────────────────

class ReleaseFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'release'
    self.dax = '{04A}'
    self.goal = 'publish the post to the primary blog'
    self.slots = {
      'source': SourceSlot(1),
      'platform': PlatformSlot(),
    }
    self.tools = ['get_post', 'publish_post']


class SyndicateFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'syndicate'
    self.dax = '{04C}'
    self.goal = 'cross-post to a secondary platform'
    self.slots = {
      'platform': PlatformSlot(),
      'source': SourceSlot(1, priority='optional'),
    }
    self.tools = ['get_post', 'publish_post', 'format_content']


class ScheduleFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'schedule'
    self.dax = '{4AC}'
    self.goal = 'schedule a post for future publication'
    self.slots = {
      'source': SourceSlot(1),
      'platform': PlatformSlot(),
      'datetime': RangeSlot([]),
    }
    self.tools = ['manage_schedule', 'list_platforms', 'check_platform']


class PreviewFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'preview'
    self.dax = '{4AD}'
    self.goal = 'preview how the post will look when published'
    self.slots = {
      'source': SourceSlot(1),
      'platform': PlatformSlot(priority='optional'),
    }
    self.tools = ['get_post', 'render_preview']


class PromoteFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'promote'
    self.dax = '{4AE}'
    self.goal = 'make a published post more prominent by pinning, featuring, or announcing to subscribers and social channels'
    self.slots = {
      'source': SourceSlot(1),
      'channel': CategorySlot(priority='optional'),
    }
    self.tools = ['get_post', 'promote_post']


class CancelFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'cancel'
    self.dax = '{04F}'
    self.goal = 'cancel a scheduled publication or unpublish a live post'
    self.slots = {
      'source': SourceSlot(1),
      'reason': FreeTextSlot(priority='optional'),
    }
    self.tools = ['manage_schedule']


class SurveyFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'survey'
    self.dax = '{01C}'
    self.goal = 'view configured publishing platforms and their health'
    self.slots = {
      'platform': PlatformSlot(priority='optional'),
    }
    self.tools = ['list_platforms', 'check_platform']


# ── Converse (7 flows) ──────────────────────────────────────────────────────

class ExplainFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'explain'
    self.dax = '{009}'
    self.goal = 'explain what Hugo did or plans to do'
    self.slots = {
      'turn_id': PositionSlot(priority='elective'),
      'source': SourceSlot(1, priority='elective'),
    }
    self.tools = ['explain_action']


class ChatFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'chat'
    self.dax = '{000}'
    self.goal = 'open-ended conversation'
    self.slots = {}
    self.tools = []


class PreferenceFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'preference'
    self.dax = '{08A}'
    self.goal = 'set a persistent writing preference'
    self.slots = {
      'setting': DictionarySlot(['key', 'value']),
    }
    self.tools = []


class SuggestFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'suggest'
    self.dax = '{29B}'
    self.goal = 'suggest a next step based on current context'
    self.slots = {}
    self.tools = ['brainstorm_ideas', 'search_posts']


class UndoFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'undo'
    self.dax = '{08F}'
    self.goal = 'reverse the most recent writing action'
    self.slots = {
      'turn': LevelSlot(priority='elective', threshold=1),
      'action': FreeTextSlot(priority='elective'),
    }
    self.tools = ['rollback_post']


class EndorseFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'endorse'
    self.dax = '{08E}'
    self.goal = "accept Hugo's proactive suggestion or general agreement with next step"
    self.slots = {
      'action': FreeTextSlot(),
    }
    self.tools = []


class DismissFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'dismiss'
    self.dax = '{09F}'
    self.goal = "decline Hugo's proactive suggestion or general disagreement with the current path"
    self.slots = {}
    self.tools = []


# ── Plan (6 flows) ──────────────────────────────────────────────────────────

class BlueprintFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'blueprint'
    self.dax = '{25A}'
    self.goal = 'plan the full post creation workflow'
    self.slots = {
      'topic': FreeTextSlot(priority='optional'),
      'steps': ChecklistSlot(priority='optional'),
    }
    self.tools = []


class TriageFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'triage'
    self.dax = '{23A}'
    self.goal = 'plan a revision sequence for a draft'
    self.slots = {
      'source': SourceSlot(1),
      'scope': CategorySlot(['content', 'structure', 'style', 'seo', 'full'], priority='optional'),
    }
    self.tools = ['analyze_content', 'check_readability', 'detect_issues', 'heads_or_tails', 'read_outline']


class CalendarFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'calendar'
    self.dax = '{24A}'
    self.goal = 'plan a content calendar'
    self.slots = {
      'timeframe': RangeSlot([], priority='elective'),
      'count': LevelSlot(priority='elective', threshold=1),
    }
    self.tools = ['plan_calendar', 'search_by_time']


class ScopeFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'scope'
    self.dax = '{12A}'
    self.goal = 'plan topic research before writing'
    self.slots = {
      'topic': FreeTextSlot(),
    }
    self.tools = ['search_posts', 'browse_topics', 'search_sources', 'search_inspiration', 'read_outline']


class DigestFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'digest'
    self.dax = '{25B}'
    self.goal = 'plan a multi-part blog series'
    self.slots = {
      'theme': FreeTextSlot(),
      'part_count': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['plan_series']


class RememberFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'remember'
    self.dax = '{19B}'
    self.goal = 'plan a memory operation'
    self.slots = {
      'key': FreeTextSlot(priority='elective'),
      'scope': CategorySlot(['session', 'user', 'global'], priority='elective'),
    }
    self.tools = []


# ── Internal (7 flows) ──────────────────────────────────────────────────────

class RecapFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recap'
    self.dax = '{018}'
    self.goal = 'read back a fact from the session scratchpad'
    self.slots = {
      'key': FreeTextSlot(priority='optional'),
    }
    self.tools = []


class StoreFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'store'
    self.dax = '{058}'
    self.goal = 'save a key-value pair to the session scratchpad'
    self.slots = {
      'key': FreeTextSlot(),
      'value': FreeTextSlot(),
    }
    self.tools = []


class RecallFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recall'
    self.dax = '{289}'
    self.goal = 'look up persistent user preferences'
    self.slots = {
      'key': FreeTextSlot(priority='optional'),
    }
    self.tools = []


class RetrieveFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'retrieve'
    self.dax = '{049}'
    self.goal = 'fetch general business context from Memory Manager'
    self.slots = {
      'topic': FreeTextSlot(),
      'context': FreeTextSlot(priority='optional'),
    }
    self.tools = []


class SearchFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'search'
    self.dax = '{189}'
    self.goal = 'look up vetted FAQs and curated editorial guidelines'
    self.slots = {
      'query': FreeTextSlot(),
    }
    self.tools = ['search_reference']


class ReferenceFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'reference'
    self.dax = '{139}'
    self.goal = 'look up word definitions, synonyms, or usage examples'
    self.slots = {
      'word': ExactSlot(),
    }
    self.tools = ['lookup_word']


class StudyFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'study'
    self.dax = '{1AC}'
    self.goal = 'internally load a previous post into agent context'
    self.slots = {
      'source': SourceSlot(1),
      'scope': CategorySlot(['voice', 'structure', 'vocabulary', 'full'], priority='optional'),
    }
    self.tools = ['read_post']
