"""Deliver intent response templates."""

FALLBACK = "{message}"

TEMPLATES = {
    'generate':  {'template': "Here are the generated files: {message}", 'block_hint': 'list'},
    'package':   {'template': "{message}", 'block_hint': 'card'},
    'test':      {'template': "{message}", 'block_hint': 'card'},
    'deploy':    {'template': "{message}", 'block_hint': 'card'},
    'secure':    {'template': "{message}", 'block_hint': 'card'},
    'version':   {'template': "{message}", 'block_hint': 'toast'},
}
