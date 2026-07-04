"""Per-turn starter prompt for CiteFlow.

Two paths through the skill:
  - URL filled → attach the citation directly via revise_content.
  - URL empty + target snippet filled → web_search and propose a source.

The starter shows the snippet (when known) plus the URL when present."""

from backend.prompts.for_pex import render_freetext


TEMPLATE_WITH_SNIPPET = """<line_content>
{snippet}
</line_content>

<resolved_details>
{parameters}
</resolved_details>"""


TEMPLATE_NO_SNIPPET = """<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    snippet = _snippet_text(flow)
    parameters = _format_parameters(flow)
    if snippet:
        return TEMPLATE_WITH_SNIPPET.format(snippet=snippet, parameters=parameters)
    return TEMPLATE_NO_SNIPPET.format(parameters=parameters)


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
