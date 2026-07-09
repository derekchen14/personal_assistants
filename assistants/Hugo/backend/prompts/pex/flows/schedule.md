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

If `datetime.start` is in the past, call `declare_ambiguity(level='specific', metadata={'missing': 'datetime', 'reason': 'invalid_value'}, observation=<parsed date>)`.

## Tools

### Task-specific tools

- `list_channels()` — fallback to enumerate channels when the user said "all channels".
- `channel_status(channel)` — verify before scheduling.
- `release_post(post_id, channel, scheduled_for=...)` — schedule the publish.
- `update_post(post_id, updates)` — persist the schedule on the post.

### General tools

- `execution_error(violation, message)`
- `declare_ambiguity(**params)`
- `read_scratchpad(**params)`
- `read_flow_stack(details)`

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

### Example 3: Requested time is in the past

Resolved Details:
- post_id: 71c0a9d4
- channel: ['Substack']
- datetime: {start: '2026-06-30T14:00:00Z', recurrence: false}

Trajectory:
1. `datetime.start` is earlier than the current time, so the schedule cannot be set.
2. `declare_ambiguity(level='specific', metadata={'missing': 'datetime', 'reason': 'invalid_value'}, observation='June 30 at 2:00 PM UTC has already passed; give me a future time')`. End turn.

### Example 4: All channels

Resolved Details:
- post_id: 71c0a9d4
- channel: ['all']
- datetime: {start: '2026-07-15T08:00:00Z', recurrence: false}

Trajectory:
1. `list_channels()` → ['Substack', 'LinkedIn', 'Twitter'].
2. `channel_status` + `release_post(scheduled_for='2026-07-15T08:00:00Z')` for each connected channel.
3. `update_post(post_id=71c0a9d4, updates={'status': 'scheduled', 'scheduled_for': '2026-07-15T08:00:00Z', 'channels': ['Substack', 'LinkedIn', 'Twitter']})` → `_success=True`.

Final reply:
```
Scheduled for July 15 at 8:00 UTC across Substack, LinkedIn, and Twitter.
```

### Example 5: One channel fails to schedule

Resolved Details:
- post_id: 71c0a9d4
- channel: ['Substack', 'LinkedIn']
- datetime: {start: '2026-07-20T09:30:00Z', recurrence: false}

Trajectory:
1. `channel_status(channel='Substack')` → ok; `release_post(post_id=71c0a9d4, channel='Substack', scheduled_for='2026-07-20T09:30:00Z')` → `_success=True`.
2. `channel_status(channel='LinkedIn')` → ok; `release_post(...)` → `_success=False`. Retry once → still `_success=False`.
3. `execution_error(violation='tool_error', message='LinkedIn scheduling failed twice', failed_tool='release_post')`. End turn.
