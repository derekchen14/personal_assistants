NATURALIZE_INSTRUCTIONS = (
    'Smooth this filled template into natural language.\n\n'
    'Rules:\n'
    '- Keep the same information — do not add or remove facts\n'
    '- Match the persona\'s tone and style\n'
    '- If a visual block accompanies the response, reference it '
    '("here\'s what I found", "as shown on the right") rather than '
    'repeating its content\n'
    '- Maximum 2 sentences unless the content genuinely requires more\n'
    '- Do not use markdown formatting unless the content is code\n'
    '- Respond with ONLY the rewritten text, nothing else'
)

CLARIFICATION_TEMPLATES = {
    'general': (
        'I\'m not quite sure what you\'re looking for. '
        'Could you tell me more about what you\'d like to do?'
    ),
    'partial': (
        'I think I understand, but I need a bit more detail. {observation}'
    ),
    'specific': (
        'To proceed, I need the following: {missing_slots}. '
        'Could you provide {first_missing}?'
    ),
    'confirmation': (
        'Just to confirm — you want to {action}? (yes/no)'
    ),
}

MERGE_INSTRUCTIONS = (
    'Combine these individual responses into one coherent message.\n\n'
    'Rules:\n'
    '- Use natural transitions between topics\n'
    '- Remove redundancy if two responses mention the same thing\n'
    '- Keep the combined response concise\n'
    '- Maintain the persona\'s tone throughout'
)


def build_naturalize_prompt(raw_text: str, history_text: str,
                            block_type: str | None) -> str:
    parts = [NATURALIZE_INSTRUCTIONS, '\n\n']
    if block_type and block_type != 'default':
        parts.append(
            f'A visual block ({block_type}) will accompany this response. '
            f'Reference it rather than repeating its content.\n\n'
        )
    if history_text:
        parts.append(f'Recent conversation:\n{history_text}\n\n')
    parts.append(f'Raw response:\n{raw_text}')
    return ''.join(parts)


def build_clarification(level: str, metadata: dict,
                        observation: str | None) -> str:
    template = CLARIFICATION_TEMPLATES.get(level, CLARIFICATION_TEMPLATES['general'])
    missing = metadata.get('missing_slots', [])
    return template.format(
        observation=observation or '',
        missing_slots=', '.join(missing) if missing else 'more information',
        first_missing=missing[0] if missing else 'more detail',
        action=metadata.get('action', 'proceed'),
    )
