"""Per-turn starter prompt for BrowseFlow.

Browse is read-only. The policy already called `find_posts` and passes
the result `items` via `extra_resolved`; this starter shows the user's
query, the target scope, and the result set for narration.
"""

from backend.prompts.for_pex import render_freetext


TEMPLATE = """<task>
Narrate the browse result in 1–2 sentences. Highlight the top matches by title; keep it short. Do NOT modify any post.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(parameters=_format_parameters(flow, resolved))


def _format_parameters(flow, resolved:dict) -> str:
    lines = []
    tags = flow.slots.get('tags')
    target = flow.slots.get('target')
    if tags and tags.check_if_filled():
        lines.append(f'Tags: {render_freetext(tags)}')
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
