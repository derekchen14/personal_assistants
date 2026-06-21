"""Per-turn starter prompt for AddFlow.

Three-way elective: points / suggestions / image. The starter shows whichever is
filled and the target section (or 'end of section' default for position)."""

from backend.prompts.for_pex import render_source


TEMPLATE = """<task>
Add content to "{post_title}". Follow the skill's Process to read the target section(s) first, then call `revise_content` for bullets/prose or `insert_media` for images. End once all additions have been saved.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        parameters=_format_parameters(flow, resolved),
    )


def _format_parameters(flow, resolved:dict) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    section_ids = resolved.get('section_ids') or []
    if section_ids:
        lines.append(f'Section ids (in order): {", ".join(section_ids)}')
    points = flow.slots['points']
    suggestions = flow.slots['suggestions']
    image = flow.slots['image']
    position = flow.slots['position']
    if points.check_if_filled():
        lines.append(f'Points: {_render_steps(points)}')
    if suggestions.check_if_filled():
        lines.append(f'Suggestions: {_render_steps(suggestions)}')
    if image.check_if_filled():
        lines.append(f'Image: {_render_image(image)}')
    if position.check_if_filled():
        lines.append(f'Position: {position.level}')
    return '\n'.join(lines)


def _render_steps(slot) -> str:
    """ChecklistSlot of {name, description}. Show description (the actual content) when present, fall back to name."""
    return '; '.join(s.get('description') or s.get('name', '') for s in slot.steps)


def _render_image(slot) -> str:
    """ImageSlot stores image_type + value(=src) + image_desc. Render the parts that are present."""
    if not slot.image_type:
        return ''
    parts = [f'type={slot.image_type}']
    if slot.value:
        parts.append(f'src={slot.value}')
    if slot.image_desc:
        parts.append(f'desc={slot.image_desc}')
    return ', '.join(parts)
