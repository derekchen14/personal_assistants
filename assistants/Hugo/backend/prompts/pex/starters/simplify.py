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
    if source.check_if_filled():
        lines.append(f'Source: {render_source(source)}')
    if image.check_if_filled():
        lines.append(f'Image: {_render_image(image)}')
    if guidance.check_if_filled():
        lines.append(f'Guidance: {render_freetext(guidance)}')
    return '\n'.join(lines) if lines else '(no entity parameters — declare ambiguity)'


def _render_image(slot) -> str:
    if not slot.values:
        return ''
    val = slot.values[0]
    if isinstance(val, dict):
        sec = val.get('sec') or val.get('section') or ''
        ref = val.get('ref') or val.get('id') or ''
        return f'section={sec}, ref={ref}' if sec else f'ref={ref}'
    return str(val)
