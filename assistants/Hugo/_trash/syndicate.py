"""Per-turn starter prompt for SyndicateFlow.

Cross-posts an already-published post to one or more SECONDARY channels.
The primary blog never appears here — that's release."""


TEMPLATE = """<task>
Syndicate "{post_title}" to {channels}. Sequence per channel: `channel_status` → `read_metadata`/`read_section` for adaptation → `release_post`. End once every channel has either published or surfaced an error.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        channels=_channel_label(flow),
        parameters=_format_parameters(flow),
    )


def _channel_label(flow) -> str:
    channel = flow.slots['channel']
    if channel.check_if_filled() and channel.values:
        return ', '.join(_channel_name(v) for v in channel.values)
    return 'the configured secondary channels'


def _channel_name(val) -> str:
    if isinstance(val, dict):
        return val.get('chl') or val.get('name') or 'channel'
    return str(val)


def _format_parameters(flow) -> str:
    lines = []
    channel = flow.slots['channel']
    if channel.check_if_filled():
        lines.append(f'Channels: {_channel_label(flow)}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
