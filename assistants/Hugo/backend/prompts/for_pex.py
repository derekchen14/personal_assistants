SKILL_SYSTEM_SUFFIX = (
    '\n\n## Execution Rules\n\n'
    '- Use the provided tools to fulfill the request\n'
    '- Follow the skill template\'s tool sequence\n'
    '- If a tool call fails, try an alternative approach before giving up\n'
    '- Stay within the tool\'s JSON Schema — do not invent parameters\n'
    '- When done, provide a clear summary of what you accomplished\n'
    '- If you need information that is not available, say so\n'
)


def build_skill_system(base_system: str, flow,
                       skill_prompt: str | None, scratchpad: dict) -> str:
    flow_name = flow.name()
    filled_slots = flow.slot_values_dict()

    parts = [base_system]
    parts.append(
        f'\n\nYou are executing the "{flow_name}" flow.\n'
        f'Purpose: {flow.goal}\n'
        f'Intent: {flow.intent}\n'
    )

    if skill_prompt:
        parts.append(f'\n--- Skill Instructions ---\n{skill_prompt}\n')

    parts.append(SKILL_SYSTEM_SUFFIX)

    if filled_slots:
        slot_lines = [f'  - {k}: {v}' for k, v in filled_slots.items()]
        parts.append(f'\nFilled slots:\n' + '\n'.join(slot_lines) + '\n')

    if scratchpad and isinstance(scratchpad, dict):
        sp_lines = [f'  - {k}: {v}' for k, v in scratchpad.items()]
        parts.append(f'\nSession context:\n' + '\n'.join(sp_lines) + '\n')

    return ''.join(parts)


def build_skill_messages(flow_name: str, convo_history: str) -> list[dict]:
    content = ''
    if convo_history:
        content += f'Recent conversation:\n{convo_history}\n\n'
    content += (
        f'Execute the "{flow_name}" flow using the available tools. '
        f'When done, provide a clear summary of what you accomplished.'
    )
    return [{'role': 'user', 'content': content}]
