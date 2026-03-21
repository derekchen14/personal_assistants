"""Gather intent response templates."""

FALLBACK = "Got it — I've recorded {slot_summary}. {message}"

TEMPLATES = {
    'scope':   {'template': "I've saved your assistant's scope: {message}", 'block_hint': 'form'},
    'teach':   {'template': "{message}"},
    'intent':  {'template': "{message}", 'block_hint': 'form'},
    'persona': {'template': "Persona saved: {message}", 'block_hint': 'form'},
    'entity':  {'template': "{message}", 'block_hint': 'form'},
    'propose': {'template': "{message}", 'block_hint': 'list'},
}
