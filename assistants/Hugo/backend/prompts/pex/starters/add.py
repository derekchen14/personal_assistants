"""Per-turn starter prompt for AddFlow.

Three-way elective: points / additions / image. The starter shows whichever
is filled and the target section (or 'end of section' default for position).
"""

from backend.prompts.for_pex import render_source, render_freetext, render_checklist


TEMPLATE = """<task>
Add content to "{post_title}". Follow the skill's Process to read the target section(s) first, then call `revise_content` for bullets/prose or `insert_media` for images. End once all additions have been saved.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        parameters=_format_parameters(flow),
    )


def _format_parameters(flow) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    sections = resolved_sections(flow, 'Post sections', '')
    if sections:
        lines.append(sections)
    points = flow.slots.get('points')
    additions = flow.slots.get('additions')
    image = flow.slots.get('image')
    position = flow.slots.get('position')
    if points and points.check_if_filled():
        lines.append(f'Points: {render_checklist(points)}')
    if additions and additions.check_if_filled():
        lines.append(f'Additions: {render_freetext(additions)}')
    if image and image.check_if_filled():
        lines.append(f'Image: {_render_image(image)}')
    if position and position.check_if_filled():
        lines.append(f'Position: {position.values[0] if position.values else "end"}')
    return '\n'.join(lines)


def resolved_sections(flow, label, default) -> str:
    """Render the post's section_ids list — helpful for multi-section adds."""
    return ''  # Populated only when the policy adds it to resolved.


def _render_image(slot) -> str:
    if not slot.values:
        return ''
    val = slot.values[0]
    if isinstance(val, dict):
        return ', '.join(f'{key}={val[key]}' for key in ('type', 'description', 'sec') if val.get(key))
    return str(val)
