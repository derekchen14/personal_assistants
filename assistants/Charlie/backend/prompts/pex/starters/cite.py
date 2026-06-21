"""Per-turn starter prompt for CiteFlow.

Two paths through the skill:
  - URL filled → attach the citation directly via revise_content.
  - URL empty + target snippet filled → web_search and propose a source.

The starter shows the snippet (when known) plus the URL when present."""

from backend.prompts.for_pex import render_freetext


TEMPLATE_WITH_SNIPPET = """<task>
Cite a snippet in "{post_title}". {tool_sequence}. {end_condition}.
</task>

<line_content>
{snippet}
</line_content>

<resolved_details>
{parameters}
</resolved_details>"""


TEMPLATE_NO_SNIPPET = """<task>
Cite content in "{post_title}". {tool_sequence}. {end_condition}.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    has_url = flow.slots['url'].check_if_filled()
    snippet = _snippet_text(flow)

    if has_url:
        tool_sequence = 'Call `revise_content` to attach the URL alongside the snippet'
        end_condition = 'End once the citation is saved'
    else:
        tool_sequence = 'Call `web_search` to find a credible source, then propose it for confirmation'
        end_condition = 'End after proposing — do NOT call revise_content until confirmed'

    common = {
        'post_title': resolved.get('post_title', 'this post'),
        'tool_sequence': tool_sequence,
        'end_condition': end_condition,
        'parameters': _format_parameters(flow),
    }
    if snippet:
        return TEMPLATE_WITH_SNIPPET.format(snippet=snippet, **common)
    return TEMPLATE_NO_SNIPPET.format(**common)


def _snippet_text(flow) -> str:
    target = flow.slots['target']
    if not target.check_if_filled() or not target.values:
        return ''
    val = target.values[0]
    if isinstance(val, dict):
        return val.get('snip') or val.get('text') or ''
    return str(val)


def _format_parameters(flow) -> str:
    lines = []
    target = flow.slots['target']
    url = flow.slots['url']
    if target.check_if_filled() and isinstance(target.values[0], dict):
        val = target.values[0]
        ref = ', '.join(f'{k}={val[k]}' for k in ('post', 'sec', 'snip') if val.get(k))
        if ref:
            lines.append(f'Target: {ref}')
    if url.check_if_filled():
        lines.append(f'URL: {render_freetext(url)}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
