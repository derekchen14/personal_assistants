"""Per-turn starter prompt for CompareFlow.

Two-post structural comparison. The policy preloads metadata for both posts. Skill optionally calls
compare_style + read_section, then narrates differences in 2-3 sentences."""


TEMPLATE_WITH_PREVIEWS = """<post_content>
{post_previews}
</post_content>

<resolved_details>
{parameters}
</resolved_details>"""


TEMPLATE_NO_PREVIEWS = """<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    posts = resolved.get('posts') or []
    if posts:
        previews = '\n\n'.join(_post_preview(p) for p in posts[:2])
        return TEMPLATE_WITH_PREVIEWS.format(
            post_previews=previews,
            parameters=_format_parameters(flow),
        )
    return TEMPLATE_NO_PREVIEWS.format(parameters=_format_parameters(flow))


def _post_preview(post:dict) -> str:
    title = post.get('title', 'Untitled')
    sections = post.get('section_ids', [])
    section_count = len(sections)
    word_count = post.get('word_count', '?')
    sec_clause = f'{section_count} sections' if section_count else 'no sections'
    return f'**{title}** ({sec_clause}, {word_count} words)'


def _format_parameters(flow) -> str:
    lines = []
    source = flow.slots['source']
    if source.values:
        ids = [v['post'] for v in source.values[:2] if v.get('post')]
        if ids:
            lines.append(f'Posts: {", ".join(ids)}')
        sec = next((v['sec'] for v in source.values if v.get('sec')), '')
        if sec:
            lines.append(f'Section: {sec}')
    category = flow.slots['category']
    if category.check_if_filled():
        lines.append(f'Category: {category.value}')
    lookback = flow.slots['lookback']
    mapping = flow.slots['mapping']
    if lookback.check_if_filled():
        lines.append(f'Lookback: {lookback.to_dict()}')
    if mapping.check_if_filled():
        lines.append(f'Mapping: {mapping.to_dict()}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
