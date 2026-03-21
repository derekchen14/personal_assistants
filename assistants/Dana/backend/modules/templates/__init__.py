"""Response templates for RES — one module per intent, no Internal."""

from backend.modules.templates import clean, transform, analyze, report, converse, plan

_INTENT_MODULES = {
    'Clean':     clean,
    'Transform': transform,
    'Analyze':   analyze,
    'Report':    report,
    'Converse':  converse,
    'Plan':      plan,
}


def get_template(flow_name:str, intent:str) -> dict:
    """Look up template by flow name within the intent module, else fallback."""
    module = _INTENT_MODULES.get(intent)
    if module:
        entry = module.TEMPLATES.get(flow_name)
        if entry:
            return {
                'template': entry.get('template', '{message}'),
                'block_hint': entry.get('block_hint'),
                'skip_naturalize': entry.get('skip_naturalize', False),
            }
        return {
            'template': module.FALLBACK,
            'block_hint': None,
            'skip_naturalize': False,
        }
    return {'template': '{message}', 'block_hint': None, 'skip_naturalize': False}
