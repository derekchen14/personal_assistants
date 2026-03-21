"""
Concrete flow implementations — one example per intent.

Each flow class:
  - Inherits from its domain parent (Intent1ParentFlow, etc.)
  - Sets flow_type (must match the key in flow_classes in __init__.py)
  - Sets dax (3-hex DAX code, unique per domain)
  - Sets goal (one-line description matching FLOW_CATALOG entry)
  - Configures self.slots (zero or more slot instances)
  - Lists self.tools (tool names available for policy execution)

Wildcard imports:
  Both slots.py and parents.py are imported with * so all slot types and all
  parent classes are available without explicit imports.

Slot selection guide:
  - No required slots needed? → use ChatFlow as a model (empty slots dict)
  - Single entity reference → SourceSlot(1) as 'source'
  - Creating something new → TargetSlot for the new item
  - Removing something → RemovalSlot for what's being removed
  - Open free-form input → FreeTextSlot (multi-value) or ExactSlot (single)
  - Ordered steps → ChecklistSlot
  - Multiple user choices → ProposalSlot
  - One from a fixed list → CategorySlot (max 8 options)
  - Numeric threshold → LevelSlot / PositionSlot / ScoreSlot
  - Date/value range → RangeSlot

DAX code composition guide (from ontology.py):
  Position 1: primary verb (0=chat, 1=retrieve, 2=plan, 3=analyze, ...)
  Position 2: primary object or secondary verb
  Position 3: modifier, sub-entity, or secondary object
  Example: {1AD} = retrieve(1) + source(A) + content(D) = "read full content"

Domain-specific: replace the example flows below with your actual domain flows.
"""

from backend.components.flow_stack.slots import *    # noqa: F401, F403
from backend.components.flow_stack.parents import *  # noqa: F401, F403


# ── Intent1 flows (domain-specific example) ───────────────────────────────────

class Action1Flow(Intent1ParentFlow):
    """
    Example: a flow that retrieves an existing entity.
    Replace with your domain's first action in this intent.
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'action1'
        self.dax = '{1AD}'  # retrieve + source + content
        self.goal = 'retrieve and display an existing item in full'
        self.slots = {
            # SourceSlot is the canonical grounding slot name — always 'source'
            'source': SourceSlot(1),
        }
        self.tools = ['read_item']


class Action2Flow(Intent1ParentFlow):
    """
    Example: a flow that searches for items.
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'action2'
        self.dax = '{001}'  # find (universal single-dact)
        self.goal = 'search items by keyword or topic'
        self.slots = {
            'query': ExactSlot(),
            'count': LevelSlot(priority='optional', threshold=1),
        }
        self.tools = ['search_items']


# ── Intent2 flows ─────────────────────────────────────────────────────────────

class Action3Flow(Intent2ParentFlow):
    """
    Example: a flow that creates a new item.
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'action3'
        self.dax = '{003}'  # compose (universal: write from scratch)
        self.goal = 'create a new item from scratch'
        self.slots = {
            'title': ExactSlot(),
            'type': CategorySlot(['draft', 'note'], priority='optional'),
        }
        self.tools = ['create_item']


class Action4Flow(Intent2ParentFlow):
    """
    Example: a flow that modifies an existing item.
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'action4'
        self.dax = '{006}'  # transform (universal: major modification)
        self.goal = 'make a major revision to an existing item'
        self.slots = {
            'source': SourceSlot(1),
            'instructions': FreeTextSlot(priority='elective'),
            'steps': ChecklistSlot(priority='elective'),
        }
        self.tools = ['read_item', 'update_item']


# ── Converse ──────────────────────────────────────────────────────────────────

class ChatFlow(ConverseParentFlow):
    """
    Universal: open-ended conversation with no side effects.
    Every domain must have a ChatFlow mapped to '{000}'.
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'chat'
        self.dax = '{000}'
        self.goal = 'open-ended conversation'
        self.slots = {}
        self.tools = []


class ExplainFlow(ConverseParentFlow):
    """Explain what the assistant did or plans to do."""

    def __init__(self):
        super().__init__()
        self.flow_type = 'explain'
        self.dax = '{009}'  # chat(0) + search(9) = explain by looking up context
        self.goal = "explain the assistant's last action or upcoming plan"
        self.slots = {
            'turn_id': PositionSlot(priority='elective'),
            'source': SourceSlot(1, priority='elective'),
        }
        self.tools = ['explain_action']


class PreferenceFlow(ConverseParentFlow):
    """Set a persistent user preference."""

    def __init__(self):
        super().__init__()
        self.flow_type = 'preference'
        self.dax = '{08A}'  # chat(0) + recall(8) + source(A) = store user pref
        self.goal = 'set a persistent user preference'
        self.slots = {
            'setting': DictionarySlot(['key', 'value']),
        }
        self.tools = []


class SuggestFlow(ConverseParentFlow):
    """Suggest a next step based on current context."""

    def __init__(self):
        super().__init__()
        self.flow_type = 'suggest'
        self.dax = '{29B}'  # plan(2) + search(9) + part(B) = suggest next piece
        self.goal = 'suggest a next step based on current context'
        self.slots = {}
        self.tools = []


class UndoFlow(ConverseParentFlow):
    """Reverse the most recent action."""

    def __init__(self):
        super().__init__()
        self.flow_type = 'undo'
        self.dax = '{08F}'  # chat(0) + recall(8) + undo(F) = recall + reverse
        self.goal = 'reverse the most recent action'
        self.slots = {
            'turn': LevelSlot(priority='elective', threshold=1),
            'action': ExactSlot(priority='elective'),
        }
        self.tools = []


class EndorseFlow(ConverseParentFlow):
    """Accept the assistant's proactive suggestion."""

    def __init__(self):
        super().__init__()
        self.flow_type = 'endorse'
        self.dax = '{08E}'  # chat(0) + recall(8) + endorse(E) = accept suggestion
        self.goal = "accept the assistant's proactive suggestion"
        self.slots = {
            'action': ExactSlot(),
        }
        self.tools = []


class DismissFlow(ConverseParentFlow):
    """Decline the assistant's proactive suggestion."""

    def __init__(self):
        super().__init__()
        self.flow_type = 'dismiss'
        self.dax = '{09F}'  # chat(0) + search(9) + undo(F) = look up + reject
        self.goal = "decline the assistant's proactive suggestion"
        self.slots = {}
        self.tools = []


# ── Plan ──────────────────────────────────────────────────────────────────────

class OutlineFlow(PlanParentFlow):
    """
    Universal: orchestrate a multi-step user request across domain intents.
    Every domain must have an OutlineFlow mapped to '{002}'.

    outline is the catch-all Plan flow.  It handles numbered lists and complex
    instructions by building a ChecklistSlot of sub-flows to execute in order.
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'outline'
        self.dax = '{002}'  # plan (universal)
        self.goal = 'orchestrate a multi-step user request across intents'
        self.slots = {
            'steps': ChecklistSlot(priority='required'),
        }
        self.tools = []


# ── Internal ──────────────────────────────────────────────────────────────────
# Universal: every domain must have recap, recall, and retrieve.
# search is strongly recommended.

class RecapFlow(InternalParentFlow):
    """
    L1 memory: read a fact from the session scratchpad.
    The scratchpad is reset when the session ends.
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'recap'
        self.dax = '{018}'  # chat(0) + insert(5→1) + recall(8) = session memory
        self.goal = 'read a fact from the session scratchpad (L1 memory)'
        self.slots = {
            'key': ExactSlot(priority='optional'),
        }
        self.tools = []


class RecallFlow(InternalParentFlow):
    """
    L2 memory: look up persistent user preferences.
    Preferences persist across sessions.
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'recall'
        self.dax = '{289}'  # plan(2) + recall(8) + search(9) = persistent lookup
        self.goal = 'look up persistent user preferences (L2 memory)'
        self.slots = {
            'key': ExactSlot(priority='optional'),
        }
        self.tools = []


class RetrieveFlow(InternalParentFlow):
    """
    L3 memory: fetch general business context from Memory Manager.
    Context is unvetted (from any source, not curated).
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'retrieve'
        self.dax = '{049}'  # chat(0) + insert(4→0) + search(9) = fetch context
        self.goal = 'fetch general business context from Memory Manager (L3 memory)'
        self.slots = {
            'topic': ExactSlot(),
            'context': ExactSlot(priority='optional'),
        }
        self.tools = []


class SearchFlow(InternalParentFlow):
    """
    Search vetted FAQs and curated reference content.

    search vs retrieve:
      search → vetted/curated content (like lookup in structured data)
      retrieve → unvetted context from any source (like raw SQL query)
    """

    def __init__(self):
        super().__init__()
        self.flow_type = 'search'
        self.dax = '{189}'  # retrieve(1) + recall(8) + search(9) = curated lookup
        self.goal = 'look up vetted FAQs and curated reference content'
        self.slots = {
            'query': ExactSlot(),
        }
        self.tools = ['search_reference']
