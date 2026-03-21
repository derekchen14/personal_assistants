"""
Flow stack module — public API and flow registry.

This __init__.py does two things:
  1. Re-exports FlowStack from stack.py (the only class consumers need to import)
  2. Defines flow_classes: the registry mapping flow_type names → flow classes

How to use in agent.py:
    from backend.components.flow_stack import FlowStack, flow_classes
    self.flow_stack = FlowStack(config, flow_classes)

Import pattern (wildcard):
  Both slots.py and parents.py are imported with * in flows.py.  Then flows.py
  is imported with * here.  This means all Flow classes are available in this
  module's namespace, and flow_classes just references them by name.

  The wildcard imports work safely because:
    - slots.py and parents.py are self-contained (no cross-imports between them)
    - flows.py imports from both but defines no new slot or parent types
    - None of these modules define __all__, so * imports everything

Domain-specific: replace the example flow entries below with your actual flows,
grouped by intent for readability.
"""

from backend.components.flow_stack.stack import FlowStack
from backend.components.flow_stack.flows import *  # noqa: F401, F403


# ── Flow registry ─────────────────────────────────────────────────────────────
#
# Maps flow_type string → flow class.
# FlowStack.push('chat') looks up 'chat' here to instantiate ChatFlow().
#
# Grouping by intent is a convention, not a requirement.  The dict is flat.

flow_classes: dict[str, type] = {

    # ── Intent1 flows (domain-specific, e.g., Research / Clean / etc.) ────
    'action1': Action1Flow,  # replace with real flow names
    'action2': Action2Flow,

    # ── Intent2 flows ──────────────────────────────────────────────────────
    'action3': Action3Flow,
    'action4': Action4Flow,

    # ── Converse ───────────────────────────────────────────────────────────
    # Universal: every domain must have 'chat'
    'chat': ChatFlow,
    'explain': ExplainFlow,
    'preference': PreferenceFlow,
    'suggest': SuggestFlow,
    'undo': UndoFlow,
    'endorse': EndorseFlow,
    'dismiss': DismissFlow,

    # ── Plan ───────────────────────────────────────────────────────────────
    # Universal: every domain must have 'outline'
    'outline': OutlineFlow,

    # ── Internal ───────────────────────────────────────────────────────────
    # Universal: every domain must have recap, recall, retrieve
    'recap': RecapFlow,
    'recall': RecallFlow,
    'retrieve': RetrieveFlow,
    'search': SearchFlow,
}
