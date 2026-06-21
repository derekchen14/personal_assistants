"""Per-turn starter prompt for SummarizeFlow.

Produces a standalone summary paragraph. The policy preloads the post title + outline into
<resolved_details>'s post block (when available) plus an optional length hint."""


TEMPLATE = """<task>
Summarize "{post_title}" in {length_clause}. Read the outline below; only call `read_section` if you need detail beyond it. End by emitting the summary as your final reply (no tool calls needed).
</task>

<post_content>
{outline}
</post_content>

<resolved_details>
{parameters}
</resolved_details>"""


TEMPLATE_NO_OUTLINE = """<task>
Summarize "{post_title}" in {length_clause}. Call `read_metadata(include_outline=True)` then `read_section` per section as needed. End by emitting the summary as your final reply.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    outline = (resolved.get('outline') or '').strip()
    length_clause = _length_clause(flow)
    common = {
        'post_title': resolved.get('post_title', 'this post'),
        'length_clause': length_clause,
        'parameters': _format_parameters(flow),
    }
    if outline:
        return TEMPLATE.format(outline=outline, **common)
    return TEMPLATE_NO_OUTLINE.format(**common)


def _length_clause(flow) -> str:
    length_slot = flow.slots['length']
    if not length_slot.check_if_filled():
        return '~75 words (default)'
    target = int(length_slot.level) if hasattr(length_slot, 'level') else 75
    if target < 30:
        return f'a single hook sentence (~{target} words)'
    return f'~{target} words'


def _format_parameters(flow) -> str:
    lines = []
    length = flow.slots['length']
    if length.check_if_filled():
        lines.append(f'Length: {length.level}')
    return '\n'.join(lines) if lines else '(default length)'
