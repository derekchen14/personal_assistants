"""Per-turn starter prompt for ComposeFlow.

Shows the per-section preview as XML so the LLM can scope the work
before reading individual sections, plus filled steps/guidance."""

from backend.prompts.for_pex import (
    render_source, render_freetext, render_checklist, render_section_preview,
)


def build(flow, resolved:dict, user_text:str) -> str:
    section_previews = render_section_preview(resolved.get('section_preview') or {})
    if not section_previews:
        section_previews = '(section previews not preloaded — call read_metadata with include_preview=True before composing)'
    return (f'<post_content>\n{section_previews}\n</post_content>\n\n'
            f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>')


def _format_parameters(flow) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    steps = flow.slots['steps']
    guidance = flow.slots['guidance']
    if steps.check_if_filled():
        lines.append(f'Steps: {render_checklist(steps)}')
    if guidance.check_if_filled():
        lines.append(f'Guidance: {render_freetext(guidance)}')
    return '\n'.join(lines)
