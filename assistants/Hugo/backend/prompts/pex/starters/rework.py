"""Per-turn starter prompt for ReworkFlow.

Rework handles both single-section and whole-post (structural) operations in a single llm_execute
pass. Policy preloads a per-section preview (title + first few lines) via include_preview=True so
the skill sees the whole-post shape without N×read_section calls."""

from backend.prompts.for_pex import (
    render_source, render_freetext, render_checklist, render_section_preview,
)


def build(flow, resolved:dict, user_text:str) -> str:
    post_preview = render_section_preview(resolved['section_preview'])
    return (f'<post_preview>\n{post_preview}\n</post_preview>\n\n'
            f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>')


def _format_parameters(flow) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    suggestions = flow.slots['suggestions']
    remove = flow.slots.get('remove')
    if suggestions.check_if_filled():
        lines.append(f'Suggestions: {render_checklist(suggestions)}')
    if remove and remove.check_if_filled():
        lines.append(f'Remove: {render_freetext(remove)}')
    type_slot = flow.slots['type']
    image = flow.slots['image']
    if type_slot.check_if_filled():
        lines.append(f'Type: {type_slot.value}')
    if image.check_if_filled():
        lines.append(f'Image: {image.to_dict()}')
    return '\n'.join(lines)
