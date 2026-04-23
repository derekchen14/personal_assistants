---
name: "schedule"
description: "schedule a post for future publication; sets a specific date and time for automatic publishing on a given channel"
version: 2
tools:
  - list_channels
  - channel_status
  - release_post
  - update_post
---

This skill schedules a post for future publication on one or more channels. The policy ensures source + channel + datetime are all filled before invoking.

## Process

1. Read `<resolved_details>` for `post_id`, `channel` (list of channel names), and `datetime` (`{start, stop, time_len, unit, recurrence}`).
2. Verify each channel is connected via `channel_status(channel=<channel>)`.
3. For each connected channel, call `release_post(post_id, channel=<channel>, scheduled_for=<start ISO timestamp>)`.
4. If `recurrence=true`, encode `unit` + `time_len` as the repeat interval in the release call.
5. Persist the schedule on the post via `update_post(post_id, updates={'status': 'scheduled', 'scheduled_for': <start>, 'channels': <channel list>})`.
6. Confirm the schedule with the user — channel(s), date/time, recurrence.

## Error Handling

If a channel fails its `channel_status` check, surface the failure for that channel and continue with the rest.

If `release_post` fails for a channel, retry ONCE; then `execution_error(violation='tool_error', message=<channel that failed>, failed_tool='release_post')`.

If `datetime.start` is in the past, call `handle_ambiguity(level='specific', metadata={'invalid_input': 'datetime'})` with an observation showing the parsed date.

## Tools

### Task-specific tools

- `list_channels()` — fallback to enumerate channels when the user said "all channels".
- `channel_status(channel)` — verify before scheduling.
- `release_post(post_id, channel, scheduled_for=...)` — schedule the publish.
- `update_post(post_id, updates)` — persist the schedule on the post.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Single-channel scheduled publish

Resolved Details:
- post_id: abcd0123
- channel: ['Substack']
- datetime: {start: '2026-05-04T09:00:00Z', recurrence: false}

Trajectory:
1. `channel_status(channel='Substack')` → ok.
2. `release_post(post_id=abcd0123, channel='Substack', scheduled_for='2026-05-04T09:00:00Z')` → `_success=True`.
3. `update_post(post_id=abcd0123, updates={'status': 'scheduled', 'scheduled_for': '2026-05-04T09:00:00Z', 'channels': ['Substack']})` → `_success=True`.

Final reply:
```
Scheduled for May 4 at 9:00 UTC on Substack.
```

### Example 2: Recurring schedule, multi-channel

Resolved Details:
- post_id: abcd0123
- channel: ['Substack', 'LinkedIn']
- datetime: {start: '2026-05-04T09:00:00Z', recurrence: true, unit: 'week', time_len: 1}

Trajectory:
1-4. channel_status + release_post for each channel.
5. update_post with the schedule + recurrence metadata.

Final reply:
```
Scheduled to publish weekly starting May 4, 9:00 UTC, on Substack and LinkedIn.
```
