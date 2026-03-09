"""
Slot types for Dana (Data Analysis).

12 universal slots + 4 domain-specific.
Grounding entity_parts: table, column, row.

Hierarchy:
  BaseSlot
  ├── GroupSlot            (multiple values in a list)
  │   ├── SourceSlot       (existing entities: table, column, row)
  │   │   ├── TargetSlot   (new entities being created)
  │   │   └── RemovalSlot  (entities being removed)
  │   ├── FreeTextSlot     (open-ended text values)
  │   ├── ChecklistSlot    (ordered steps to check off)
  │   └── ProposalSlot     (selectable options)
  ├── LevelSlot            (numeric threshold)
  │   ├── PositionSlot     (non-negative integer)
  │   ├── ProbabilitySlot  (0-1 range)                    [domain-specific]
  │   └── ScoreSlot        (any numeric value)             [domain-specific]
  ├── CategorySlot         (one from predefined list, 8 max)
  ├── ExactSlot            (specific term or phrase)
  ├── DictionarySlot       (key-value pairs)
  ├── RangeSlot            (time or value range)
  ├── ChartSlot            (chart reference)               [domain-specific]
  └── FunctionSlot         (code expression)               [domain-specific]
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
    if hasattr(self, 'tab_cols'):
      self.tab_cols = []
    if hasattr(self, 'steps'):
      self.steps = []
    if hasattr(self, 'options'):
      self.options = []


# ── Grounding Entity ──────────────────────────────────

class SourceSlot(GroupSlot):
  """References existing entities. Each entity is {tab, col, row, ver, rel}."""
  def __init__(self, min_size=1, entity_part='', priority='required'):
    super().__init__(min_size, priority)
    self.slot_type = 'source'
    self.entity_part = entity_part
    self.tab_cols = []
    self.active_tab = ''
    if entity_part:
      self.purpose = f"at least {min_size} {entity_part}" if min_size == 1 else f"at least {min_size} {entity_part}s"
    else:
      self.purpose = f"at least {min_size} grounding reference" if min_size == 1 else f"at least {min_size} grounding references"

  def add_one(self, tab, col, row=-1, ver=False, rel=''):
    tab_col = f"{tab}-{col}"
    alt_col = f"{self.active_tab}-{col}"
    if tab_col in self.tab_cols:
      tc_index = self.tab_cols.index(tab_col)
      self.values[tc_index]['row'] = row
      self.values[tc_index]['ver'] = ver
    elif alt_col in self.tab_cols:
      pass  # earlier table is the active one
    else:
      entity = {'tab': tab, 'col': col, 'row': row, 'ver': ver, 'rel': rel}
      self.values.append(entity)
      self.tab_cols.append(tab_col)
    self.check_if_filled()

  def replace_entity(self, old_tab, old_col, new_tab='', new_col=''):
    for i, entity in enumerate(self.values):
      if entity['tab'] == old_tab and entity['col'] == old_col:
        if new_tab:
          self.values[i]['tab'] = new_tab
        if new_col:
          self.values[i]['col'] = new_col
    self.tab_cols = [f"{e['tab']}-{e['col']}" for e in self.values]

  def drop_unverified(self, conditional=False):
    verified = [e for e in self.values if e['ver']]
    if conditional:
      if len(verified) > 0:
        self.values = verified
    else:
      self.values = verified
    self.tab_cols = [f"{e['tab']}-{e['col']}" for e in self.values]
    self.check_if_filled()

  def drop_ambiguous(self):
    self.values = [e for e in self.values if e['rel'] != 'ambiguous']
    self.tab_cols = [f"{e['tab']}-{e['col']}" for e in self.values]
    self.check_if_filled()

  def is_verified(self):
    return len([e for e in self.values if e['ver']]) >= self.size

  def table_name(self):
    return self.values[0]['tab'] if self.values else 'N/A'


class TargetSlot(SourceSlot):
  """New entities being created (new column name, new table)."""
  def __init__(self, min_size, entity_part, priority='required'):
    super().__init__(min_size, entity_part, priority)
    self.slot_type = 'target'


class RemovalSlot(SourceSlot):
  """Entities to remove from the data."""
  def __init__(self, removal_type, priority='required'):
    super().__init__(1, removal_type, priority)
    self.slot_type = 'removal'
    self.rtype = removal_type
    self.purpose = f"target {removal_type} to remove"


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
  def __init__(self, options=None, priority='required'):
    super().__init__(1, priority)
    self.slot_type = 'proposal'
    self.purpose = 'options for the user to select from'
    self.options = options or []

  def check_if_filled(self):
    self.filled = len(self.options) >= 2 and len(self.values) >= self.size
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


# ── Domain-Specific Slots (Dana) ─────────────────────────────────────────

class ChartSlot(BaseSlot):
  """Identifies a specific chart in the display."""
  def __init__(self, priority='required'):
    super().__init__(priority)
    self.slot_type = 'chart'
    self.purpose = 'a specific chart to interact with'
    self.chart_name = ''

  def assign_id(self, location, height=0, width=0, chart_name=''):
    if location in ('dashboard', 'panel'):
      self.value = f"{location}-{height}-{width}"
    if chart_name:
      self.chart_name = chart_name
    self.check_if_filled()


class FunctionSlot(BaseSlot):
  """Contains a code expression, formula, or calculation."""
  def __init__(self, priority='required'):
    super().__init__(priority)
    self.slot_type = 'function'
    self.purpose = 'a code expression or formula'
    self.str_rep = ''
    self.fuzzy = False

  def assign_one(self, function, str_rep='', fuzzy=False):
    self.value = function
    if str_rep:
      self.str_rep = str_rep
    self.fuzzy = fuzzy
    self.check_if_filled()

  def reset(self):
    self.value = None
    self.filled = False

  def check_if_filled(self):
    if self.value is None:
      self.filled = False
    elif callable(self.value):
      self.filled = True
    elif isinstance(self.value, str):
      self.filled = len(self.value) > 0
    else:
      self.filled = False
    return self.filled
