"""Per-turn starter prompt for BrowseFlow.

Browse is read-only. The policy already called `find_posts` and passes
the result `items` via `extra_resolved`; this starter shows the user's
query, the target scope, and the result set for narration."""

from backend.prompts.for_pex import render_freetext


def build(flow, resolved:dict, user_text:str) -> str:
    return f'<resolved_details>\n{_format_parameters(flow, resolved)}\n</resolved_details>'


def _format_parameters(flow, resolved:dict) -> str:
    lines = []
    query = flow.slots.get('query')
    target = flow.slots.get('target')
    if query and query.check_if_filled():
        lines.append(f'Tags: {render_freetext(query)}')
    if target and target.check_if_filled():
        val = target.values[0] if target.values else ''
        lines.append(f'Target: {val}')
    items = resolved.get('items') or []
    if items:
        titles = [it.get('title', 'Untitled') for it in items[:5]]
        lines.append(f'Items ({len(items)}): ' + '; '.join(titles))
    else:
        lines.append('Items: none')
    return '\n'.join(lines) if lines else '(no parameters filled)'
