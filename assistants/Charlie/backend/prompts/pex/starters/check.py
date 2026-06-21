"""Per-turn starter prompt for CheckFlow.

Read-only narration of a status check. The policy has already called `find_posts` and passes the
result via `<resolved_details>`. Skill narrates in 1-2 sentences and suggests a next action."""


TEMPLATE = """<task>
Narrate the status check{status_clause}. {tool_sequence}. End once you've replied with a 1-2 sentence summary plus a suggested next action.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    status_clause = _status_clause(flow)
    tool_sequence = (
        'Read the result set from <resolved_details>; do NOT call find_posts again — '
        'the policy already did the lookup'
    )
    return TEMPLATE.format(
        status_clause=status_clause,
        tool_sequence=tool_sequence,
        parameters=_format_parameters(flow, resolved),
    )


def _status_clause(flow) -> str:
    source = flow.slots['source']
    if source.check_if_filled() and source.values:
        val = source.values[0]
        if isinstance(val, dict):
            tab = val.get('post', '')
            if tab:
                return f' (filtered to {tab})'
    return ''


def _format_parameters(flow, resolved:dict) -> str:
    lines = []
    items = resolved.get('items') or []
    if items:
        titles = [it.get('title', 'Untitled') for it in items[:5]]
        lines.append(f'Items ({len(items)}): ' + '; '.join(titles))
    else:
        lines.append('Items: none')
    return '\n'.join(lines)
