"""Per-turn starter prompt for BrainstormFlow.

Generates angle ideas when `topic` is filled, or phrase alternatives when
`source.snip` is filled. At least one of source / topic must be filled."""

from backend.prompts.for_pex import render_source


def build(flow, resolved:dict, user_text:str) -> str:
    return f'<resolved_details>\n{_format_parameters(flow)}\n</resolved_details>'


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
