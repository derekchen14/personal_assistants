"""Per-turn starter prompt for ReleaseFlow.

Publishes the post to its primary blog. Release always targets the primary channel; the skill
calls channel_status (against the primary) then release_post."""


TEMPLATE = """<task>
Release "{post_title}". Publish to each channel in `channel` below; when none is named, default to the primary blog. Per channel, call `channel_status` first then `release_post` on success — one channel's failure must not abort the rest.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        parameters=_format_parameters(flow, resolved),
    )


def _format_parameters(flow, resolved:dict) -> str:
    lines = []
    post_id = resolved.get('post_id')
    post_title = resolved.get('post_title')
    if post_id:
        lines.append(f'Post ID: {post_id}')
    if post_title:
        lines.append(f'Title: {post_title}')
    channel = flow.slots['channel']
    if channel.check_if_filled():
        lines.append(f'channel: {channel.to_dict()}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
