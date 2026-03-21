"""
Ontology: the shared vocabulary for all personal assistants.

Defines:
  - Intent         — top-level intent categories (universal + domain-specific)
  - FlowLifecycle  — states a flow moves through on the stack
  - AmbiguityLevel — how specific a user's intent is
  - DACT_CATALOG   — all 16 dialogue act token primitives (hex 0–F)
  - FLOW_CATALOG   — one entry per flow: dax, intent, slots, output, edges
  - KEY_ENTITIES   — the domain's primary grounding entities (domain-specific)

DACT primitive system:
  Every flow has a DAX code: a 3-hex-digit string like '{1AD}'.
  Each digit is one primitive from DACT_CATALOG.  The code encodes what the
  flow DOES (verb) and what it ACTS ON (object/modifier).  Primitives compose
  semantically — '{5BD}' means insert(5) + part(B) + multiple(D).  Never assign
  arbitrary codes; derive them from the semantic composition.

Universal DAX codes {000}–{007}:
  Single-dact reserved codes that every domain must define:
    {000} chat      — free conversation
    {001} find      — keyword search
    {002} plan      — outline / orchestrate multi-step
    {003} compose   — write content from scratch
    {004} promote   — distribute or publish
    {005} add       — insert a new item
    {006} transform — major rewrite / restructure
    {007} remove    — delete or discard
"""

from enum import Enum


# ── Intent ────────────────────────────────────────────────────────────────────

class Intent(str, Enum):
    # Universal — every domain must define flows for these three
    PLAN = 'Plan'
    CONVERSE = 'Converse'
    INTERNAL = 'Internal'

    # Domain-specific — uncomment and rename per assistant
    # Example (Hugo):
    # RESEARCH = 'Research'
    # DRAFT = 'Draft'
    # REVISE = 'Revise'
    # PUBLISH = 'Publish'

    # Example (Dana):
    # CLEAN = 'Clean'
    # TRANSFORM = 'Transform'
    # ANALYZE = 'Analyze'
    # REPORT = 'Report'


# ── Flow lifecycle ────────────────────────────────────────────────────────────

class FlowLifecycle(str, Enum):
    # Flow is waiting for an earlier flow to complete first
    PENDING = 'Pending'
    # Flow is the current active flow being executed
    ACTIVE = 'Active'
    # Flow completed successfully; result is stored in flow.result
    COMPLETED = 'Completed'
    # Flow was abandoned (e.g., user changed intent mid-flow)
    INVALID = 'Invalid'


# ── Ambiguity level ───────────────────────────────────────────────────────────

class AmbiguityLevel(str, Enum):
    # Multiple intents possible; need broad disambiguation
    GENERAL = 'general'
    # Intent clear but multiple flows possible within the intent
    PARTIAL = 'partial'
    # Flow identified but a required slot is missing or ambiguous
    SPECIFIC = 'specific'
    # Everything identified; just asking user to confirm before executing
    CONFIRMATION = 'confirmation'


# ── DACT catalog — all 16 primitives ─────────────────────────────────────────
#
# Primitives 0–9 are VERB primitives (what the flow does).
# Primitives A–F are NOUN/MODIFIER primitives (what it acts on or how).
#
# Composition rules:
#   - Position 1 (leftmost): primary verb
#   - Position 2: primary object or secondary verb
#   - Position 3 (rightmost): modifier, sub-entity, or secondary object
#
# Domain-specific note: some primitives (especially A–F) take on domain-
# specific meanings.  For example, B = 'section' in Hugo but B = 'row' in Dana.
# The label here is the generic name; document domain overrides in domain.yaml.

DACT_CATALOG = {
    # ── Verb primitives ─────────────────────────────────────────────────
    '0': {
        'label': 'chat',
        'pos': 'verb',
        'description': 'communicate, converse, or respond without side effects',
    },
    '1': {
        'label': 'retrieve',
        'pos': 'verb',
        'description': 'read, fetch, or load existing content into context',
    },
    '2': {
        'label': 'plan',
        'pos': 'verb',
        'description': 'ideate, outline, strategize, or brainstorm',
    },
    '3': {
        'label': 'analyze',
        'pos': 'verb',
        'description': 'inspect, evaluate, audit, or assess quality',
    },
    '4': {
        'label': 'publish',
        'pos': 'verb',
        'description': 'export, distribute, release, or render output externally',
    },
    '5': {
        'label': 'insert',
        'pos': 'verb',
        'description': 'add a new item, record, or entity',
    },
    '6': {
        'label': 'transform',
        'pos': 'verb',
        'description': 'major modification, restructure, rewrite, or convert',
    },
    '7': {
        'label': 'remove',
        'pos': 'verb',
        'description': 'delete, discard, revoke, or drop',
    },
    '8': {
        'label': 'recall',
        'pos': 'verb',
        'description': 'access memory, preferences, or prior session history',
    },
    '9': {
        'label': 'search',
        'pos': 'verb',
        'description': 'look up, find, or reference external / curated sources',
    },

    # ── Noun / modifier primitives ──────────────────────────────────────
    'A': {
        'label': 'source',
        'pos': 'noun',
        'description': 'primary entity reference — the object being acted on',
        # Domain override examples: post (Hugo), table (Dana)
    },
    'B': {
        'label': 'part',
        'pos': 'noun',
        'description': 'sub-entity or structural portion of a larger whole',
        # Domain override examples: section (Hugo), row (Dana)
    },
    'C': {
        'label': 'channel',
        'pos': 'noun',
        'description': 'destination, platform, or output medium',
        # Renamed from 'platform' to 'channel' in v2; hex C is canonical
    },
    'D': {
        'label': 'content',
        'pos': 'noun',
        'description': 'body text, prose, data payload, or rendered output',
        # Domain override examples: content/body (Hugo), multiple/bulk (Dana)
    },
    'E': {
        'label': 'endorse',
        'pos': 'modifier',
        'description': 'accept, approve, confirm, or agree',
    },
    'F': {
        'label': 'undo',
        'pos': 'modifier',
        'description': 'reverse, cancel, rollback, or negate the primary action',
    },
}


# ── Flow catalog ──────────────────────────────────────────────────────────────
#
# FLOW_CATALOG is the authoritative reference for every flow in the domain.
# The actual flow class lives in backend/components/flow_stack/flows.py.
# This catalog is used for documentation, DAX validation, and flow discovery.
#
# Required fields per entry:
#   dax          — 3-hex DAX code, must be unique across the domain
#   intent       — one of the Intent enum values
#   description  — one-line goal statement (matches flow.goal in flows.py)
#   slots        — dict of slot_name → {type, priority}
#   output       — frame type the flow produces: 'card', 'list', 'grid', 'text'
#   edge_flows   — list of flows that naturally follow this one (for Plan chains)
#   policy_path  — dotted module path to the policy handler

FLOW_CATALOG = {

    # ── Converse ──────────────────────────────────────────────────────────

    'chat': {
        'dax': '{000}',
        'intent': Intent.CONVERSE,
        'description': 'Open-ended conversation with no side effects',
        'slots': {},
        'output': 'text',
        'edge_flows': [],
        'policy_path': 'policies.converse',
    },

    # Domain-specific Converse flows: explain, preference, suggest, undo,
    # endorse, dismiss.  Each gets its own entry here.

    # ── Plan ──────────────────────────────────────────────────────────────
    #
    # Plan/outline is the catch-all orchestrator for multi-step requests.
    # It chains other flows in sequence and is the ONLY Plan flow that every
    # domain must define.  Additional Plan flows are domain-specific.

    'outline': {
        'dax': '{002}',
        'intent': Intent.PLAN,
        'description': 'Orchestrate a multi-step user request across domain intents',
        'slots': {
            'steps': {'type': 'ChecklistSlot', 'priority': 'required'},
        },
        'output': 'list',
        'edge_flows': [],   # outline chains whatever sub-flows the plan needs
        'policy_path': 'policies.plan',
    },

    # ── Internal ──────────────────────────────────────────────────────────
    #
    # Internal flows run asynchronously alongside user-facing flows.
    # recap/recall/retrieve are mandatory; search and calculate are recommended.

    'recap': {
        'dax': '{018}',
        'intent': Intent.INTERNAL,
        'description': 'Read a fact from the session scratchpad (L1 memory)',
        'slots': {
            'key': {'type': 'ExactSlot', 'priority': 'optional'},
        },
        'output': 'text',
        'edge_flows': ['retrieve'],
        'policy_path': 'policies.internal',
    },

    'recall': {
        'dax': '{289}',
        'intent': Intent.INTERNAL,
        'description': 'Look up persistent user preferences (L2 memory)',
        'slots': {
            'key': {'type': 'ExactSlot', 'priority': 'optional'},
        },
        'output': 'text',
        'edge_flows': [],
        'policy_path': 'policies.internal',
    },

    'retrieve': {
        'dax': '{049}',
        'intent': Intent.INTERNAL,
        'description': 'Fetch general business context from Memory Manager (L3)',
        'slots': {
            'topic': {'type': 'ExactSlot', 'priority': 'required'},
            'context': {'type': 'ExactSlot', 'priority': 'optional'},
        },
        'output': 'text',
        'edge_flows': [],
        'policy_path': 'policies.internal',
    },

    # Domain-specific flows go here — one section per intent, matching the
    # Intent enum values defined above.
    #
    # Naming: flow keys must match the flow_type attribute in flows.py.
}


# ── Key entities ──────────────────────────────────────────────────────────────
#
# KEY_ENTITIES lists the primary grounding entities for this domain.
# Each entry becomes a valid entity_part in SourceSlot.add_one().
#
# Hugo example:
#   KEY_ENTITIES = ['post', 'section', 'note', 'channel']
#
# Dana example:
#   KEY_ENTITIES = ['table', 'column', 'row']
#
# Rules:
#   - Use short, lowercase, single-word names
#   - 'version' (ver) is a universal pseudo-entity for diff/undo flows
#   - 'draft' is NOT an entity — it is a status field of a post/document

KEY_ENTITIES = [
    # Domain-specific: replace with your primary grounding entities
    # 'entity_type_1',
    # 'entity_type_2',
    # 'entity_type_3',
]
