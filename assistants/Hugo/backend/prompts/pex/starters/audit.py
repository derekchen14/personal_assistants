"""Per-turn starter prompt for AuditFlow.

Whole-post voice + style consistency check that now fixes the drift itself via revise_content and
applies any requested tone shift. The policy snapshots before the skill runs, so edits are undoable."""

from backend.prompts.for_pex import render_source, render_checklist


TEMPLATE = """<task>
Audit "{post_title}" for voice + style consistency, then fix it. {tool_sequence}. Rewrite each drifting section with `revise_content` so it reads in the user's voice; apply the `Tone` shift below when present. If the post already reads cleanly, make no edits and say so.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    tool_sequence = (
        'Detect with `editor_review` and `inspect_post` by default; only chain `find_posts` + '
        '`compare_style` when the user asks for comparison against prior posts or `Reference count` is '
        'shown below. Honor explicit exclusions ("just the editor part", "skip structure")'
    )
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        tool_sequence=tool_sequence,
        parameters=_format_parameters(flow, resolved),
    )


def _format_parameters(flow, resolved:dict) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    ref_count = flow.slots['reference_count']
    threshold = flow.slots['threshold']
    tone = flow.slots['tone']
    suggestions = flow.slots['suggestions']
    if ref_count.check_if_filled():
        lines.append(f'Reference count: {ref_count.level}')
    if threshold.check_if_filled():
        lines.append(f'Threshold: {threshold.to_dict()}')
    if tone.check_if_filled():
        lines.append(f'Tone: {tone.to_dict()}')
    if suggestions.check_if_filled():
        lines.append(f'Tone changes: {render_checklist(suggestions)}')
    # Surface valid section ids so read_section / revise_content use real ids rather
    # than invented slugs that fail with not_found and waste tool rounds.
    section_ids = resolved.get('section_ids') or []
    if section_ids:
        lines.append(f'Valid section ids: {", ".join(section_ids)}')
    return '\n'.join(lines)
