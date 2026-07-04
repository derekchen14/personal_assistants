"""Per-turn starter prompt for SummarizeFlow.

Produces a standalone summary paragraph. The policy preloads the post title + outline into
<resolved_details>'s post block (when available) plus an optional length hint."""


TEMPLATE = """<post_content>
{outline}
</post_content>

<resolved_details>
{parameters}
</resolved_details>"""


TEMPLATE_NO_OUTLINE = """<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    outline = (resolved.get('outline') or '').strip()
    parameters = _format_parameters(flow)
    if outline:
        return TEMPLATE.format(outline=outline, parameters=parameters)
    return TEMPLATE_NO_OUTLINE.format(parameters=parameters)


def _format_parameters(flow) -> str:
    lines = []
    length = flow.slots['length']
    if length.check_if_filled():
        lines.append(f'Length: {length.level}')
    return '\n'.join(lines) if lines else '(default length)'
