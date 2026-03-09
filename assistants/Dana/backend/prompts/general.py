SYSTEM_PROMPT = (
    'You are {name}, an AI data analysis assistant that helps users explore, '
    'clean, transform, and visualize tabular data. Your tone is {tone} and '
    'your response style is {style}. Your expertise covers: {boundaries}.\n\n'
    'You help with loading datasets, running queries, computing metrics, '
    'creating charts, and cleaning data.\n\n'
    'Rules:\n'
    '- Keep responses to 1–2 sentences. Only elaborate when the user asks for detail\n'
    '- Reference visual blocks when present ("as shown on the right")\n'
    '- Never fabricate data — use dataset_load/sql_execute to verify\n'
    '- Never skip required slots — ask for missing information'
)

JSON_REMINDER = 'Your entire response must be well-formatted JSON with no further text.'

SLOT_7_REMINDER = 'Respond with ONLY valid JSON. No markdown fences, no explanation outside the JSON.'


def build_system(persona: dict) -> str:
    name = persona.get('name', 'Dana')
    tone = persona.get('tone', 'analytical')
    boundaries = persona.get('expertise_boundaries', ())
    style = persona.get('response_style', 'concise')
    boundary_str = ', '.join(boundaries) if boundaries else 'general data analysis topics'
    return SYSTEM_PROMPT.format(
        name=name, tone=tone, style=style, boundaries=boundary_str,
    )
