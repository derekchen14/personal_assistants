"""Analyze intent response templates."""

FALLBACK = "Here's what I found: {message}"

TEMPLATES = {
    'query':    {'template': "{message}", 'block_hint': 'card'},
    'lookup':   {'template': "Here's what I found: {message}", 'block_hint': 'list'},
    'pivot':    {'template': "{message}", 'block_hint': 'card'},
    'describe': {'template': "Here's a summary: {message}", 'block_hint': 'card'},
    'compare':  {'template': "Here's how they compare: {message}", 'block_hint': 'card'},
    'exist':    {'template': "{message}"},
    'segment':  {'template': "{message}", 'block_hint': 'card'},
}
