"""Report intent response templates."""

FALLBACK = "{message}"

TEMPLATES = {
    'plot':      {'template': "{message}", 'block_hint': 'card'},
    'trend':     {'template': "{message}", 'block_hint': 'card'},
    'dashboard': {'template': "{message}", 'block_hint': 'card'},
    'export':    {'template': "{message}", 'block_hint': 'toast'},
    'summarize': {'template': "Here's a summary: {message}", 'block_hint': 'card'},
    'style':     {'template': "{message}", 'block_hint': 'card'},
    'design':    {'template': "{message}", 'block_hint': 'card'},
}
