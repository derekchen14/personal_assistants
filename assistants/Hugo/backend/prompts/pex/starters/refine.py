"""Per-turn starter prompt for RefineFlow.

The skill body (`pex/skills/refine.md`) carries the static process. This file carries the runtime
payload — post title, current outline (as XML), and the filled feedback / steps parameters."""

from backend.prompts.for_pex import render_freetext, render_checklist


def build(flow, resolved:dict, user_text:str) -> str:
    current_outline = resolved.get(
        'current_outline',
        '(outline not preloaded — call read_metadata with include_outline=True)',
    )
    return (f'<post_content>\n{current_outline}\n</post_content>\n\n'
            f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>')


def _format_parameters(flow) -> str:
    lines = []
    feedback = flow.slots['feedback']
    steps = flow.slots['steps']
    if feedback.check_if_filled():
        lines.append(f'Feedback: {render_freetext(feedback)}')
    if steps.check_if_filled():
        lines.append(f'Specific changes: {render_checklist(steps)}')
    image = flow.slots['image']
    position = flow.slots['position']
    settings = flow.slots['settings']
    if image.check_if_filled():
        lines.append(f'Image: {image.to_dict()}')
    if position.check_if_filled():
        lines.append(f'Position: {position.to_dict()}')
    if settings.check_if_filled():
        lines.append(f'Formatting settings: {settings.to_dict()}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret the latest utterance directly)'
