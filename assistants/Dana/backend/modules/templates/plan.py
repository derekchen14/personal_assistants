"""Plan intent response templates."""

FALLBACK = "{message}"

TEMPLATES = {
    'insight':  {'template': "{message}", 'block_hint': 'card'},
    'pipeline': {'template': "{message}", 'block_hint': 'list'},
    'blank':    {'template': "{message}", 'block_hint': 'card'},
    'issue':    {'template': "{message}", 'block_hint': 'card'},
    'outline':  {'template': "Here's the plan: {message}", 'block_hint': 'list'},
}
