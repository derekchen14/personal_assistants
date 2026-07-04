"""Per-turn starter prompt for AuditFlow.

Whole-post voice + style consistency check that now fixes the drift itself via revise_content and
applies any requested tone shift. The policy snapshots before the skill runs, so edits are undoable."""

from backend.prompts.for_pex import render_source, render_checklist


def build(flow, resolved:dict, user_text:str) -> str:
    prose = (resolved.get('post_prose') or '').strip()
    block = f'<post_content>\n{prose}\n</post_content>\n\n' if prose else ''
    return block + f'<resolved_details>\n{_format_parameters(flow, resolved)}\n</resolved_details>'


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
