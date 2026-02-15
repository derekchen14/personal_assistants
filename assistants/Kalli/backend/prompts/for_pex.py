SKILL_SYSTEM_SUFFIX = (
    '\n\n## Execution Rules\n\n'
    '- Use the provided tools to fulfill the request\n'
    '- Follow the skill template\'s tool sequence\n'
    '- If a tool call fails, try an alternative approach before giving up\n'
    '- Stay within the tool\'s JSON Schema — do not invent parameters\n'
    '- When done, provide a clear summary of what you accomplished\n'
    '- If you need information that is not available, say so\n'
)

CODE_GUARDRAILS = (
    '\n\n## Code Generation Rules\n\n'
    '- Strip markdown fences from generated code before execution\n'
    '- Only import standard library modules and explicitly allowed packages\n'
    '- Validate all entity references against the provided schema\n'
    '- Generated code must be syntactically valid (parseable by ast.parse)\n'
    '- Never generate code that modifies the filesystem outside the target '
    'directory\n'
    '- Never generate code that makes network requests\n'
)


def build_skill_system(base_system: str, flow_name: str, flow_info: dict,
                       skill_prompt: str | None, filled_slots: dict,
                       scratchpad: dict) -> str:
    parts = [base_system]
    parts.append(
        f'\n\nYou are executing the "{flow_name}" flow.\n'
        f'Purpose: {flow_info.get("description", "")}\n'
        f'Intent: {flow_info.get("intent", "")}\n'
    )

    if skill_prompt:
        parts.append(f'\n--- Skill Instructions ---\n{skill_prompt}\n')

    parts.append(SKILL_SYSTEM_SUFFIX)

    if flow_name in ('generate', 'ontology', 'yaml_generate'):
        parts.append(CODE_GUARDRAILS)

    if filled_slots:
        slot_lines = [f'  - {k}: {v}' for k, v in filled_slots.items()]
        parts.append(f'\nFilled slots:\n' + '\n'.join(slot_lines) + '\n')

    if scratchpad and isinstance(scratchpad, dict):
        sp_lines = [f'  - {k}: {v}' for k, v in scratchpad.items()]
        parts.append(f'\nSession context:\n' + '\n'.join(sp_lines) + '\n')

    return ''.join(parts)


def build_skill_messages(flow_name: str, history_text: str) -> list[dict]:
    content = ''
    if history_text:
        content += f'Recent conversation:\n{history_text}\n\n'
    content += (
        f'Execute the "{flow_name}" flow using the available tools. '
        f'When done, provide a clear summary of what you accomplished.'
    )
    return [{'role': 'user', 'content': content}]
