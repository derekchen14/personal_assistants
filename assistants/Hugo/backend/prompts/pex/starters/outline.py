"""Per-turn starter prompt for OutlineFlow.

Two-stage flow:
  - Direct mode: `sections` slot is filled — emit + save the outline.
  - Propose mode: `topic` filled but no sections — emit 3 candidate options as text.

The skill body branches on the same signal; the starter just frames the task
and surfaces the depth + topic + sections."""

from backend.prompts.for_pex import render_freetext, render_checklist


def build(flow, resolved:dict, user_text:str) -> str:
    return f'<resolved_details>\n{_format_parameters(flow, resolved)}\n</resolved_details>'


def _format_parameters(flow, resolved:dict) -> str:
    # The skill branches on `stage`, and direct mode saves via generate_outline(post_id, ...) —
    # both MUST render here or the sub-agent falls back to propose behavior and never saves.
    lines = [f'stage: {flow.stage}']
    if resolved.get('post_id'):
        lines.append(f'post_id: {resolved["post_id"]}')
    topic = resolved.get('topic') or (flow.slots['topic'].to_dict()
                                      if flow.slots['topic'].check_if_filled() else '')
    if topic:
        lines.append(f'Topic: {topic}')
    sections = flow.slots['sections']
    if sections.check_if_filled():
        lines.append(f'Sections: {render_checklist(sections)}')
    depth = resolved.get('depth') or (flow.slots['depth'].level
                                      if flow.slots['depth'].check_if_filled() else 0)
    if depth:
        lines.append(f'Depth: {int(depth)}')
    return '\n'.join(lines)
