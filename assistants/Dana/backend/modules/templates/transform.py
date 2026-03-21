"""Transform intent response templates."""

FALLBACK = "{message}"

TEMPLATES = {
    'insert':  {'template': "{message}", 'block_hint': 'card'},
    'delete':  {'template': "{message}", 'block_hint': 'card'},
    'join':    {'template': "{message}", 'block_hint': 'card'},
    'append':  {'template': "{message}", 'block_hint': 'card'},
    'reshape': {'template': "{message}", 'block_hint': 'card'},
    'merge':   {'template': "{message}", 'block_hint': 'card'},
    'split':   {'template': "{message}", 'block_hint': 'card'},
    'define':  {'template': "{message}", 'block_hint': 'card'},
}
