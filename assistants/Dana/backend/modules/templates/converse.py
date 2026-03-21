"""Converse intent response templates."""

FALLBACK = "{message}"

TEMPLATES = {
    'explain':    {'template': "{message}"},
    'chat':       {'template': "{message}"},
    'preference': {'template': "{message}", 'skip_naturalize': True},
    'recommend':  {'template': "{message}"},
    'undo':       {'template': "{message}", 'block_hint': 'toast'},
    'approve':    {'template': "{message}", 'skip_naturalize': True},
    'reject':     {'template': "{message}", 'skip_naturalize': True},
}
