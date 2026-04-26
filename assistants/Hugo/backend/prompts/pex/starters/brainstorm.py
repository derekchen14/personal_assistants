"""Per-turn starter prompt for BrainstormFlow.

Two modes:
  - Topic mode (`topic` filled): generate 3–5 angle ideas.
  - Snippet mode (`source.snip` filled): suggest 2–3 alternative phrasings.

Disjunction entity: at least one of source / topic must be filled."""

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
        verb = f'Brainstorm angles for "{topic.to_dict()}"'
        tool_sequence = 'Call `brainstorm_ideas` for candidate angles; optionally `find_posts` once to dedup'
        end_condition = 'Emit 3–5 distinct ideas as JSON'
    elif snippet:
        verb = f'Suggest alternative phrasings for the highlighted snippet'
        tool_sequence = 'Optionally call `read_section` for tone context, then propose 2–3 alternatives'
        end_condition = 'Emit alternatives as JSON'
    else:
        # Should not happen — policy guards against this. Render a generic frame.
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
    if topic.check_if_filled():
        lines.append(f'Topic: {topic.to_dict()}')
    if source.check_if_filled():
        lines.append(f'Source: {render_source(source)}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
