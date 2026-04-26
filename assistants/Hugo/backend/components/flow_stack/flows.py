from backend.components.flow_stack.slots import *
from backend.components.flow_stack.parents import *

OUTLINE_LEVELS = {
    0: {'markdown': '# Title', 'meaning': 'Post title'},
    1: {'markdown': '## Heading', 'meaning': 'Section header'},
    2: {'markdown': '### Sub-heading', 'meaning': 'Sub-section'},
    3: {'markdown': ' - bullet', 'meaning': 'Bullet point'},
    4: {'markdown': '   * sub-bullet', 'meaning': 'Sub-bullet'},
}

# ── Research (7 flows) ──────────────────────────────────────────────────────

class BrowseFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'browse'
    self.dax = '{012}'
    self.entity_slot = 'tags'
    self.goal = 'browse the user\'s tagged content and saved notes for trending subjects, ideas, and content gaps; excludes drafts and posts which use the "find" flow instead'

    self.slots = {
      'tags': FreeTextSlot(priority='required'),
      'target': CategorySlot(['tag', 'note', 'both'], priority='required'),
    }
    self.tools = ['find_posts', 'brainstorm_ideas', 'search_notes']

class SummarizeFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'summarize'
    self.dax = '{19A}'
    self.goal = 'synthesize a post into a short paragraph capturing the core argument, target audience, and main takeaways; useful for excerpts, SEO descriptions, or pre-reads before writing a follow-up'
    self.slots = {
      'source': SourceSlot(1),
      'length': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['read_metadata', 'read_section', 'summarize_text']

class CheckFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'check'
    self.dax = '{0AD}'
    self.goal = 'check the technical metadata surrounding a post; category tags, has_featured_image, publication date, last edited date, scheduled date, channels, status: draft, scheduled, published, or unpublished'

    self.slots = {
      'source': SourceSlot(1, priority='optional'),
    }
    self.tools = ['find_posts', 'channel_status']

class InspectFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'inspect'
    self.dax = '{1BD}'
    self.goal = 'report numeric content metrics; word count, section count, reading time, image count, post size (MB); optionally filtered to a single metric. Use check for post metadata'

    self.slots = {
      'source': SourceSlot(1),
      'aspect': CategorySlot(['word_count', 'num_sections', 'time_to_read', 'image_count', 'num_links', 'post_size'], priority='required'),
      'threshold': ScoreSlot(priority='optional'),
    }
    # Deterministic flow — the policy calls inspect_post directly; no skill delegation.
    self.tools = ['inspect_post']

class FindFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'find'
    self.dax = '{001}'
    self.entity_slot = 'query'
    self.goal = 'search previous posts by keyword or topic; returns matching titles, excerpts, and publication dates sorted by relevance'

    self.slots = {
      'query': ExactSlot(),
      'count': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['find_posts']

class CompareFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'compare'
    self.dax = '{18A}'
    self.goal = 'compare style or structure across two or more posts; sentence length, paragraph density, heading patterns, vocabulary, and tonal consistency'

    self.slots = {
      'source': SourceSlot(2),
    }
    self.tools = ['read_metadata', 'read_section', 'compare_style']

class DiffFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'diff'
    self.dax = '{0BD}'
    self.goal = 'compare two versions of a section side by side; shows additions, deletions, and modifications highlighted so the user can evaluate what changed'

    self.slots = {
      'source': SourceSlot(1),
      'lookback': PositionSlot(priority='elective'),
      'mapping': DictionarySlot(priority='elective'),
    }
    self.tools = ['find_posts', 'read_metadata', 'read_section', 'diff_section']

# ── Draft (7 flows) ─────────────────────────────────────────────────────────

class BrainstormFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'brainstorm'
    self.dax = '{29A}'
    self.goal = 'come up with new ideas or angles for a given topic, word, or phrase; may include hooks, opening lines, synonyms, or new perspectives the user can choose from'

    self.slots = {
      'source': SourceSlot(1, entity_part='', priority='elective'),
      'topic': ExactSlot(priority='elective'),
      'ideas': ProposalSlot(priority='optional'),
    }
    self.tools = ['brainstorm_ideas', 'find_posts', 'search_notes', 'read_section']

class CreateFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'create'
    self.entity_slot = 'title'
    self.dax = '{05A}'
    self.goal = 'start a new post from scratch; initializes a post record with title, topic, and empty sections. Does not generate content; use outline or compose to fill sections'
    self.slots = {
      'title': ExactSlot(priority='required'),
      'type': CategorySlot(['draft', 'note'], priority='required'),
      'topic': ExactSlot(priority='optional'),
    }
    self.tools = ['create_post']

class OutlineFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'outline'
    self.dax = '{002}'
    self.goal = 'generate an outline including section headings, key bullet points, estimated word counts, and suggested reading order'
    self.slots = {
      'source': SourceSlot(1, priority='required'),
      'sections': ChecklistSlot(priority='elective'),
      'topic': ExactSlot(priority='elective'),
      'depth': LevelSlot(priority='optional', threshold=1),
      'proposals': ProposalSlot(priority='optional'),  # used internally, rather than filled by NLU
    }
    self.tools = ['find_posts', 'brainstorm_ideas', 'generate_outline']

class RefineFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'refine'
    self.dax = '{02B}'
    self.goal = 'refine the bullet points in the outline; adjust headings, reorder points, add or remove subsections, and incorporate feedback'
    self.slots = {
      'source': SourceSlot(1),
      'steps': ChecklistSlot(priority='elective'),  # structured list of specific changes requested by the user
      'feedback': FreeTextSlot(priority='elective'),  # open-ended feedback on how to improve the outline
    }
    self.tools = ['find_posts', 'read_metadata', 'read_section', 'generate_section', 'remove_content', 'write_text']

class CiteFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'cite'
    self.entity_slot = 'target'
    self.dax = '{15B}'
    self.goal = 'add a citation to a sentence or phrase within a post; if a URL is provided, attach it directly; if only a target snippet is provided, search the web for a supporting source and propose it for user confirmation'
    self.slots = {
      'target': TargetSlot(1, entity_part='snip', priority='elective'),
      'url': ExactSlot(priority='elective'),
    }
    self.tools = ['read_metadata', 'read_section', 'revise_content', 'web_search']

class ComposeFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'compose'
    self.dax = '{003}'
    self.goal = 'write a section from scratch based on instructions or an outline. If only given a topic, generate an outline first; for editing existing content, use rework'
    self.slots = {
      'source': SourceSlot(1),
      'steps': ChecklistSlot(priority='elective'),
      'guidance': FreeTextSlot(priority='elective')
    }
    self.tools = ['read_metadata', 'read_section', 'convert_to_prose', 'write_text', 'revise_content']

class AddFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'add'
    self.dax = '{005}'
    self.goal = 'add more in depth content, such as sub-sections or an image to an existing section; inserted at a specific position'
    # 'Add' is about drilling down into more depth within a section, whereas 'Refine' is about shuffling sections around or even removing sections.
    self.slots = {
      'source': SourceSlot(1),
      'points': ChecklistSlot(priority='elective'),
      'additions': DictionarySlot(priority='elective'),  # key is the section name, value is the bulletpoint to add
      'image': ImageSlot(priority='elective'),
      'position': PositionSlot(priority='optional'),
    }
    self.tools = ['read_metadata', 'read_section', 'insert_section', 'revise_content', 'insert_media']

# ── Revise (7 flows) ────────────────────────────────────────────────────────

class ReworkFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'rework'
    self.dax = '{006}'
    self.goal = 'major revision of draft content; restructures arguments, replaces weak sections, addresses reviewer comments. Scope can go across the whole post, or an entire section. For smaller changes, use polish'
    self.slots = {
      'source': SourceSlot(1, 'sec'),
      'remove': RemovalSlot(priority='optional'),
      'changes': FreeTextSlot(priority='elective'),
      'suggestions': ChecklistSlot(priority='elective'),
    }
    self.tools = ['read_metadata', 'read_section', 'revise_content', 'insert_section', 'remove_content']

class PolishFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'polish'
    self.dax = '{3BD}'
    self.goal = 'editing of a specific paragraph, sentence or phrase; improves word choice, tightens sentences, fixes transitions, and smooths flow without changing meaning or structure. The scope is within a single paragraph or image, not across the whole post'
    self.slots = {
      'source': SourceSlot(1, 'sec'),
      'style_notes': FreeTextSlot(priority='optional'),
      'image': ImageSlot(priority='optional'),
    }
    self.tools = ['read_metadata', 'read_section', 'write_text', 'revise_content']

class ToneFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'tone'
    self.dax = '{38A}'
    self.goal = 'adjust tone or voice across the entire post; shifts register (formal, casual, technical, academic, witty, natural), adjusts sentence length and vocabulary complexity'
    tone_options = ['formal', 'casual', 'technical', 'academic', 'witty', 'natural']
    self.slots = {
      'source': SourceSlot(1, 'post'),
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
    self.tools = ['read_metadata', 'read_section', 'revise_content', 'channel_status']

class AuditFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'audit'
    self.dax = '{13A}'
    self.goal = "check that the post is written in the user's voice rather than sounding like AI; compares voice, terminology, formatting conventions, and stylistic patterns against previous posts"
    self.slots = {
      'source': SourceSlot(1, 'post'),
      'reference_count': LevelSlot(priority='optional', threshold=1),
      'threshold': ProbabilitySlot(priority='optional'),
    }
    self.tools = ['find_posts', 'compare_style', 'editor_review', 'inspect_post', 'read_section']

class SimplifyFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'simplify'
    self.dax = '{7BD}'
    self.goal = 'reduce complexity of a section or note; shorten paragraphs, simplify sentence structure, remove redundancy; image simplification means replacing with a simpler alternative or removing entirely'
    self.slots = {
      'source': SourceSlot(1, 'sec', priority='elective'),
      'image': ImageSlot(priority='elective'),
      'guidance': FreeTextSlot(priority='required'),
    }
    self.tools = ['read_metadata', 'read_section', 'revise_content', 'remove_content', 'write_text']

class RemoveFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'remove'
    self.dax = '{007}'
    self.goal = 'remove a section from the post, delete a draft or note'
    self.slots = {
      'source': SourceSlot(1, 'sec', priority='elective'),
      'image': ImageSlot(priority='elective'),
      'type': CategorySlot(['post', 'draft', 'section', 'paragraph', 'note', 'image'], priority='required'),
    }
    self.tools = ['delete_post', 'remove_content', 'read_metadata']

class TidyFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'tidy'
    self.dax = '{3AB}'
    self.goal = 'normalize structural formatting across the post; consistent heading hierarchy, list indentation, paragraph spacing, and whitespace cleanup. Does not change wording'
    self.slots = {
      'source': SourceSlot(1, 'post'),
      'settings': DictionarySlot(),
      'image': ImageSlot(priority='optional'),
    }
    self.tools = ['read_metadata', 'read_section', 'revise_content', 'check_links']

# ── Publish (7 flows) ───────────────────────────────────────────────────────

class ReleaseFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'release'
    self.dax = '{04A}'
    self.goal = 'publish the post to the primary blog; makes the post live immediately on the main channel. Use syndicate to cross-post, promote to amplify reach after publishing'
    self.slots = {
      'source': SourceSlot(1),
      'channel': ChannelSlot(priority='required'),
    }
    # `update_post` is called by release_policy after the skill returns; the
    # skill itself must not flip status, so it's not exposed to the LLM.
    self.tools = ['read_metadata', 'channel_status', 'release_post']

class SyndicateFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'syndicate'
    self.dax = '{04C}'
    self.goal = 'cross-post to one or more secondary channels; adapts formatting for each target (Medium, Dev.to, LinkedIn, Substack) and publishes a tailored version'
    self.slots = {
      'channel': ChannelSlot(),
      'source': SourceSlot(1),
    }
    self.tools = ['read_metadata', 'read_section', 'channel_status', 'release_post']

class ScheduleFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'schedule'
    self.dax = '{4AC}'
    self.goal = 'schedule a post for future publication; sets a specific date and time for automatic publishing on a given channel'
    self.slots = {
      'source': SourceSlot(1),
      'channel': ChannelSlot(),
      'datetime': RangeSlot(['minute', 'hour', 'day', 'week']),
    }
    self.tools = ['list_channels', 'channel_status', 'release_post', 'update_post']

class PreviewFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'preview'
    self.dax = '{4AD}'
    self.goal = "preview how the post will look when published; renders the post in the target channel's format so the user can review layout, images, and formatting before going live"
    self.slots = {
      'source': SourceSlot(1),
      'channel': ChannelSlot(priority='optional'),
    }
    self.tools = ['read_metadata', 'read_section']

class PromoteFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'promote'
    self.dax = '{004}'
    self.goal = 'make a published post more prominent; pin to the top of the blog, mark as featured, announce to subscribers, or share to social channels and email lists. Amplifies reach after release or syndicate'
    self.slots = {
      'source': SourceSlot(1),
      'channel': CategorySlot(['pin', 'feature', 'announce', 'social'], priority='optional'),
    }
    self.tools = ['read_metadata', 'promote_post']

class CancelFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'cancel'
    self.entity_slot = 'remove'
    self.dax = '{04F}'
    self.goal = 'cancel a scheduled publication or unpublish a live post; reverts to draft status or removes from the channel entirely'
    self.slots = {
      'remove': RemovalSlot(1),
      'reason': ExactSlot(priority='optional'),
    }
    self.tools = ['read_metadata', 'cancel_release', 'update_post']

class SurveyFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'survey'
    self.entity_slot = 'channel'
    self.dax = '{01C}'
    self.goal = 'view configured publishing channels and their health; lists connected channels (WordPress, Medium, etc.), API status, last sync date, and credential validity'
    self.slots = {
      'channel': ChannelSlot(priority='optional'),
    }
    self.tools = ['list_channels', 'channel_status']

# ── Converse (7 flows) ──────────────────────────────────────────────────────

class ExplainFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'explain'
    self.dax = '{009}'
    self.goal = 'Hugo explains what it did or plans to do; transparency into the writing process and recent actions'
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
    self.goal = 'open-ended conversation; general Q&A about writing craft, blogging strategy, SEO, audience engagement, or any topic not tied to a specific post action'
    self.slots = {}
    self.tools = []

class PreferenceFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'preference'
    self.dax = '{08A}'
    self.goal = 'set a persistent writing preference stored in Memory Manager (L2); preferred tone, default post length, heading style, Oxford comma usage, or channel defaults'
    self.slots = {
      'setting': DictionarySlot(['key', 'value']),
    }
    self.tools = []

class SuggestFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'suggest'
    self.dax = '{29B}'
    self.goal = 'Hugo proactively suggests a next step based on current context; what to write next, which section needs attention, a new angle to explore, or an improvement to try'
    self.slots = {}
    self.tools = ['brainstorm_ideas', 'find_posts']

class UndoFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'undo'
    self.dax = '{08F}'
    self.goal = 'reverse the most recent writing action; rolls back the last edit, addition, deletion, or formatting change and restores the previous version of the affected section'
    self.slots = {
      'turn': LevelSlot(priority='elective', threshold=1),
      'action': ExactSlot(priority='elective'),
    }
    self.tools = ['rollback_post']

class EndorseFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'endorse'
    self.dax = '{09E}'
    self.goal = "accept Hugo's proactive suggestion and trigger the corresponding action; e.g., a recommended edit, topic idea, or next step that Hugo offered via suggest"
    self.slots = {
      'action': ExactSlot(),
    }
    self.tools = []

class DismissFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'dismiss'
    self.dax = '{09F}'
    self.goal = "decline Hugo's proactive suggestion without providing feedback; Hugo notes the preference and moves on without further prompting"
    self.slots = {}
    self.tools = []

# ── Plan (6 flows) ──────────────────────────────────────────────────────────

class BlueprintFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'blueprint'
    self.entity_slot = 'topic'
    self.dax = '{25A}'
    self.goal = 'plan the full post creation workflow from idea to publication; orchestrates Research, Draft, Revise, and Publish flows into a sequenced checklist with dependencies'
    self.slots = {
      'topic': ExactSlot(priority='optional'),
      'steps': ChecklistSlot(priority='optional'),
    }
    self.tools = []

class TriageFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'triage'
    self.dax = '{23A}'
    self.goal = 'plan a revision sequence; examines a draft and prioritizes which sections need rework, polish, or restructuring; produces an ordered checklist of revision tasks'
    self.slots = {
      'source': RemovalSlot(1, 'sec'),
      'scope': CategorySlot(['content', 'structure', 'style', 'seo', 'full'], priority='optional'),
      'count': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['read_metadata', 'inspect_post']

class CalendarFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'calendar'
    self.entity_slot = 'target'
    self.dax = '{24A}'
    self.goal = 'plan a content calendar; lays out a publishing schedule over weeks or months: which topics to draft, target publish dates, and how to space content for consistency'
    self.slots = {
      'target': TargetSlot(1, 'post'),
      'timeframe': RangeSlot([], priority='elective'),
      'count': LevelSlot(priority='elective', threshold=1),
    }
    self.tools = ['find_posts']

class ScopeFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'scope'
    self.entity_slot = 'topic'
    self.dax = '{12A}'
    self.goal = 'plan topic research before writing; defines what information to gather, which previous posts to reference, and what questions to answer before drafting begins'
    self.slots = {
      'topic': ExactSlot(),
    }
    self.tools = ['find_posts', 'brainstorm_ideas']

class DigestFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'digest'
    self.dax = '{25B}'
    self.goal = 'plan a multi-part blog series; splits a broad theme into installments, defines the narrative arc, assigns subtopics to each part, and sets a suggested publication sequence'
    self.slots = {
      'source': SourceSlot(1, 'post'),
      'theme': ExactSlot(),
      'part_count': LevelSlot(priority='optional', threshold=1),
    }
    self.tools = ['find_posts']

class RememberFlow(PlanParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'remember'
    self.entity_slot = 'topic'
    self.dax = '{19B}'
    self.goal = 'plan a memory operation; determines whether information should be stored (L1 scratchpad), saved as a preference (L2), or retrieved from business context (L3), then orchestrates the appropriate internal flows'
    self.slots = {
      'topic': ExactSlot(priority='elective'),
      'scope': CategorySlot(['session', 'user', 'global'], priority='elective'),
    }
    self.tools = []

# ── Internal (7 flows) ──────────────────────────────────────────────────────

class RecapFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recap'
    self.dax = '{018}'
    self.goal = 'read back a previously noted fact from the current session scratchpad (L1); a decision, constraint, topic preference, or reference the agent stored earlier via store'
    self.slots = {
      'key': ExactSlot(priority='optional'),
    }
    self.tools = []

class StoreFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'store'
    self.dax = '{058}'
    self.goal = 'save a key-value pair to the session scratchpad (L1) for later use in the same session; topic preferences, user corrections, interim decisions, or reference snippets'
    self.slots = {
      'entry': DictionarySlot(['key', 'value']),
    }
    self.tools = []

class RecallFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'recall'
    self.dax = '{289}'
    self.goal = 'look up persistent user preferences from Memory Manager (L2); default tone, word count targets, stylistic rules, or channel credentials set via the preference flow'
    self.slots = {
      'key': ExactSlot(priority='optional'),
    }
    self.tools = []

class RetrieveFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'retrieve'
    self.dax = '{049}'
    self.goal = 'fetch general business context from Memory Manager; unvetted documents, style guides, or domain knowledge (L3)'
    self.slots = {
      'topic': ExactSlot(),
      'context': ExactSlot(priority='optional'),
    }
    self.tools = []

class SearchFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'search'
    self.dax = '{189}'
    self.goal = 'look up vetted FAQs and curated editorial guidelines; the unstructured equivalent of a style manual'
    self.slots = {
      'query': ExactSlot(),
    }
    self.tools = ['find_posts']

class ReferenceFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'reference'
    self.dax = '{139}'
    self.goal = 'look up word definitions, synonyms, antonyms, or usage examples via dictionary and thesaurus; e.g., "synonym for important", "definition of ephemeral", "formal alternatives to good"'
    self.slots = {
      'word': ExactSlot(),
    }
    self.tools = []

class StudyFlow(InternalParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'study'
    self.dax = '{1AC}'
    self.goal = 'internally load a previous post into agent context without showing it to the user; used to match voice, structure, or vocabulary patterns when writing new content'
    self.slots = {
      'source': SourceSlot(1),
      'scope': CategorySlot(['voice', 'structure', 'vocabulary', 'full'], priority='optional'),
    }
    self.tools = ['read_metadata', 'read_section']
