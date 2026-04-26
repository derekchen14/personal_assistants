"""Per-turn starter prompt for PolishFlow.

Section-scoped sentence/paragraph polish. style_notes (when filled) takes priority over the inferred
style from the existing prose. Image polish is also supported via the image slot.
"""

from backend.prompts.for_pex import render_source, render_freetext


TEMPLATE = """<task>
Polish the named span in "{post_title}". {tool_sequence}. End once `revise_content` saves the polished section.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    has_style_notes = flow.slots['style_notes'].check_if_filled()
    has_image = flow.slots['image'].check_if_filled()

    if has_image:
        tool_sequence = 'Read the section, assess the image vs. the section\'s main idea, propose a replacement via `revise_content` if needed'
    elif has_style_notes:
        tool_sequence = 'Read the section, rewrite the named span to the requested style (style_notes overrides current register), save via `revise_content`'
    else:
        tool_sequence = 'Read the section, tighten sentences and word choice within the named span, save via `revise_content`'

    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        tool_sequence=tool_sequence,
        parameters=_format_parameters(flow),
    )


def _format_parameters(flow) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    style_notes = flow.slots['style_notes']
    image = flow.slots['image']
    if style_notes.check_if_filled():
        lines.append(f'Style notes: {render_freetext(style_notes)}')
    if image.check_if_filled():
        lines.append(f'Image: {_render_image(image)}')
    return '\n'.join(lines)


def _render_image(slot) -> str:
    if not slot.values:
        return ''
    val = slot.values[0]
    if isinstance(val, dict):
        return ', '.join(f'{key}={val[key]}' for key in ('type', 'sec', 'description') if val.get(key))
    return str(val)
