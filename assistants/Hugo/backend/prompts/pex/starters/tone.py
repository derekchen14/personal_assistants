"""Per-turn starter prompt for ToneFlow.

Whole-post tone shift. The policy default-commits chosen_tone='natural'
when both electives are unset; that resolution happens before the starter
sees the slot state.
"""

from backend.prompts.for_pex import render_source, render_freetext


TEMPLATE = """<task>
Adjust the tone of "{post_title}" to {tone_label}. Read each section, rewrite to the target tone (preserve facts and structure), and save via `revise_content`. End once every section has been processed.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    tone_label = _tone_label(flow)
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        tone_label=tone_label,
        parameters=_format_parameters(flow),
    )


def _tone_label(flow) -> str:
    chosen = flow.slots['chosen_tone']
    custom = flow.slots['custom_tone']
    if custom.check_if_filled():
        return f'"{custom.to_dict()}"'
    if chosen.check_if_filled():
        return str(chosen.to_dict())
    return 'natural'


def _format_parameters(flow) -> str:
    lines = [f'Source: {render_source(flow.slots["source"])}']
    chosen = flow.slots['chosen_tone']
    custom = flow.slots['custom_tone']
    if chosen.check_if_filled():
        lines.append(f'Chosen tone: {chosen.to_dict()}')
    if custom.check_if_filled():
        lines.append(f'Custom tone: {render_freetext(custom)}')
    return '\n'.join(lines)
