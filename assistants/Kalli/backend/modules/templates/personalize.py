"""Personalize intent response templates."""

FALLBACK = "{message}"

TEMPLATES = {
    'revise':   {'template': "{message}", 'block_hint': 'card'},
    'remove':   {'template': "{message}", 'block_hint': 'toast'},
    'rework':   {'template': "{message}", 'block_hint': 'card'},
    'approve':  {'template': "Approved! {message}", 'block_hint': 'toast', 'skip_naturalize': True},
    'decline':  {'template': "Noted — I've removed that proposal. {message}", 'block_hint': 'toast', 'skip_naturalize': True},
    'suggest':  {'template': "{message}", 'block_hint': 'list'},
    'refine':   {'template': "{message}", 'block_hint': 'card'},
    'validate': {'template': "{message}"},
}
