SLOT_TYPES = {
    'FreeTextSlot': 'Any text input from the user.',
    'CategorySlot': 'One of a predefined set of values.',
    'SectionSlot': (
        'A config section name. Valid values: scope, persona, guardrails, '
        'intents, entities, flows, tools, display, key_entities.'
    ),
    'SpecSlot': (
        'A spec file name from _specs/. Common values: nlu, pex, res, '
        'dialogue_state, flow_stack, context_coordinator, prompt_engineer, '
        'display_frame, ambiguity_handler, memory_manager, blocks, '
        'evaluation, server_setup, configuration, tool_smith, style_guide.'
    ),
    'FlowSlot': 'A flow name from the FLOW_CATALOG.',
    'IntentSlot': (
        'An intent name. Values: Plan, Converse, Internal, '
        'Explore, Provide, Design, Deliver.'
    ),
    'LevelSlot': 'An integer level or count.',
    'GroupSlot': 'A comma-separated list of items.',
}

VALID_SECTIONS = [
    'scope', 'persona', 'guardrails', 'intents', 'entities',
    'flows', 'tools', 'display', 'key_entities',
]


def describe_slot_type(slot_type: str) -> str:
    return SLOT_TYPES.get(slot_type, 'Unknown slot type.')


def describe_slot_schema(slots: dict) -> str:
    if not slots:
        return 'No slots for this flow.'
    lines = []
    for name, info in slots.items():
        priority = info.get('priority', 'optional')
        if hasattr(priority, 'value'):
            priority = priority.value
        slot_type = info.get('type', 'FreeTextSlot')
        desc = SLOT_TYPES.get(slot_type, '')
        lines.append(f'- {name} ({priority}, {slot_type}): {desc}')
    return '\n'.join(lines)
