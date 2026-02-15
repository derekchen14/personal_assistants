"""Domain helpers for the Onboarding domain (Kalli).

Utilities for converting between dact names, dax codes, and flow names.
"""

from schemas.ontology import DACT_CATALOG, FLOW_CATALOG, Intent


def dax2dact(dax: str) -> list[str]:
    """Convert a dax code like '{03A}' to its component dact names.

    Strips braces and leading zeros, maps each hex char to a dact name.

    >>> dax2dact('{03A}')
    ['chat', 'iterate', 'config']
    >>> dax2dact('{000}')
    ['chat']
    """
    hex_to_dact = {v['hex']: k for k, v in DACT_CATALOG.items()}
    raw = dax.strip('{}')
    # Deduplicate (e.g., {000} → just '0')
    chars = list(dict.fromkeys(raw))
    return [hex_to_dact[c] for c in chars if c in hex_to_dact]


def dact2dax(dact_names: list[str]) -> str:
    """Convert a list of dact names to a sorted dax code.

    >>> dact2dax(['iterate', 'config'])
    '{03A}'
    >>> dact2dax(['chat'])
    '{000}'
    """
    hexes = sorted(DACT_CATALOG[name]['hex'] for name in dact_names)
    code = ''.join(hexes)
    return '{' + code.rjust(3, '0') + '}'


def flow2dax(flow_name: str) -> str | None:
    """Look up the dax code for a flow name.

    >>> flow2dax('scope')
    '{02A}'
    """
    flow = FLOW_CATALOG.get(flow_name)
    return flow['dax'] if flow else None


def dax2flow(dax: str) -> str | None:
    """Look up the flow name for a dax code.

    >>> dax2flow('{02A}')
    'scope'
    """
    for name, flow in FLOW_CATALOG.items():
        if flow['dax'] == dax:
            return name
    return None


def flows_by_intent(intent: Intent) -> dict:
    """Return all flows belonging to a given intent.

    >>> len(flows_by_intent(Intent.EXPLORE))
    8
    """
    return {
        name: flow for name, flow in FLOW_CATALOG.items()
        if flow['intent'] == intent
    }


def flow_names_by_intent(intent: Intent) -> list[str]:
    """Return sorted flow names for an intent.

    >>> flow_names_by_intent(Intent.CONVERSE)
    ['chat', 'dismiss', 'endorse', 'feedback', 'next_step', 'preference', 'style']
    """
    return sorted(
        name for name, flow in FLOW_CATALOG.items()
        if flow['intent'] == intent
    )


def all_dax_codes() -> list[str]:
    """Return all dax codes sorted."""
    return sorted(flow['dax'] for flow in FLOW_CATALOG.values())


def edge_flows_for(flow_name: str) -> list[str]:
    """Return edge flow names for a given flow.

    >>> edge_flows_for('scope')
    ['persona', 'entity']
    """
    flow = FLOW_CATALOG.get(flow_name)
    return flow['edge_flows'] if flow else []


def required_slots(flow_name: str) -> list[str]:
    """Return names of required slots for a flow.

    >>> required_slots('scope')
    ['name', 'task']
    """
    flow = FLOW_CATALOG.get(flow_name)
    if not flow:
        return []
    return [
        slot_name for slot_name, slot in flow['slots'].items()
        if slot['priority'] == 'required'
    ]
