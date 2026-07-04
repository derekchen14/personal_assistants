"""Per-turn starter prompt for WriteFlow (sentence-level editing).

Section-scoped sentence/paragraph editing. style_notes (when filled) takes priority over the inferred
style from the existing prose. Image edits are also supported via the image slot."""

from backend.prompts.for_pex import render_source, render_freetext


def build(flow, resolved:dict, user_text:str) -> str:
    return f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>'


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
