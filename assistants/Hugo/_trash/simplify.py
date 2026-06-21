"""Per-turn starter prompt for SimplifyFlow.

Disjunction-style entity (source vs image), so the parameters block shows whichever is filled. When
the policy preloads the target section content via `extra_resolved['section_content']`, the starter
embeds it in a `<section_content>` XML block so the skill can skip a runtime `read_section` call."""

from backend.prompts.for_pex import render_source, render_freetext


TEMPLATE_WITH_SECTION = """<task>
Simplify the named target in "{post_title}" — shorten sentences, reduce paragraph length, remove redundancy. Rewrite the content below, then call `revise_content` to save.
</task>

<section_content>
{section_content}
</section_content>

<resolved_details>
{parameters}
</resolved_details>"""


TEMPLATE_NO_SECTION = """<task>
Simplify the named target in "{post_title}" — shorten sentences, reduce paragraph length, remove redundancy. Always `read_section` before editing. Always call `revise_content` to save.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    section_content = resolved.get('section_content', '').strip()
    common = {
        'post_title': resolved.get('post_title', 'this post'),
        'parameters': _format_parameters(flow),
    }
    if section_content:
        return TEMPLATE_WITH_SECTION.format(section_content=section_content, **common)
    return TEMPLATE_NO_SECTION.format(**common)


def _format_parameters(flow) -> str:
    lines = []
    source = flow.slots['source']
    image = flow.slots['image']
    guidance = flow.slots['guidance']
    suggestions = flow.slots['suggestions']
    if source.check_if_filled():
        lines.append(f'Source: {render_source(source)}')
    if image.check_if_filled():
        lines.append(f'Image: {_render_image(image)}')
    if guidance.check_if_filled():
        lines.append(f'Guidance: {render_freetext(guidance)}')
    if suggestions.check_if_filled():
        lines.append(f'Suggestions: {_render_suggestions(suggestions)}')
    return '\n'.join(lines) if lines else '(no entity parameters — declare ambiguity)'


def _render_image(slot) -> str:
    """ImageSlot stores image_type + value(=src) + position. NLU also passes `alt` but the slot doesn't store it (see `ImageSlot.assign_one`)."""
    if not slot.image_type:
        return ''
    parts = [f'type={slot.image_type}']
    if slot.value:
        parts.append(f'src={slot.value}')
    return ', '.join(parts)


def _render_suggestions(slot) -> str:
    """ChecklistSlot from the audit-chain: name='[severity] issue', description='note'. Render both so the skill sees what to fix."""
    parts = []
    for step in slot.steps:
        name, desc = step.get('name', ''), step.get('description', '')
        if name and desc:
            parts.append(f'{name}: {desc}')
        else:
            parts.append(name or desc)
    return '; '.join(p for p in parts if p)
