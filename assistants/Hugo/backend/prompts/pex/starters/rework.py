"""Per-turn starter prompt for ReworkFlow.

Rework handles both single-section and whole-post (structural) operations in a single llm_execute
pass. Policy preloads a per-section preview (title + first few lines) via include_preview=True so
the skill sees the whole-post shape without N×read_section calls."""

from backend.prompts.for_pex import (
    render_source, render_freetext, render_checklist, render_section_preview,
)


TEMPLATE = """<task>
{tool_sequence} from '{post_title}' to meet the user's requests while avoiding common AI writing mannerisms.
</task>

<post_preview>
{post_preview}
</post_preview>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    has_remove = flow.slots['remove'].check_if_filled()
    if has_remove:
        tool_sequence = 'Remove content as needed'
    else:
        tool_sequence = 'Read and revise content'

    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        tool_sequence=tool_sequence,
        post_preview=render_section_preview(resolved['section_preview']),
        parameters=_format_parameters(flow),
    )


def _format_parameters(flow) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    suggestions = flow.slots['suggestions']
    remove = flow.slots.get('remove')
    if suggestions.check_if_filled():
        lines.append(f'Suggestions: {render_checklist(suggestions)}')
    if remove and remove.check_if_filled():
        lines.append(f'Remove: {render_freetext(remove)}')
    return '\n'.join(lines)
