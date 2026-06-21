"""Per-turn starter prompt for RemoveFlow.

Removal is destructive, so the starter never preloads section content — the skill calls
`read_metadata` first to confirm the target and check `status` before dispatching to
`delete_post` or `remove_content`. The starter just renders the resolved entity (target /
image / type) so the skill knows what to delete and which tool path to take."""

from backend.prompts.for_pex import render_source


TEMPLATE = """<task>
Remove the named {type_label} from "{post_title}". Always call `read_metadata` first to confirm the target and check its `status`. Then dispatch: `delete_post` for whole-post / draft / note removal, `remove_content` for section / paragraph removal in place.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(
        type_label=_type_label(flow),
        post_title=resolved.get('post_title', 'this post'),
        parameters=_format_parameters(flow),
    )


def _format_parameters(flow) -> str:
    lines = []
    target = flow.slots['target']
    image = flow.slots['image']
    type_slot = flow.slots['type']
    if target.check_if_filled():
        lines.append(f'Target: {render_source(target)}')
    if image.check_if_filled():
        lines.append(f'Image: {_render_image(image)}')
    if type_slot.check_if_filled():
        lines.append(f'Type: {type_slot.value}')
    return '\n'.join(lines) if lines else '(no entity parameters — declare ambiguity)'


def _type_label(flow) -> str:
    type_slot = flow.slots['type']
    return type_slot.value if type_slot.check_if_filled() else 'entity'


def _render_image(slot) -> str:
    """ImageSlot stores image_type + value(=src). Mirror simplify.py's helper."""
    if not slot.image_type:
        return ''
    parts = [f'type={slot.image_type}']
    if slot.value:
        parts.append(f'src={slot.value}')
    return ', '.join(parts)
