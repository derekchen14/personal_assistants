from backend.components.flow_stack.slots import *
from backend.components.flow_stack.parents import *

OUTLINE_LEVELS = {
    0: {'markdown': '# Title', 'meaning': 'Post title'},
    1: {'markdown': '## Heading', 'meaning': 'Section header'},
    2: {'markdown': '### Sub-heading', 'meaning': 'Sub-section'},
    3: {'markdown': ' - bullet', 'meaning': 'Bullet point'},
    4: {'markdown': '   * sub-bullet', 'meaning': 'Sub-bullet'},
}

# ── Research (4 flows) ──────────────────────────────────────────────────────

class InspectFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'inspect'
    self.dax = '{1AD}'
    self.goal = ('report one or more metrics — word count, section count, reading time, image '
                 'count, post size — or post metadata: category tags, featured image, '
                 'publication/edit/scheduled dates, channels, status')
    self.slots = {
      'source': SourceSlot(1, priority='elective'),
      'metrics': ChecklistSlot(priority='elective'),
      'threshold': ScoreSlot(priority='optional'),  # check a metric against this bound
    }
    self.tools = ['read_metadata', 'find_posts', 'channel_status']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    for item in values.get('metrics', []):
      if isinstance(item, dict):
        self.slots['metrics'].add_one(**item)
      else:
        self.slots['metrics'].add_one(item)
    if 'threshold' in values:
      self.slots['threshold'].assign_one(float(values['threshold']))

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

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    if 'length' in values:
      self.slots['length'].level = int(values['length'])
      self.slots['length'].check_if_filled()

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

  def fill_slot_values(self, values):
    if 'query' in values:
      self.slots['query'].add_one(values['query'])
    if 'count' in values:
      self.slots['count'].level = int(values['count'])
    return self.is_filled()

class CompareFlow(ResearchParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'compare'
    self.dax = '{18A}'
    self.goal = 'compare style or structure across two or more posts; sentence length, paragraph density, heading patterns, vocabulary, and tonal consistency'

    self.slots = {
      'source': SourceSlot(2),
      'category': CategorySlot(['inspect', 'check', 'tone']),
      'lookback': PositionSlot(priority='optional'),   # which prior version to compare against
      'mapping': DictionarySlot(priority='optional'),  # field/term mapping for the comparison
    }
    self.tools = ['read_metadata', 'read_section', 'inspect_post', 'diff_section']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    if 'category' in values:
      self.slots['category'].assign_one(values['category'])
    if 'lookback' in values:
      self.slots['lookback'].assign_one(values['lookback'])
    for key, val in values.get('mapping', {}).items():
      self.slots['mapping'].add_one(key, val)

# ── Draft (4 flows) ─────────────────────────────────────────────────────────

class BrainstormFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'brainstorm'
    self.dax = '{39D}'
    self.goal = 'come up with new ideas or angles for a given topic, word, or phrase; may include hooks, opening lines, synonyms, or new perspectives the user can choose from'

    self.slots = {
      'source': SourceSlot(1, entity_part=''),
      'topic': ExactSlot(priority='elective'),
      'ideas': ProposalSlot(priority='elective'),
    }
    self.tools = ['brainstorm_ideas', 'find_posts', 'search_notes', 'read_section']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    if 'topic' in values:
      self.slots['topic'].add_one(values['topic'])
    for item in values.get('ideas', []):
      self.slots['ideas'].add_one(item)

class OutlineFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'outline'
    self.dax = '{002}'
    self.goal = 'generate an outline including section headings, key bullet points, estimated word counts, and suggested reading order'
    self.slots = {
      'source': SourceSlot(1, priority='elective'),
      'sections': ChecklistSlot(priority='elective'),
      'topic': ExactSlot(priority='elective'),
      'depth': LevelSlot(priority='optional', threshold=1),
      'proposals': ProposalSlot(priority='optional'),  # used internally, rather than filled by NLU
    }
    self.tools = ['find_posts', 'brainstorm_ideas', 'create_post', 'generate_outline']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    for item in values.get('sections', []):
      self.slots['sections'].add_one(**item)
    if 'topic' in values:
      self.slots['topic'].add_one(values['topic'])
    if 'depth' in values:
      self.slots['depth'].level = int(values['depth'])
      self.slots['depth'].check_if_filled()

class ComposeFlow(DraftParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'compose'
    self.dax = '{3AD}'
    self.goal = 'draft a full post from its outline — converts outline bullets into prose paragraphs across the post (still rough). Input is an outline, output is a post. If no outline exists yet, outline first; for section-level edits use write, for whole-post revision use rework'
    self.slots = {
      'source': SourceSlot(1),
      'steps': ChecklistSlot(priority='elective'),
      'guidance': FreeTextSlot(priority='elective'),
    }
    self.tools = ['read_metadata', 'read_section', 'convert_to_prose', 'write_text', 'revise_content']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    for item in values.get('steps', []):
      self.slots['steps'].add_one(**item)
    for item in values.get('guidance', []):
      self.slots['guidance'].add_one(item)

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
      'image': ImageSlot(priority='optional'),         # image to insert into a section
      'position': PositionSlot(priority='optional'),   # where to insert the new content
      'settings': DictionarySlot(priority='optional'), # structural formatting settings
    }
    self.tools = ['find_posts', 'read_metadata', 'read_section', 'update_post', 'insert_section', 'revise_content', 'remove_content', 'write_text', 'insert_media']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    for item in values.get('steps', []):
      self.slots['steps'].add_one(**item)
    for item in values.get('feedback', []):
      self.slots['feedback'].add_one(item)
    if 'image' in values:
      self.slots['image'].assign_one(**values['image'])
    if 'position' in values:
      self.slots['position'].assign_one(values['position'])
    for key, val in values.get('settings', {}).items():
      self.slots['settings'].add_one(key, val)

# ── Revise (4 flows) ────────────────────────────────────────────────────────

class ReworkFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'rework'
    self.dax = '{006}'
    self.goal = 'major revision of draft content; restructures arguments, replaces weak sections, addresses reviewer comments. Operates across more than one section, up to the whole post. For paragraph- or sentence-level edits, use write'
    self.slots = {
      'source': SourceSlot(1, 'sec'),
      'category': CategorySlot(['swap', 'to_top', 'to_end', 'trim', 'sharpen', 'reframe'], priority='elective'),
      'suggestions': ChecklistSlot(priority='elective'),
      'remove': RemovalSlot(priority='optional'),
      'image': ImageSlot(priority='optional'),  # image to delete
      # what kind of thing is being removed (post-wide deletion vs section-level)
      'type': CategorySlot(['post', 'draft', 'section', 'paragraph', 'note', 'image'], priority='optional'),
    }
    self.tools = ['read_metadata', 'read_section', 'revise_content', 'insert_section', 'remove_content']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    if 'category' in values:
      self.slots['category'].assign_one(values['category'])
    for item in values.get('suggestions', []):
      self.slots['suggestions'].add_one(**item)
    for item in values.get('remove', []):
      self.slots['remove'].add_one(**item)
    if 'image' in values:
      self.slots['image'].assign_one(**values['image'])
    if 'type' in values:
      self.slots['type'].assign_one(values['type'])

class WriteFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'write'
    self.dax = '{003}'
    self.goal = 'sentence-level editing of a paragraph, sentence, or phrase — improves word choice, tightens sentences, fixes transitions, smooths flow, and trims or simplifies wording. Input is a section, output is a section; scope stays within a single paragraph or image, not the whole post (use rework for that)'
    self.slots = {
      'source': SourceSlot(1, 'snip'),
      'style_notes': FreeTextSlot(priority='optional'),
      'image': ImageSlot(priority='elective'),
      'suggestions': ChecklistSlot(priority='elective'),
    }
    self.tools = ['read_metadata', 'read_section', 'write_text', 'revise_content', 'remove_content']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    for item in values.get('style_notes', []):
      self.slots['style_notes'].add_one(item)
    if 'image' in values:
      self.slots['image'].assign_one(**values['image'])
    for item in values.get('suggestions', []):
      self.slots['suggestions'].add_one(**item)

class AuditFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'audit'
    self.dax = '{13A}'
    self.goal = "check that the post is written in the user's voice rather than sounding like AI — compares voice, terminology, formatting, and stylistic patterns against previous posts, then fixes the drift directly and applies any requested tone shift"
    self.slots = {
      'source': SourceSlot(1, 'post'),
      'reference_count': LevelSlot(priority='optional', threshold=1),
      'threshold': ProbabilitySlot(priority='optional'),
      'tone': ExactSlot(priority='optional'),             # free-form target register
      'suggestions': ChecklistSlot(priority='optional'),  # tone-change instructions
    }
    self.tools = ['find_posts', 'compare_style', 'editor_review', 'inspect_post', 'read_section', 'revise_content']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    if 'reference_count' in values:
      self.slots['reference_count'].level = int(values['reference_count'])
      self.slots['reference_count'].check_if_filled()
    if 'threshold' in values:
      self.slots['threshold'].assign_one(values['threshold'])
    if 'tone' in values:
      self.slots['tone'].add_one(values['tone'])
    for item in values.get('suggestions', []):
      self.slots['suggestions'].add_one(**item)

class ProposeFlow(ReviseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'propose'
    self.dax = '{39B}'
    self.goal = 'generate 2-3 targeted alternatives to fill a placeholder gap (<fill in here>, TODO, or blank slot) in existing content, presented inline for the user to pick; like brainstorm but scoped to a specific slot in a draft'
    self.slots = {
      'source': SourceSlot(1, 'sec'),
      'context': FreeTextSlot(priority='optional'),
    }
    self.tools = ['read_metadata', 'read_section', 'revise_content']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    for item in values.get('context', []):
      self.slots['context'].add_one(item)

# ── Publish (3 flows) ───────────────────────────────────────────────────────

class ReleaseFlow(PublishParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'release'
    self.dax = '{004}'
    self.goal = 'publish the post to the primary blog; makes the post live immediately on the main channel. Cross-posts to secondary channels when channels are named.'
    self.slots = {
      'source': SourceSlot(1),
      'channel': ChannelSlot(priority='optional'),  # secondary channels to cross-post to
    }
    self.tools = ['read_metadata', 'channel_status', 'release_post']

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    for item in values.get('channel', []):
      self.slots['channel'].add_one(item)

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

  def fill_slot_values(self, values):
    for item in values.get('source', []):
      self.slots['source'].add_one(**item)
    for item in values.get('channel', []):
      self.slots['channel'].add_one(item)
    if 'datetime' in values:
      self.slots['datetime'].add_one(**values['datetime'])

class CiteFlow(PublishParentFlow):
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

  def fill_slot_values(self, values):
    for item in values.get('target', []):
      self.slots['target'].add_one(**item)
    if 'url' in values:
      self.slots['url'].add_one(values['url'])

# ── Converse (1 flow) ───────────────────────────────────────────────────────

class ChatFlow(ConverseParentFlow):
  def __init__(self):
    super().__init__()
    self.flow_type = 'chat'
    self.dax = '{000}'
    self.goal = 'open-ended conversation; general Q&A about writing craft, blogging strategy, SEO, audience engagement, or any topic not tied to a specific post action'
    self.slots = {
      'topic': FreeTextSlot(priority='optional'),
    }
    self.tools = []

  def fill_slot_values(self, values):
    for item in values.get('topic', []):
      self.slots['topic'].add_one(item)

# ── Plan (flow_classes only — no FLOW_ONTOLOGY entry, so never a detection candidate) ───────

class PlanFlow(BaseFlow):
  """The Plan Flow oversees, it does not do the work (round 3.5). think stacks it Pending at
  the bottom with the detected steps above it; it anchors has_plan and its `steps` checklist
  keeps a readable record of the plan shape even after steps complete and pop. think fills the
  checklist directly at stacking — no LLM slot fill.
  TODO(review pass, future round): when this flow surfaces as Active, its policy reviews what
  the overseen steps did (reading the session scratchpad) and makes final adjustments. Until
  that policy exists, the pop that surfaces it removes it instead of running it."""
  def __init__(self):
    super().__init__()
    self.parent_type = 'Plan'
    self.flow_type = 'plan'
    self.dax = '{29D}'
    self.entity_slot = 'steps'
    self.goal = 'oversee a multi-step plan: hold the ordered steps and review their work at the end'
    self.slots = {
      'steps': ChecklistSlot(),
    }
    self.tools = []

  def fill_slot_values(self, values):
    for item in values.get('steps', []):
      if isinstance(item, dict):
        self.slots['steps'].add_one(**item)
      else:
        self.slots['steps'].add_one(item)
