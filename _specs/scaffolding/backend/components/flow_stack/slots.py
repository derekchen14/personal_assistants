"""
Slot type hierarchy — self-contained, no cross-module imports.

This file defines ALL slot types from scratch.  It intentionally does NOT
import from parents.py or flows.py so it can be used in isolation (e.g., in
tests or in a standalone slot extraction tool).

12 universal slots (shared across all domains):
  BaseSlot
  ├── GroupSlot            — multiple values in a list
  │   ├── SourceSlot       — existing entities (primary grounding slot)
  │   │   ├── TargetSlot   — new entities being created
  │   │   └── RemovalSlot  — entities being removed
  │   ├── FreeTextSlot     — open-ended text, multi-value accumulation
  │   ├── ChecklistSlot    — ordered steps to check off
  │   └── ProposalSlot     — selectable options (at least one must be chosen)
  ├── LevelSlot            — numeric threshold
  │   ├── PositionSlot     — non-negative integer position
  │   ├── ProbabilitySlot  — 0–1 range                    [domain-specific]
  │   └── ScoreSlot        — any numeric value             [domain-specific]
  ├── CategorySlot         — one item from a predefined list (max 8)
  ├── ExactSlot            — a specific term or phrase
  ├── DictionarySlot       — key-value pairs
  └── RangeSlot            — time or value range

4 domain-specific slots (2 below as commented examples):
  ChartSlot / FunctionSlot (Dana)
  ChannelSlot / ImageSlot  (Hugo)

Key design decisions:
  - FreeTextSlot is for multi-value accumulation only.
    Single phrases or terms → use ExactSlot.
  - SourceSlot entity_part is OPTIONAL.  Pass '' to allow any entity type.
  - SourceSlot.entity_slot = 'source' is canonical; never name it 'post_id'.
  - CategorySlot: max 8 options, mutually exclusive.
    If you need an "other" option, pair it with an ExactSlot (priority='elective').
  - ProbabilitySlot and ScoreSlot are domain-specific but common enough to
    include here; they inherit from LevelSlot.
"""


# ── Base ──────────────────────────────────────────────────────────────────────

class BaseSlot(object):
    """
    Root of the slot hierarchy.

    Attributes:
      filled     — True when the slot has a valid value
      uncertain  — True when the value exists but is ambiguous
      criteria   — 'single' | 'multiple' | 'numeric' — drives __str__ and to_dict
      priority   — 'required' | 'optional' | 'elective'
                   required: must be filled before the flow is_filled()
                   optional: nice to have; doesn't block is_filled()
                   elective: at least ONE elective slot must be filled
      value      — the slot's current value (string for most single-value slots)
    """

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


# ── Group slots ───────────────────────────────────────────────────────────────

class GroupSlot(BaseSlot):
    """
    Slot values are a list of items rather than a single string.

    min_size: how many items are needed for the slot to be considered filled.
    Most GroupSlots require at least 1 item; CompareFlow's SourceSlot needs 2.
    """

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
        # Reset any sub-lists that specific GroupSlot subclasses may add
        if hasattr(self, '_keys'):
            self._keys = []
        if hasattr(self, 'steps'):
            self.steps = []
        if hasattr(self, 'options'):
            self.options = []


# ── Grounding entity slot ─────────────────────────────────────────────────────

class SourceSlot(GroupSlot):
    """
    References existing entities (primary grounding slot for most flows).

    entity_part: which field on the entity to expect (e.g., 'post', 'section').
      Pass '' to accept any entity part.
      Pass a specific string to guide extraction ('post', 'section', etc.).

    Entity dict shape is domain-specific.  Hugo uses:
      {'post': str, 'sec': str, 'note': str, 'chl': str, 'ver': bool}
    Dana uses:
      {'tab': str, 'col': str, 'row': str, 'ver': bool}

    Canonical name: every flow's primary grounding slot MUST be named 'source'
    (not 'post_id', 'dataset', 'table', etc.).  BaseFlow.entity_slot = 'source'.

    One SourceSlot per flow.  If a flow needs a FreeTextSlot AND has a source
    slot, name the FreeText something else (e.g., 'context', 'feedback').
    """

    def __init__(self, min_size=1, entity_part='', priority='required'):
        super().__init__(min_size, priority)
        self.slot_type = 'source'
        self.entity_part = entity_part
        self._keys = []     # deduplication keys: f"{primary_id}-{secondary_id}"
        self.active_entity = ''  # set by agent when user has an active context
        if entity_part:
            self.purpose = (
                f"at least {min_size} {entity_part}" if min_size == 1
                else f"at least {min_size} {entity_part}s"
            )
        else:
            self.purpose = (
                f"at least {min_size} grounding reference" if min_size == 1
                else f"at least {min_size} grounding references"
            )

    def add_one(self, **kwargs):
        """
        Add one entity reference.  Domain-specific: add the entity fields that
        match your KEY_ENTITIES (e.g., post=, sec=, note= for Hugo).

        The first positional argument is the primary entity ID.
        Example for Hugo: slot.add_one(post='my-post', sec='intro', ver=False)
        """
        # Build a deduplication key from the first two entity fields
        values = list(kwargs.values())
        primary = str(values[0]) if values else ''
        secondary = str(values[1]) if len(values) > 1 else ''
        key = f"{primary}-{secondary}"
        alt_key = f"{self.active_entity}-{secondary}"

        if key in self._keys:
            # Already present — update mutable fields (e.g., ver)
            idx = self._keys.index(key)
            for k, v in kwargs.items():
                self.values[idx][k] = v
        elif alt_key in self._keys:
            pass  # active entity takes precedence; skip the new reference
        else:
            entity = dict(kwargs)
            self.values.append(entity)
            self._keys.append(key)
        self.check_if_filled()

    def _rebuild_keys(self):
        self._keys = [
            f"{list(e.values())[0]}-{list(e.values())[1] if len(e) > 1 else ''}"
            for e in self.values
        ]

    def drop_unverified(self, conditional=False):
        """Remove entities where the verification flag (ver) is False."""
        verified = [e for e in self.values if e.get('ver')]
        if not conditional or verified:
            self.values = verified
        self._rebuild_keys()
        self.check_if_filled()

    def is_verified(self):
        return len([e for e in self.values if e.get('ver')]) >= self.size

    def primary_name(self):
        """Return the primary entity ID of the first reference, or 'N/A'."""
        if self.values:
            return list(self.values[0].values())[0]
        return 'N/A'


class TargetSlot(SourceSlot):
    """
    New entities being created (e.g., new post title, new section name).

    Use for flows that CREATE something new rather than referencing existing.
    Example: AddFlow creates a new section, so it uses TargetSlot(1, 'section').
    """

    def __init__(self, min_size, entity_part, priority='required'):
        super().__init__(min_size, entity_part, priority)
        self.slot_type = 'target'


class RemovalSlot(SourceSlot):
    """
    Entities to remove (e.g., a section being deleted from a post).

    rtype: the type of thing being removed, for prompt clarity.
    """

    def __init__(self, removal_type, priority='required'):
        super().__init__(1, removal_type, priority)
        self.slot_type = 'removal'
        self.rtype = removal_type
        self.purpose = f"target {removal_type} to remove"


class FreeTextSlot(GroupSlot):
    """
    Open-ended text input, stored as a list of accumulated values.

    Use for multi-value accumulation (e.g., feedback across multiple turns,
    a growing list of instructions).

    IMPORTANT: Do NOT use FreeTextSlot for single phrases or terms.
    For a single user-provided phrase, use ExactSlot instead.  FreeTextSlot's
    list semantics make sense only when values accumulate across turns.
    """

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
        """Pull 'operations' list from NLU label dict, if present."""
        if 'operations' in labels:
            for op in labels['operations']:
                self.add_one(op)


class ChecklistSlot(GroupSlot):
    """
    Ordered steps where each must be checked off before the flow is done.
    Each step: {'name': <dact_label>, 'description': <detail>, 'checked': bool}

    Used by Plan flows to track multi-step execution progress.
    """

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
        """Return the first unchecked step, or '' if all done."""
        for step in self.steps:
            if not step['checked']:
                return step[detail] if detail else step
        return ''


class ProposalSlot(GroupSlot):
    """
    Selectable options where the user must pick at least one.
    The 'options' list is populated by the agent; 'values' holds chosen ones.
    """

    def __init__(self, options=None, priority='required'):
        super().__init__(1, priority)
        self.slot_type = 'proposal'
        self.purpose = 'options for the user to select from'
        self.options = options or []

    def check_if_filled(self):
        # Needs at least 2 options to be a real proposal, and at least 1 chosen
        self.filled = len(self.options) >= 2 and len(self.values) >= self.size
        return self.filled

    def add_one(self, option):
        if option in self.options and option not in self.values:
            self.values.append(option)
        self.check_if_filled()


# ── Level slots ───────────────────────────────────────────────────────────────

class LevelSlot(BaseSlot):
    """
    Numeric threshold slot.

    threshold: the minimum value for the slot to be considered filled.
    epsilon: a small buffer subtracted from threshold (for float comparisons).
    inverse: if True, filled when level < threshold (e.g., PositionSlot(inverse=True)).
    """

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
    """
    Non-negative integer position in a sequence (0-indexed is valid).

    inverse=True: filled when level < threshold (e.g., "first N items").
    """

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
    """
    Confidence score, 0–1.  Used for auto-execution gating.

    Domain-specific, but common enough to include in every domain.
    threshold defaults to 0.95 (very high confidence required).
    """

    def __init__(self, priority='required', threshold=0.95):
        super().__init__(priority, threshold, epsilon=1e-4)
        self.slot_type = 'probability'
        self.purpose = 'a confidence score for auto-execution'

    def assign_one(self, probability):
        if 0 <= probability <= 1:
            self.level = probability
        self.check_if_filled()


class ScoreSlot(LevelSlot):
    """
    A numeric score that can be any value including negatives.

    Use for ranking, filtering by score, or any numeric measurement that
    isn't a position or probability.
    """

    def __init__(self, priority='required', threshold=1):
        super().__init__(priority, threshold)
        self.slot_type = 'score'
        self.purpose = 'a score for ranking or filtering'

    def assign_one(self, score):
        self.level = score
        self.check_if_filled()


# ── Single-value slots ────────────────────────────────────────────────────────

class CategorySlot(BaseSlot):
    """
    Choose exactly one item from a predefined list.

    options: max 8 items (more than 8 = use a different slot type).
    Mutually exclusive — only one option can be held at a time.

    When paired with an ExactSlot (priority='elective'), it enables an "other"
    option.  Example: ToneFlow has CategorySlot(['formal', 'casual', ...]) +
    ExactSlot(priority='elective') for custom tones.
    """

    def __init__(self, options, priority='required'):
        super().__init__(priority)
        self.slot_type = 'category'
        self.options = options
        self.purpose = f"choose one from: {options}"
        self.detail = ''  # holds ambiguous candidates when uncertain

    def assign_one(self, option):
        if option in self.options:
            self.value = option
        return self.check_if_filled()

    def assign_multiple(self, options):
        """Pick from a list; set uncertain=True if more than one matches."""
        candidates = [o for o in options if o in self.options]
        if len(candidates) == 1:
            self.assign_one(candidates[0])
        elif len(candidates) > 1:
            self.detail = candidates
            self.uncertain = True
        return self.check_if_filled()


class ExactSlot(BaseSlot):
    """
    A specific term or phrase, typically provided verbatim by the user.

    Use when the value is a single string that doesn't fit into a predefined
    category list and doesn't need to accumulate across turns.

    Examples: a search query, a custom tone, a post title, a topic name.
    """

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
    """
    Key-value pairs for structured settings or configurations.

    keys: predefined keys that must all be filled.
    If keys=['key', 'value'], the LLM fills {key: actual_key, value: actual_val}.
    This is the canonical pattern for storing user preferences.
    """

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
            # All values must be non-empty strings
            self.filled = all(
                not (isinstance(v, str) and len(v) == 0) for v in self.value.values()
            )
        return self.filled


class RangeSlot(BaseSlot):
    """
    Start and stop points for filtering, often a date range.

    Two fill modes:
      duration: unit ('week', 'month', ...) + time_len (e.g., 2 weeks)
      range:    explicit start + stop timestamps

    options: if provided, restricts valid unit values.
    If not provided, uses a default set of time keywords + 'all'.
    """

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


# ── Domain-specific slots ─────────────────────────────────────────────────────
# Replace with your domain's unique slot types.
# Two examples from Hugo and Dana are shown below.

# Hugo: ChannelSlot — identifies a publishing destination
#
# class ChannelSlot(BaseSlot):
#     """Publishing channel (blog, LinkedIn, Twitter, etc.)."""
#     def __init__(self, priority='required'):
#         super().__init__(priority)
#         self.slot_type = 'channel'
#         self.purpose = 'a publishing channel'
#         self.channel_name = ''
#         self.config = {}
#
#     def assign_one(self, channel, config=None):
#         self.value = channel
#         self.channel_name = channel
#         if config:
#             self.config = config
#         self.check_if_filled()


# Dana: ChartSlot — identifies a visualization type
#
# class ChartSlot(BaseSlot):
#     """Chart type for data visualizations."""
#     def __init__(self, priority='required'):
#         super().__init__(priority)
#         self.slot_type = 'chart'
#         self.purpose = 'a chart or visualization type'
#         self.chart_type = ''
#         self.config = {}
#
#     def assign_one(self, chart_type, config=None):
#         self.value = chart_type
#         self.chart_type = chart_type
#         if config:
#             self.config = config
#         self.check_if_filled()
