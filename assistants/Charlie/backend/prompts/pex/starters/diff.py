"""Per-turn starter prompt for DiffFlow.

Section-scoped version diff. Calls diff_section with either lookback
(N versions back) or mapping (e.g. draft vs published)."""

from backend.prompts.for_pex import render_source


TEMPLATE = """<task>
Describe the version diff for the section in "{post_title}". {tool_sequence}. End once you've narrated what changed in 2-3 sentences.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    has_lookback = flow.slots['lookback'].check_if_filled()
    has_mapping = flow.slots['mapping'].check_if_filled() if 'mapping' in flow.slots else False

    if has_lookback:
        tool_sequence = 'Call `diff_section(post_id, sec_id, lookback=N)` to get the structured diff'
    elif has_mapping:
        tool_sequence = 'Call `diff_section(post_id, sec_id, mapping=...)` to compare the two named versions'
    else:
        tool_sequence = 'Call `diff_section(post_id, sec_id, lookback=1)` to compare against the previous version'

    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        tool_sequence=tool_sequence,
        parameters=_format_parameters(flow),
    )


def _format_parameters(flow) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    lookback = flow.slots['lookback']
    if lookback.check_if_filled():
        lines.append(f'Lookback: {lookback.to_dict()}')
    mapping = flow.slots.get('mapping')
    if mapping and mapping.check_if_filled():
        lines.append(f'Mapping: {mapping.to_dict()}')
    return '\n'.join(lines)
