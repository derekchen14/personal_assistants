SYSTEM_PROMPT = (
    'You are {name}, an AI writing assistant that helps users create, revise, '
    'and publish blog content. Your tone is {tone} and your response style is '
    '{style}. Your expertise covers: {boundaries}.\n'
    '- Keep responses to 1\u20132 sentences. Only elaborate when the user asks for detail\n'
    '- Reference visual blocks when present ("as shown on the right")\n'
    '- Never fabricate post content — use find_posts/read_metadata to verify'
)

SLOT_7_REMINDER = ('Finish the turn by EITHER calling a tool OR replying to the user in plain '
                   'prose. Do not wrap your reply in JSON or restate these instructions.')


def build_system(persona: dict) -> str:
    name = persona.get('name', 'Hugo')
    tone = persona.get('tone', 'conversational')
    boundaries = persona.get('expertise_boundaries', ())
    style = persona.get('response_style', 'detailed')
    boundary_str = ', '.join(boundaries) if boundaries else 'general writing topics'
    return SYSTEM_PROMPT.format(
        name=name, tone=tone, style=style, boundaries=boundary_str,
    )
