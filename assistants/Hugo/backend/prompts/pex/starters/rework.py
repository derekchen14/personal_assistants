"""Per-turn starter prompt for ReworkFlow.

Rework handles both single-section and whole-post (structural) operations in a single llm_execute
pass. Policy preloads a per-section preview (title + first few lines) via include_preview=True so
the skill sees the whole-post shape without N×read_section calls."""

from backend.prompts.for_pex import (
    render_source, render_freetext, render_checklist, render_section_preview,
)


TEMPLATE = """<task>
Rework "{post_title}". {tool_sequence}. End once the rework is saved.
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
        tool_sequence = 'Read each target section, then call `revise_content` twice — first to excise removed material, then to add new material on top'
    else:
        tool_sequence = 'For section-scoped changes: read, revise, save via `revise_content`. For structural swaps / reorders: read_section each target, remove_content to cut, insert_section to re-insert, revise_content on adjacent sections to smooth transitions'

    preview = resolved.get('section_preview') or {}
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        tool_sequence=tool_sequence,
        post_preview=render_section_preview(preview) or '(no preview available)',
        parameters=_format_parameters(flow),
    )


def _format_parameters(flow) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    changes = flow.slots['changes']
    suggestions = flow.slots['suggestions']
    remove = flow.slots.get('remove')
    if changes.check_if_filled():
        lines.append(f'Changes: {render_freetext(changes)}')
    if suggestions.check_if_filled():
        lines.append(f'Suggestions: {render_checklist(suggestions)}')
    if remove and remove.check_if_filled():
        lines.append(f'Remove: {render_freetext(remove)}')
    return '\n'.join(lines)
