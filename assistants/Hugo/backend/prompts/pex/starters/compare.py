"""Per-turn starter prompt for CompareFlow.

Two-post structural comparison. The policy preloads metadata for both posts. Skill optionally calls
compare_style + read_section, then narrates differences in 2-3 sentences."""


TEMPLATE_WITH_PREVIEWS = """<task>
Compare two posts: {post_labels}. Branch on the `Category` in `<resolved_details>`: `inspect` → `inspect_post` per post (numeric metrics); `check` → `read_metadata` per post (status / tags / dates); `tone` → `read_section` per post on a representative section (judge voice from prose). End by narrating the differences in 2-3 sentences, scoped to the chosen category.
</task>

<post_content>
{post_previews}
</post_content>

<resolved_details>
{parameters}
</resolved_details>"""


TEMPLATE_NO_PREVIEWS = """<task>
Compare two posts. Branch on the `Category` in `<resolved_details>`: `inspect` → `inspect_post` per post; `check` → `read_metadata` per post; `tone` → `read_section` per post on a representative section. End by narrating the differences in 2-3 sentences, scoped to the chosen category.
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
        ids = [v['post'] for v in source.values[:2] if v.get('post')]
        if ids:
            lines.append(f'Posts: {", ".join(ids)}')
    category = flow.slots['category']
    if category.check_if_filled():
        lines.append(f'Category: {category.value}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
