"""Per-turn starter prompt for BrainstormFlow.

Generates angle ideas when `topic` is filled, or phrase alternatives when
`source.snip` is filled. At least one of source / topic must be filled."""

from backend.prompts.for_pex import render_source


TEMPLATE = """<task>
{verb}. {tool_sequence}. {end_condition}.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    topic = flow.slots['topic']
    source = flow.slots['source']
    snippet = _snippet_text(source)

    if topic.check_if_filled() and not snippet:
        seeded = flow.slots['ideas'].check_if_filled()
        verb = f'Brainstorm angles for "{topic.to_dict()}"'
        if seeded:
            verb += '. The user already seeded the brainstorm — do NOT repeat their items; extend the direction with complementary ideas'
        tool_sequence = 'Call `read_section` to gain context on what the source post already covers; optionally `find_posts` once to dedup against prior coverage'
        end_condition = 'Emit 3–5 distinct ideas as JSON'
    elif snippet:
        verb = f'Suggest alternative phrasings for the highlighted snippet'
        tool_sequence = 'Call `read_section` for surrounding tone context, then propose 2–3 alternatives'
        end_condition = 'Emit alternatives as JSON'
    else:
        # Should not happen — policy guards against this. Render a generic artifact.
        verb = 'Brainstorm based on the latest utterance'
        tool_sequence = 'Pick the right helper from your tool list'
        end_condition = 'Emit results as JSON'

    return TEMPLATE.format(
        verb=verb,
        tool_sequence=tool_sequence,
        end_condition=end_condition,
        parameters=_format_parameters(flow),
    )


def _snippet_text(source_slot) -> str:
    if not source_slot.check_if_filled() or not source_slot.values:
        return ''
    val = source_slot.values[0]
    if isinstance(val, dict):
        return val.get('snip') or ''
    return ''


def _format_parameters(flow) -> str:
    lines = []
    topic = flow.slots['topic']
    source = flow.slots['source']
    ideas = flow.slots['ideas']
    if topic.check_if_filled():
        lines.append(f'Topic: {topic.to_dict()}')
    if source.check_if_filled():
        lines.append(f'Source: {render_source(source)}')
    if ideas.check_if_filled():
        lines.append(f'Ideas (user seed list): {ideas.to_dict()}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
