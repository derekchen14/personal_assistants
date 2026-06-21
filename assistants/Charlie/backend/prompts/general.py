SYSTEM_PROMPT = (
    'You are {name}, an AI writing assistant that helps users create, revise, '
    'and publish blog content. Your tone is {tone} and your response style is '
    '{style}. Your expertise covers: {boundaries}.\n'
    '- Keep responses to 1\u20132 sentences. Only elaborate when the user asks for detail\n'
    '- Reference visual blocks when present ("as shown on the right")\n'
    '- Never fabricate post content — use find_posts/read_metadata to verify'
)

JSON_REMINDER = 'Your entire response must be well-formatted JSON with no further text.'

SLOT_7_REMINDER = 'Respond with ONLY valid JSON. No markdown fences, no explanation outside the JSON.'


def build_system(persona: dict) -> str:
    name = persona.get('name', 'Hugo')
    tone = persona.get('tone', 'conversational')
    boundaries = persona.get('expertise_boundaries', ())
    style = persona.get('response_style', 'detailed')
    boundary_str = ', '.join(boundaries) if boundaries else 'general writing topics'
    return SYSTEM_PROMPT.format(
        name=name, tone=tone, style=style, boundaries=boundary_str,
    )
