from schemas.ontology import DACT_CATALOG, FLOW_CATALOG, Intent


def dax2dact(dax: str) -> list[str]:
    hex_to_dact = {v['hex']: k for k, v in DACT_CATALOG.items()}
    raw = dax.strip('{}')
    chars = list(dict.fromkeys(raw))
    return [hex_to_dact[c] for c in chars if c in hex_to_dact]


def dact2dax(dact_names: list[str]) -> str:
    hexes = sorted(DACT_CATALOG[name]['hex'] for name in dact_names)
    code = ''.join(hexes)
    return '{' + code.rjust(3, '0') + '}'


def flow2dax(flow_name: str) -> str | None:
    flow = FLOW_CATALOG.get(flow_name)
    return flow['dax'] if flow else None


def dax2flow(dax: str) -> str | None:
    for name, flow in FLOW_CATALOG.items():
        if flow['dax'] == dax:
            return name
    return None


def flows_by_intent(intent: Intent) -> dict:
    return {
        name: flow for name, flow in FLOW_CATALOG.items()
        if flow['intent'] == intent
    }


def flow_names_by_intent(intent: Intent) -> list[str]:
    return sorted(
        name for name, flow in FLOW_CATALOG.items()
        if flow['intent'] == intent
    )


def all_dax_codes() -> list[str]:
    return sorted(flow['dax'] for flow in FLOW_CATALOG.values())


def edge_flows_for(flow_name: str) -> list[str]:
    flow = FLOW_CATALOG.get(flow_name)
    return flow['edge_flows'] if flow else []


def required_slots(flow_name: str) -> list[str]:
    flow = FLOW_CATALOG.get(flow_name)
    if not flow:
        return []
    return [
        slot_name for slot_name, slot in flow['slots'].items()
        if slot['priority'] == 'required'
    ]
