from enum import Enum


class Intent(str, Enum):
    PLAN = 'Plan'
    CONVERSE = 'Converse'
    INTERNAL = 'Internal'
    # Domain-specific: add intents per assistant
    # RESEARCH = 'Research'
    # DRAFT = 'Draft'


class FlowLifecycle(str, Enum):
    PENDING = 'Pending'
    ACTIVE = 'Active'
    COMPLETED = 'Completed'
    INVALID = 'Invalid'


class AmbiguityLevel(str, Enum):
    GENERAL = 'general'
    PARTIAL = 'partial'
    SPECIFIC = 'specific'
    CONFIRMATION = 'confirmation'


DACT_CATALOG = {
    'chat':     {'hex': '0', 'pos': 'noun'},
    # Domain-specific: add dialogue act tokens per assistant
}

FLOW_CATALOG = {

    # ── Converse ──────────────────────────────────────────────────

    'chat': {
        'dax': '{000}',
        'intent': Intent.CONVERSE,
        'description': 'Open-ended conversation',
        'slots': {
            'topic': {'type': 'FreeTextSlot', 'priority': 'optional'},
        },
        'output': 'card',
        'edge_flows': [],
        'policy_path': 'policies.converse',
    },

    # Domain-specific: add flows per assistant
}

KEY_ENTITIES = []
