"""
Parent flow classes — self-contained, no cross-module imports.

This file defines BaseFlow and all domain parent flows from scratch.
It intentionally does NOT import from slots.py (slots.py is imported by
flows.py, not here) so parents.py can be used in isolation.

Why self-contained:
  If parents.py imported from slots.py and slots.py changed its import paths,
  both files would break.  Keeping them independent means each can be tested,
  read, and understood without loading the other.

BaseFlow:
  The foundation every flow inherits from.  Holds flow identity, slots, tools,
  and lifecycle state.  Key attributes:
    entity_slot   — canonical name for the primary grounding slot ('source')
    status        — FlowLifecycle value, managed by FlowStack
    is_newborn    — True until the first slot-fill attempt; used by PEX

is_filled():
  A flow is "filled" when:
    1. ALL required slots are filled, AND
    2. If any elective slots exist, at least ONE is filled.
  Optional slots never block is_filled().

Domain parents:
  Each intent gets its own parent class (Intent1ParentFlow, etc.).  They all
  currently just set self.parent_type.  Override validate_entity() in a domain
  parent to add intent-specific entity validation (e.g., checking that a post
  exists before accepting it as a SourceSlot value).

InternalParentFlow:
  Sets interjected=True so the flow stack knows this flow runs async (in
  parallel with the user-facing flow) and should not block user turns.
"""


class BaseFlow(object):
    """
    Root of the flow hierarchy.  Never instantiated directly.

    Every flow class in flows.py inherits from a domain parent which inherits
    from BaseFlow.  The flow_type and parent_type strings must match the
    FLOW_CATALOG keys in ontology.py.
    """

    def __init__(self):
        # ── Slot and tool containers ───────────────────────────────────────
        # flows.py fills these in __init__ for each concrete flow class.
        self.slots = {}      # dict[str, BaseSlot]
        self.tools = []      # list[str] — tool names available to this flow

        # ── Lifecycle flags ────────────────────────────────────────────────
        self.completed = False
        self.interjected = False    # True for Internal flows (run async)
        self.is_newborn = True      # True until first slot-fill attempt
        self.is_uncertain = False   # True when intent/entity is ambiguous

        # ── Planning ───────────────────────────────────────────────────────
        self.fall_back = None       # fallback flow if this one fails
        self.stage = ''             # current execution stage name

        # ── Grounding ─────────────────────────────────────────────────────
        # The canonical name for the primary grounding slot.  NEVER rename
        # this to 'post_id', 'dataset', 'table', etc. — always 'source'.
        self.entity_slot = 'source'

        # ── Identity (set by FlowStack.push) ──────────────────────────────
        self.flow_id: str = ''
        self.status: str = ''       # FlowLifecycle value
        self.plan_id: str | None = None
        self.turn_ids: list[str] = []
        self.result: dict | None = None

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def intent(self):
        """Alias for parent_type; used interchangeably in policies."""
        return self.parent_type

    def get(self, key, default=None):
        return getattr(self, key, default)

    def name(self, full=False):
        if full:
            return f'{self.parent_type}({self.flow_type})'
        return self.flow_type

    def __str__(self):
        parts = [f"{self.name(full=True)} >"]
        for slot_name, slot in self.slots.items():
            if slot.criteria == 'multiple':
                parts.append(f"{slot_name}: {slot.values}")
            elif slot.criteria == 'numeric':
                parts.append(f"{slot_name}: {slot.level}")
            elif slot.filled:
                parts.append(f"{slot_name}: {slot.value}")
        return ' '.join(parts)

    # ── Core slot logic ───────────────────────────────────────────────────────

    def is_filled(self):
        """
        True when the flow has enough slot values to execute.

        Logic:
          - All 'required' slots must be filled.
          - If any 'elective' slots exist, at least one must be filled.
          - 'optional' slots never block is_filled().
        """
        for slot in self.slots.values():
            slot.check_if_filled()

        elective = [s for s in self.slots.values() if s.priority == 'elective']
        at_least_one_elective = not elective or any(s.filled for s in elective)
        all_required = all(s.filled for s in self.slots.values() if s.priority == 'required')
        return all_required and at_least_one_elective

    def fill_slots_by_label(self, labels: dict):
        """
        System 1 slot fill — targeted single-slot fill from PEX label extraction.

        labels format: {slot_name: extracted_value}

        Routes entity-slot values through validate_entity() so domain parents
        can override for early validation (e.g., checking that a post exists).
        Returns True if the flow is now fully filled.
        """
        for slot_name, value in labels.items():
            if slot_name not in self.slots or value is None:
                continue
            if slot_name == self.entity_slot:
                entity = value if isinstance(value, dict) else {'id': str(value)}
                self.validate_entity(entity)
            else:
                self.fill_slot_values({slot_name: value})
        return self.is_filled()

    def fill_slot_values(self, values: dict):
        """
        Transfer prediction values onto slot objects.

        Handles the common dispatch cases:
          - list → GroupSlot (source/target/removal) via add_one(**item)
          - dict → DictionarySlot via add_one(key, val)
          - dict → GroupSlot via add_one(**value) with TypeError fallback
          - scalar → assign_one(value) or add_one(value)
        """
        if not values:
            return

        # Common aliases from LLM outputs that differ from slot names
        _ALIASES = {'title': 'target', 'post': 'source', 'post_id': 'source'}

        for slot_name, value in values.items():
            slot = self.slots.get(slot_name)
            if not slot:
                alias = _ALIASES.get(slot_name)
                if alias:
                    slot = self.slots.get(alias)
            if not slot or not value:
                continue

            st = getattr(slot, 'slot_type', '')
            if isinstance(value, list) and st in ('source', 'target', 'removal'):
                for item in value:
                    if isinstance(item, dict):
                        slot.add_one(**item)
                    else:
                        slot.add_one(post=str(item))  # fallback: treat as primary ID
            elif isinstance(value, dict) and st == 'dictionary':
                predefined = set(slot.value.keys()) if isinstance(slot.value, dict) else set()
                if predefined == {'key', 'value'} and not any(k in predefined for k in value):
                    # LLM returned {actual_key: actual_val} instead of {key:..., value:...}
                    for k, v in value.items():
                        slot.add_one(key='key', val=str(k))
                        slot.add_one(key='value', val=str(v))
                        break
                else:
                    for k, v in value.items():
                        slot.add_one(key=str(k), val=str(v))
            elif isinstance(value, dict) and hasattr(slot, 'add_one'):
                try:
                    slot.add_one(**value)
                except TypeError:
                    # Unknown keys — extract primary/secondary if possible
                    primary = value.get('id', value.get('post', str(value)))
                    secondary = value.get('sec', value.get('section', ''))
                    if st in ('source', 'target', 'removal'):
                        slot.add_one(post=str(primary), sec=str(secondary))
                    else:
                        slot.add_one(str(primary))
            elif hasattr(slot, 'assign_one'):
                slot.assign_one(value)
            elif hasattr(slot, 'add_one'):
                if st in ('source', 'target', 'removal'):
                    slot.add_one(post=str(value))
                elif st == 'range' and isinstance(value, str):
                    slot.add_one(start=value)
                else:
                    slot.add_one(value)
            else:
                slot.value = str(value)

    def slot_values_dict(self) -> dict:
        """Read filled slot values as a flat dict (for prompt serialization)."""
        return {
            sn: slot.to_dict() for sn, slot in self.slots.items()
            if slot.filled
               or (slot.criteria == 'multiple' and slot.to_dict())
               or (slot.criteria == 'numeric' and slot.to_dict())
        }

    def to_dict(self) -> dict:
        """Serialize the flow to a dict for logging or plan storage."""
        return {
            'flow_id': self.flow_id, 'flow_name': self.flow_type,
            'dax': self.dax, 'intent': self.parent_type,
            'status': self.status, 'slots': self.slot_values_dict(),
            'plan_id': self.plan_id, 'turn_ids': self.turn_ids,
        }

    # ── Entity helpers ─────────────────────────────────────────────────────────

    def validate_entity(self, entity):
        """
        Add entity to the primary grounding slot.

        Override in domain parents to add validation logic before accepting
        the entity (e.g., verify the post exists in the metadata index).
        """
        if self.entity_slot in self.slots:
            self.slots[self.entity_slot].add_one(**entity)

    def entity_values(self, size=False):
        values = self.slots[self.entity_slot].values
        return len(values) if size else values

    # ── Control flow helpers ───────────────────────────────────────────────────

    def needs_to_think(self):
        """True when the flow is incomplete but not ambiguous (System 2 path)."""
        if self.is_uncertain or self.is_filled():
            return False
        return True

    def match_action(self, action_name):
        return action_name.startswith(self.parent_type.upper())


# ── Internal parent ───────────────────────────────────────────────────────────

class InternalParentFlow(BaseFlow):
    """
    Parent for all Internal-intent flows (recap, recall, retrieve, search, ...).

    interjected=True tells the flow stack that this flow runs asynchronously
    alongside the user-facing flow.  It does NOT block the user from continuing
    their conversation while the internal flow fetches memory context.
    """

    def __init__(self):
        super().__init__()
        self.parent_type = 'Internal'
        self.interjected = True
        self.origin = ''   # which user-facing flow triggered this internal flow


# ── Domain parents ────────────────────────────────────────────────────────────
# One parent per domain intent.  Each sets parent_type and can override
# validate_entity() for intent-specific entity validation.
#
# Domain-specific: replace Intent1/Intent2/... with your actual intent names.
# Example (Hugo): Research, Draft, Revise, Publish, Converse, Plan
# Example (Dana): Clean, Transform, Analyze, Report, Converse, Plan

class Intent1ParentFlow(BaseFlow):
    """
    Parent for Intent1 flows.

    Override validate_entity() here if this intent requires entity validation
    (e.g., checking that a post exists in the metadata index before accepting
    it as a SourceSlot value).
    """

    def __init__(self):
        super().__init__()
        self.parent_type = 'Intent1'   # Domain-specific: rename


class Intent2ParentFlow(BaseFlow):
    def __init__(self):
        super().__init__()
        self.parent_type = 'Intent2'   # Domain-specific: rename


class Intent3ParentFlow(BaseFlow):
    def __init__(self):
        super().__init__()
        self.parent_type = 'Intent3'   # Domain-specific: rename


class ConverseParentFlow(BaseFlow):
    """Parent for all Converse-intent flows.  Universal — keep as-is."""

    def __init__(self):
        super().__init__()
        self.parent_type = 'Converse'


class PlanParentFlow(BaseFlow):
    """Parent for all Plan-intent flows.  Universal — keep as-is."""

    def __init__(self):
        super().__init__()
        self.parent_type = 'Plan'
