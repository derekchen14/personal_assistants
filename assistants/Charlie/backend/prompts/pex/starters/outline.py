"""Per-turn starter prompt for OutlineFlow.

Two-stage flow:
  - Direct mode: `sections` slot is filled — emit + save the outline.
  - Propose mode: `topic` filled but no sections — emit 3 candidate options as text.

The skill body branches on the same signal; the starter just frames the task
and surfaces the depth + topic + sections."""

from backend.prompts.for_pex import render_freetext, render_checklist


TEMPLATE = """<task>
Outline the post on "{topic}" at depth {depth}. {tool_sequence}. {end_condition}.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    sections_filled = flow.slots['sections'].check_if_filled()
    propose_mode = bool(resolved.get('propose_mode'))
    topic = _topic_text(flow, resolved)
    depth = resolved.get('depth', 2)

    if propose_mode or not sections_filled:
        tool_sequence = (
            'Emit three candidate outlines as text. '
            'Forbidden tools this turn: read_metadata, generate_outline, inspect_post, write_text. '
            'find_posts is optional (at most once) — skip it for green-field topics'
        )
        end_condition = 'Stop after Option 3 — no trailing commentary'
    else:
        tool_sequence = 'Generate the markdown outline and save it via `generate_outline`'
        end_condition = 'End once `generate_outline` returns success'

    return TEMPLATE.format(
        topic=topic,
        depth=depth,
        tool_sequence=tool_sequence,
        end_condition=end_condition,
        parameters=_format_parameters(flow),
    )


def _topic_text(flow, resolved:dict) -> str:
    topic_slot = flow.slots['topic']
    if topic_slot.check_if_filled():
        return str(topic_slot.to_dict())
    return resolved.get('post_title') or 'this post'


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
