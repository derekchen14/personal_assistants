"""Per-turn starter prompt for CompareFlow.

Two-post structural comparison. The policy preloads metadata for both
posts. Skill optionally calls compare_style + read_section, then
narrates differences in 2-3 sentences.
"""


TEMPLATE_WITH_PREVIEWS = """<task>
Compare two posts: {post_labels}. Call `compare_style(left=<id_1>, right=<id_2>)` for metrics, then optionally `read_section` for any section-deep comparison. End by narrating the differences in 2-3 sentences.
</task>

<post_content>
{post_previews}
</post_content>

<resolved_details>
{parameters}
</resolved_details>"""


TEMPLATE_NO_PREVIEWS = """<task>
Compare two posts. Call `read_metadata` for each, optionally `read_section` for section-deep comparison, and `compare_style` for metrics. End by narrating the differences in 2-3 sentences.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    posts = resolved.get('posts') or []
    if posts:
        labels = ' vs. '.join(_post_label(p) for p in posts[:2])
        previews = '\n\n'.join(_post_preview(p) for p in posts[:2])
        return TEMPLATE_WITH_PREVIEWS.format(
            post_labels=labels,
            post_previews=previews,
            parameters=_format_parameters(flow),
        )
    return TEMPLATE_NO_PREVIEWS.format(parameters=_format_parameters(flow))


def _post_label(post:dict) -> str:
    title = post.get('title', 'Untitled')
    return f'"{title}"'


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
    if source.check_if_filled() and source.values:
        ids = []
        for v in source.values[:2]:
            if isinstance(v, dict):
                pid = v.get('post', '')
                if pid:
                    ids.append(pid)
        if ids:
            lines.append(f'Posts: {", ".join(ids)}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
