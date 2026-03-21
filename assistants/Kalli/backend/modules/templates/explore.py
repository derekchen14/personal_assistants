"""Explore intent response templates."""

FALLBACK = "Here's what I found about {flow_name}: {message}"

TEMPLATES = {
    'status':    {'template': "Here's where we stand: {message}", 'block_hint': 'card'},
    'lessons':   {'template': "{message}", 'block_hint': 'list'},
    'browse':    {'template': "Here's what I found: {message}", 'block_hint': 'list'},
    'recommend': {'template': "{message}"},
    'summarize': {'template': "Here's a summary: {message}"},
    'explain':   {'template': "{message}"},
    'inspect':   {'template': "{message}", 'block_hint': 'card'},
    'compare':   {'template': "Here's how they compare: {message}", 'block_hint': 'card'},
}
