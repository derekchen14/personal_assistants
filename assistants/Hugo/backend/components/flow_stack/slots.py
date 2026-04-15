"""
Slot types for Hugo (Blog Writing).

12 universal slots + 4 domain-specific.
Grounding entity_parts: post, section, snippet (snip), channel.

Hierarchy:
  BaseSlot
  ├── GroupSlot            (multiple values in a list)
  │   ├── SourceSlot       (existing entities: post, section, snippet)
  │   │   ├── TargetSlot   (new entities being created)
  │   │   ├── RemovalSlot  (entities being removed)
  │   │   └── ChannelSlot  (publishing destination)       [domain-specific]
  │   ├── FreeTextSlot     (open-ended text values)
  │   ├── ChecklistSlot    (ordered steps to check off)
  │   └── ProposalSlot     (selectable options)
  ├── LevelSlot            (numeric threshold)
  │   ├── PositionSlot     (non-negative integer)
  │   ├── ProbabilitySlot  (0-1 range)                    [domain-specific]
  │   └── ScoreSlot        (any numeric value)            [domain-specific]
  ├── CategorySlot         (one from predefined list, 8 max)
  ├── ExactSlot            (specific term or phrase)
  ├── DictionarySlot       (key-value pairs)
  ├── RangeSlot            (time or value range)
  └── ImageSlot            (hero image, diagram, picture) [domain-specific]
"""

class BaseSlot(object):
  def __init__(self, priority):
    self.filled = False
    self.uncertain = False
    self.criteria = 'single'
    self.priority = priority
    self.value = ''

  def __str__(self):
    if self.criteria == 'single':
      return f"{self.slot_type}: {self.value}"
    elif self.criteria == 'multiple':
      return f"{self.slot_type}: {self.values}"
    elif self.criteria == 'numeric':
      return f"{self.slot_type}: {self.level}"

  def check_if_filled(self):
    self.filled = len(self.value) > 0
    return self.filled

  def to_dict(self):
    if self.criteria == 'multiple':
      return self.values
    elif self.criteria == 'numeric':
      return self.level
    return self.value

  def reset(self):
    self.value = ''
    self.filled = False


class GroupSlot(BaseSlot):
  """Slot values are multiple items in a list rather than a single string."""
  def __init__(self, min_size, priority='required'):
    super().__init__(priority)
    self.criteria = 'multiple'
    self.values = []
    self.size = min_size

  def __str__(self):
    return f"{self.slot_type}: {self.values}"

  def check_if_filled(self):
    self.filled = len(self.values) >= self.size
    return self.filled

  def reset(self):
    self.values = []
    self.filled = False
    if hasattr(self, '_keys'):
      self._keys = []
    if hasattr(self, 'steps'):
      self.steps = []
    if hasattr(self, 'options'):
      self.options = []


# ── Grounding Entity ───────────────────────────────────────────────────────

class SourceSlot(GroupSlot):
  """References existing entities. Each entity is {post, sec, snip, chl, ver}."""
  def __init__(self, min_size=1, entity_part='', priority='required'):
    super().__init__(min_size, priority)
    self.slot_type = 'source'
    self.entity_part = entity_part
    self._keys = []
    self.active_post = ''
    if entity_part:
      self.purpose = f"at least {min_size} {entity_part}" if min_size == 1 else f"at least {min_size} {entity_part}s"
    else:
      self.purpose = f"at least {min_size} grounding reference" if min_size == 1 else f"at least {min_size} grounding references"

  def add_one(self, post, sec='', snip='', chl='', ver=False):
    key = f"{post}-{sec}"
    alt_key = f"{self.active_post}-{sec}"
    if key in self._keys:
      idx = self._keys.index(key)
      self.values[idx]['ver'] = ver
    elif alt_key in self._keys:
      pass  # earlier post is the active one
    else:
      entity = {'post': post, 'sec': sec, 'snip': snip, 'chl': chl, 'ver': ver}
      self.values.append(entity)
      self._keys.append(key)
    self.check_if_filled()

  def check_if_filled(self):
    valid = [e for e in self.values if e.get('post')]
    self.filled = len(valid) >= self.size
    return self.filled

  def _rebuild_keys(self):
    self._keys = [f"{e['post']}-{e['sec']}" for e in self.values]

  def replace_entity(self, old_post, old_sec, new_post='', new_sec=''):
    for i, entity in enumerate(self.values):
      if entity['post'] == old_post and entity['sec'] == old_sec:
        if new_post:
          self.values[i]['post'] = new_post
        if new_sec:
          self.values[i]['sec'] = new_sec
    self._rebuild_keys()

  def drop_unverified(self, conditional=False):
    verified = [e for e in self.values if e['ver']]
    if conditional:
      if len(verified) > 0:
        self.values = verified
    else:
      self.values = verified
    self._rebuild_keys()
    self.check_if_filled()

  def drop_ambiguous(self):
    self.values = [e for e in self.values if e['chl'] != 'ambiguous']
    self._rebuild_keys()
    self.check_if_filled()

  def is_verified(self):
    return len([e for e in self.values if e['ver']]) >= self.size

  def post_name(self):
    return self.values[0]['post'] if self.values else 'N/A'


class TargetSlot(SourceSlot):
  """New entities being created (new post title, new section)."""
  def __init__(self, min_size, entity_part, priority='required'):
    super().__init__(min_size, entity_part, priority)
    self.slot_type = 'target'


class RemovalSlot(SourceSlot):
  """Entities to remove from the document."""
  def __init__(self, min_size=1, entity_part='sec', priority='required'):
    super().__init__(min_size, entity_part, priority)
    self.slot_type = 'removal'
    self.purpose = f'target {entity_part} to remove'


# ── Group Slots ───────────────────────────────────────────────────────────

class FreeTextSlot(GroupSlot):
  """Open-ended text input, stored as a list of values."""
  def __init__(self, priority='required'):
    super().__init__(1, priority)
    self.slot_type = 'freetext'
    self.purpose = 'open-ended text input'
    self.verified = False

  def add_one(self, text):
    if text not in self.values:
      self.values.append(text)
    self.check_if_filled()

  def extract(self, labels):
    if 'operations' in labels:
      for operation in labels['operations']:
        self.add_one(operation)


class ChecklistSlot(GroupSlot):
  """Ordered steps where each must be checked off.
  Each step: {'name': <dact>, 'description': <detail>, 'checked': bool}."""
  def __init__(self, steps=None, priority='required'):
    super().__init__(1, priority)
    self.slot_type = 'checklist'
    self.purpose = 'a series of steps to check off'
    self.steps = steps or []
    self.approved = False

  def check_if_filled(self):
    self.filled = self.size > 0 and len(self.steps) >= self.size
    return self.filled

  def is_verified(self):
    return self.filled and all(step['checked'] for step in self.steps)

  def mark_as_complete(self, step_name):
    for i, step in enumerate(self.steps):
      if step['name'] == step_name and not step['checked']:
        self.steps[i]['checked'] = True
        break

  def current_step(self, detail=''):
    for step in self.steps:
      if not step['checked']:
        return step[detail] if detail else step
    return ''


class ProposalSlot(GroupSlot):
  """Selectable options where at least one must be chosen."""
  def __init__(self, options=None, size=2, priority='required'):
    super().__init__(size, priority)
    self.slot_type = 'proposal'
    self.purpose = 'options for the user to select from'
    self.options = options or []

  def check_if_filled(self):
    self.filled = len(self.options) >= self.size and len(self.values) >= 1
    return self.filled

  def add_one(self, option):
    if option in self.options and option not in self.values:
      self.values.append(option)
    self.check_if_filled()


# ── Level Slots ───────────────────────────────────────────────────────────

class LevelSlot(BaseSlot):
  """Numeric threshold slot."""
  def __init__(self, priority='required', threshold=1, epsilon=0):
    super().__init__(priority)
    self.slot_type = 'level'
    self.criteria = 'numeric'
    self.threshold = threshold if epsilon == 0 else threshold - epsilon
    self.level = 0.0
    self.inverse = False

  def check_if_filled(self):
    self.filled = self.level >= self.threshold
    return self.filled

  def reset(self, level=0.0):
    self.level = level
    self.filled = False


class PositionSlot(LevelSlot):
  """Non-negative integer position in a sequence."""
  def __init__(self, priority='required', threshold=1, inverse=False):
    super().__init__(priority, threshold)
    self.slot_type = 'position'
    self.purpose = 'a position in a sequence'
    self.inverse = inverse

  def check_if_filled(self):
    activated = self.level >= 0
    if self.inverse:
      self.filled = activated and self.level < self.threshold
    else:
      self.filled = activated and self.level >= self.threshold
    return self.filled

  def assign_one(self, position):
    try:
      position = int(position)
    except (ValueError, TypeError):
      return
    if position >= 0:
      self.level = position
    self.check_if_filled()


class ProbabilitySlot(LevelSlot):
  """Numeric slot ranging from 0 to 1."""
  def __init__(self, priority='required', threshold=0.95):
    super().__init__(priority, threshold, epsilon=1e-4)
    self.slot_type = 'probability'
    self.purpose = 'a confidence score for auto-execution'

  def assign_one(self, probability):
    if 0 <= probability <= 1:
      self.level = probability
    self.check_if_filled()


class ScoreSlot(LevelSlot):
  """Numeric slot that can hold any value including negatives."""
  def __init__(self, priority='required', threshold=1):
    super().__init__(priority, threshold)
    self.slot_type = 'score'
    self.purpose = 'a score for ranking or filtering'

  def assign_one(self, score):
    self.level = score
    self.check_if_filled()


# ── Single-Value Slots ────────────────────────────────────────────────────

class CategorySlot(BaseSlot):
  """Choose exactly one item from a predefined list."""
  def __init__(self, options, priority='required'):
    super().__init__(priority)
    self.slot_type = 'category'
    self.options = options
    self.purpose = f"choose one from: {options}"
    self.detail = ''

  def assign_multiple(self, options):
    candidates = [o for o in options if o in self.options]
    if len(candidates) == 1:
      self.assign_one(candidates[0])
    elif len(candidates) > 1:
      self.detail = candidates
      self.uncertain = True
    return self.check_if_filled()

  def assign_one(self, option):
    if option in self.options:
      self.value = option
    return self.check_if_filled()


class ExactSlot(BaseSlot):
  """A specific term or phrase, likely user-provided."""
  def __init__(self, priority='required'):
    super().__init__(priority)
    self.slot_type = 'exact'
    self.entity_part = 'snip'
    self.purpose = 'a specific term or phrase'
    self.term = ''

  def add_one(self, term):
    self.value = term
    self.term = term
    self.check_if_filled()


class DictionarySlot(BaseSlot):
  """Key-value pairs for settings or configurations."""
  def __init__(self, keys=None, priority='required'):
    super().__init__(priority)
    self.slot_type = 'dictionary'
    self.value = {key: '' for key in (keys or [])}
    self.purpose = 'a set of key-value pairs'

  def add_one(self, key, val):
    self.value[key] = val
    self.check_if_filled()

  def check_if_filled(self):
    if len(self.value) > 0:
      self.filled = all(
        not (isinstance(v, str) and len(v) == 0) for v in self.value.values()
      )
    return self.filled


class RangeSlot(BaseSlot):
  """Start and stop points for filtering, often a date range."""
  def __init__(self, options=None, priority='optional'):
    super().__init__(priority)
    self.slot_type = 'range'
    self.verified = False
    self.purpose = 'a time or value range'
    self.time_len = 0
    self.unit = ''
    self.range = {'start': None, 'stop': None}
    self.entities = []
    self.recurrence = False

    if not options:
      self.keywords = ['minute', 'hour', 'day', 'week', 'month', 'quarter', 'year']
      self.options = self.keywords + ['all']
    else:
      self.keywords = []
      self.options = options

  def add_one(self, start=None, stop=None, time_len=0, unit='', recurrence=False):
    if start:
      self.range['start'] = start
    if stop:
      self.range['stop'] = stop
    if time_len:
      self.time_len = time_len
    if unit in self.options:
      self.unit = unit
    if recurrence:
      self.recurrence = True
    return self.check_if_filled()

  def check_if_filled(self):
    has_duration = bool(self.unit) and (self.time_len != 0)
    has_range = bool(self.range['start']) and bool(self.range['stop'])
    self.filled = has_duration or has_range
    return self.filled

  def get_details(self):
    return {
      'start': self.range['start'], 'stop': self.range['stop'],
      'time_len': self.time_len, 'unit': self.unit,
      'recurrence': self.recurrence,
    }


# ── Domain-Specific Slots (Hugo) ─────────────────────────────────────────

class ChannelSlot(SourceSlot):
  """Identifies a publishing channel destination."""
  def __init__(self, priority='required'):
    super().__init__(min_size=1, entity_part='chl', priority=priority)
    self.slot_type = 'channel'
    self.purpose = 'a publishing channel'


class ImageSlot(BaseSlot):
  """References images in a post (hero images, diagrams, pictures)."""
  def __init__(self, priority='required'):
    super().__init__(priority)
    self.slot_type = 'image'
    self.purpose = 'a hero image, diagram, or picture'
    self.image_type = ''
    self.position = -1

  def assign_one(self, image_type, src='', alt='', position=-1):
    self.value = src
    self.image_type = image_type
    if position >= 0:
      self.position = position
    self.check_if_filled()
