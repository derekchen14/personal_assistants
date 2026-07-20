from schemas.ontology import DACT_ONTOLOGY, FLOW_ONTOLOGY


# Build DAX lookup once at import
_DAX_LOOKUP = {
    cat['dax'].strip('{}').upper(): name
    for name, cat in FLOW_ONTOLOGY.items()
}


def dax2dact(dax: str) -> list[str]:
    hex_to_dact = {v['hex']: k for k, v in DACT_ONTOLOGY.items()}
    raw = dax.strip('{}')
    chars = list(dict.fromkeys(raw))
    return [hex_to_dact[c] for c in chars if c in hex_to_dact]


def dact2dax(dact_names: list[str]) -> str:
    hexes = sorted(DACT_ONTOLOGY[name]['hex'] for name in dact_names)
    code = ''.join(hexes)
    return '{' + code.rjust(3, '0') + '}'


def flow2dax(flow_name: str) -> str | None:
    cat = FLOW_ONTOLOGY.get(flow_name)
    return cat['dax'] if cat else None


def dax2flow(dax: str) -> str | None:
    code = dax.strip('{}').upper()
    return _DAX_LOOKUP.get(code)


# The intent → basic-flow mapping is definitional: flow names vary by domain, the dax codes do not.
_BASIC_DAX = {'Converse': '{000}', 'Research': '{001}', 'Draft': '{002}',
              'Revise': '{003}', 'Publish': '{004}'}


def intent2flow(intent: str) -> str | None:
    """The intent's basic flow (Converse→chat, Research→find, Draft→outline, Revise→write,
    Publish→release in the blog domain). Plan/Clarify have no basic flow and return None."""
    dax = _BASIC_DAX.get(intent)
    return dax2flow(dax) if dax else None


def flows_by_intent(intent: str) -> dict:
    return {
        name: cat for name, cat in FLOW_ONTOLOGY.items()
        if cat.get('intent') == intent
    }


def flow_names_by_intent(intent: str) -> list[str]:
    return sorted(
        name for name, cat in FLOW_ONTOLOGY.items()
        if cat.get('intent') == intent
    )


def all_dax_codes() -> list[str]:
    return sorted(cat['dax'] for cat in FLOW_ONTOLOGY.values())


def edge_flows_for(flow_name: str) -> list[str]:
    cat = FLOW_ONTOLOGY.get(flow_name, {})
    return cat.get('edge_flows', [])


def output_for_flow(flow_name: str) -> str:
    cat = FLOW_ONTOLOGY.get(flow_name, {})
    return cat.get('output', 'list')


def required_slots(flow_name: str) -> list[str]:
    from backend.components.flow_stack import flow_classes
    cls = flow_classes.get(flow_name)
    if not cls:
        return []
    inst = cls()
    return [
        slot_name for slot_name, slot in inst.slots.items()
        if slot.priority == 'required'
    ]
