"""Per-turn starter prompt for ReleaseFlow.

Publishes the post to one or more channels (defaults to the primary blog). The skill iterates each
channel: channel_status → release_post, then emits a single JSON response with a `releases` array.
"""


TEMPLATE = """<task>
Release "{post_title}" to {channels}. For each channel, call `channel_status` first, then `release_post` on success. Emit a single JSON response at the end with a `releases` array (one entry per channel attempted).
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        channels=_channel_label(flow),
        parameters=_format_parameters(flow, resolved),
    )


def _channel_label(flow) -> str:
    channel = flow.slots['channel']
    if channel.check_if_filled() and channel.values:
        return ', '.join(_channel_name(v) for v in channel.values)
    return 'the primary blog'


def _channel_name(val) -> str:
    if isinstance(val, dict):
        return val.get('chl') or val.get('name') or 'channel'
    return str(val)


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
        lines.append(f'Channels: {_channel_label(flow)}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
