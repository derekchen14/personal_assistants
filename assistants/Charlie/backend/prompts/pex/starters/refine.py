"""Per-turn starter prompt for RefineFlow.

The skill body (`pex/skills/refine.md`) carries the static process. This file carries the runtime
payload — post title, current outline (as XML), and the filled feedback / steps parameters."""

from backend.prompts.for_pex import render_freetext, render_checklist


TEMPLATE = """<task>
Refine the outline of "{post_title}". Apply the changes from the user's final utterance to the outline below. Use `revise_content` to rewrite an existing section's body, `insert_section` (then `revise_content` for the body) to add a new H2 at a position, `update_post` with `rename_section` to rename an existing heading, or `remove_content` to delete a section. End once you have successfully saved all your refinements.
</task>

<post_content>
{current_outline}
</post_content>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        current_outline=resolved.get(
            'current_outline',
            '(outline not preloaded — call read_metadata with include_outline=True)',
        ),
        parameters=_format_parameters(flow),
    )


def _format_parameters(flow) -> str:
    lines = []
    feedback = flow.slots['feedback']
    steps = flow.slots['steps']
    if feedback.check_if_filled():
        lines.append(f'Feedback: {render_freetext(feedback)}')
    if steps.check_if_filled():
        lines.append(f'Specific changes: {render_checklist(steps)}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret the latest utterance directly)'
