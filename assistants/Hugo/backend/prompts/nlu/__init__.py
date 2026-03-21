from backend.prompts.nlu import (
    research_slots, draft_slots, revise_slots, publish_slots,
    converse_slots, plan_slots, internal_slots,
)

_MODULES = (research_slots, draft_slots, revise_slots, publish_slots,
            converse_slots, plan_slots, internal_slots)

_EXEMPLAR_REGISTRY = {}
_INSTRUCTION_REGISTRY = {}

def _build():
    for module in _MODULES:
        _EXEMPLAR_REGISTRY.update(module.EXEMPLARS)
        _INSTRUCTION_REGISTRY.update(module.INSTRUCTIONS)

def get_exemplars(flow_name:str) -> str:
    if not _EXEMPLAR_REGISTRY:
        _build()
    return _EXEMPLAR_REGISTRY.get(flow_name, '')

def get_instructions(flow_name:str) -> str:
    if not _INSTRUCTION_REGISTRY:
        _build()
    return _INSTRUCTION_REGISTRY.get(flow_name, '')
