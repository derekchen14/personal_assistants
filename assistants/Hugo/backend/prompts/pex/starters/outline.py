"""Per-turn starter prompt for OutlineFlow.

Two-stage flow:
  - Direct mode: `sections` slot is filled — emit + save the outline.
  - Propose mode: `topic` filled but no sections — emit 3 candidate options as text.

The skill body branches on the same signal; the starter just frames the task
and surfaces the depth + topic + sections."""

from backend.prompts.for_pex import render_freetext, render_checklist


def build(flow, resolved:dict, user_text:str) -> str:
    return f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>'


def _format_parameters(flow) -> str:
    lines = []
    sections = flow.slots['sections']
    topic = flow.slots['topic']
    depth = flow.slots['depth']
    if topic.check_if_filled():
        lines.append(f'Topic: {topic.to_dict()}')
    if sections.check_if_filled():
        lines.append(f'Sections: {render_checklist(sections)}')
    if depth.check_if_filled():
        lines.append(f'Depth: {depth.level}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
