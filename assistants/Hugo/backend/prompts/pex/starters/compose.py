"""Per-turn starter prompt for ComposeFlow.

Shows the per-section preview as XML so the LLM can scope the work
before reading individual sections, plus filled steps/guidance.
"""

from backend.prompts.for_pex import (
    render_source, render_freetext, render_checklist, render_section_preview,
)


TEMPLATE = """<task>
Compose prose for sections of "{post_title}". For each in-scope section, call `read_section`, `convert_to_prose`, then `revise_content`. Decide scope from the parameters and the user's latest utterance.
</task>

<post_content>
{section_previews}
</post_content>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    section_previews = render_section_preview(resolved.get('section_preview') or {})
    if not section_previews:
        section_previews = '(section previews not preloaded — call read_metadata with include_preview=True before composing)'
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        section_previews=section_previews,
        parameters=_format_parameters(flow),
    )


def _format_parameters(flow) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    steps = flow.slots['steps']
    guidance = flow.slots['guidance']
    if steps.check_if_filled():
        lines.append(f'Steps: {render_checklist(steps)}')
    if guidance.check_if_filled():
        lines.append(f'Guidance: {render_freetext(guidance)}')
    return '\n'.join(lines)
