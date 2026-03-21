"""Clean intent response templates."""

FALLBACK = "{message}"

TEMPLATES = {
    'update':      {'template': "{message}", 'block_hint': 'card'},
    'datatype':    {'template': "{message}", 'block_hint': 'card'},
    'dedupe':      {'template': "{message}", 'block_hint': 'card'},
    'fill':        {'template': "{message}", 'block_hint': 'card'},
    'interpolate': {'template': "{message}", 'block_hint': 'card'},
    'replace':     {'template': "{message}", 'block_hint': 'card'},
    'validate':    {'template': "{message}", 'block_hint': 'card'},
    'format':      {'template': "{message}", 'block_hint': 'card'},
}
