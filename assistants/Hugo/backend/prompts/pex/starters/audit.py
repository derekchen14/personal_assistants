"""Per-turn starter prompt for AuditFlow.

Whole-post style + voice consistency check. Read-only — never edits the post.
The policy handles threshold-based confirmation before any downstream edits."""

from backend.prompts.for_pex import render_source


TEMPLATE = """<task>
Audit "{post_title}" for voice + style consistency. {tool_sequence}. End by calling `save_findings` with the structured findings — do NOT edit the post.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    tool_sequence = (
        'Run `editor_review` and `inspect_post` by default; only chain `find_posts` + `compare_style` '
        'when the user explicitly asks for comparison against prior posts or `Reference count` is shown '
        'below. Honor explicit exclusions ("just the editor part", "skip structure") by running only the '
        'requested tools'
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
    if ref_count.check_if_filled():
        lines.append(f'Reference count: {ref_count.level}')
    if threshold.check_if_filled():
        lines.append(f'Threshold: {threshold.to_dict()}')
    # Surface valid section ids so read_section calls use real ids rather
    # than invented slugs that fail with not_found and waste tool rounds.
    section_ids = resolved.get('section_ids') or []
    if section_ids:
        lines.append(f'Valid section ids: {", ".join(section_ids)}')
    return '\n'.join(lines)
