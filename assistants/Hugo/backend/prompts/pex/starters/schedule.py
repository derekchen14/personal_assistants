"""Per-turn starter prompt for ScheduleFlow.

Schedules a post for future publication on one or more channels. The
datetime slot carries `{start, stop, time_len, unit, recurrence}`.
"""


TEMPLATE = """<task>
Schedule "{post_title}" for {datetime_label} on {channels}. Sequence per channel: `channel_status` → `release_post(scheduled_for=<start>)`. Then `update_post` to persist the schedule on the post. End once every channel is scheduled or has surfaced an error.
</task>

<resolved_details>
{parameters}
</resolved_details>"""


def build(flow, resolved:dict, user_text:str) -> str:
    return TEMPLATE.format(
        post_title=resolved.get('post_title', 'this post'),
        datetime_label=_datetime_label(flow),
        channels=_channel_label(flow),
        parameters=_format_parameters(flow),
    )


def _datetime_label(flow) -> str:
    dt_slot = flow.slots['datetime']
    if not dt_slot.check_if_filled():
        return 'the requested datetime'
    val = dt_slot.to_dict() if hasattr(dt_slot, 'to_dict') else None
    if isinstance(val, dict):
        start = val.get('start') or 'the requested datetime'
        rec = val.get('recurrence')
        unit = val.get('unit')
        time_len = val.get('time_len')
        if rec and unit and time_len:
            return f'{start}, recurring every {time_len} {unit}(s)'
        return str(start)
    return str(val) if val else 'the requested datetime'


def _channel_label(flow) -> str:
    channel = flow.slots['channel']
    if channel.check_if_filled() and channel.values:
        names = []
        for v in channel.values:
            if isinstance(v, dict):
                names.append(v.get('chl') or v.get('name') or 'channel')
            else:
                names.append(str(v))
        return ', '.join(names)
    return 'the configured channels'


def _format_parameters(flow) -> str:
    lines = []
    channel = flow.slots['channel']
    dt_slot = flow.slots['datetime']
    if channel.check_if_filled():
        lines.append(f'Channels: {_channel_label(flow)}')
    if dt_slot.check_if_filled():
        lines.append(f'Datetime: {_datetime_label(flow)}')
    return '\n'.join(lines) if lines else '(no parameters filled — interpret latest utterance)'
