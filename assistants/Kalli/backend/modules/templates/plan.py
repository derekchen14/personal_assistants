"""Plan intent response templates."""

FALLBACK = "{message}"

TEMPLATES = {
    'research':  {'template': "{message}", 'block_hint': 'list'},
    'finalize':  {'template': "{message}", 'block_hint': 'list'},
    'onboard':   {'template': "Here's the onboarding plan: {message}", 'block_hint': 'list'},
    'expand':    {'template': "{message}", 'block_hint': 'list'},
    'redesign':  {'template': "{message}", 'block_hint': 'list'},
}
