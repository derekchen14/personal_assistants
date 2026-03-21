"""Converse intent response templates."""

FALLBACK = "{message}"

TEMPLATES = {
    'chat':       {'template': "{message}"},
    'next':       {'template': "{message}"},
    'feedback':   {'template': "{message}"},
    'preference': {'template': "{message}", 'skip_naturalize': True},
    'style':      {'template': "{message}", 'skip_naturalize': True},
    'endorse':    {'template': "{message}", 'skip_naturalize': True},
    'dismiss':    {'template': "{message}", 'skip_naturalize': True},
}
