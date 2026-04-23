---
name: "syndicate"
description: "cross-post to one or more secondary channels; adapts formatting for each target (Medium, Dev.to, LinkedIn, Substack) and publishes a tailored version"
version: 2
tools:
  - read_metadata
  - read_section
  - channel_status
  - release_post
---

This skill cross-posts an already-published post to one or more **secondary** channels. The primary blog (`MoreThanOneTurn`) never appears in syndicate channels — that's the Release flow.

## Process

1. Read `<resolved_details>` for `post_id` and `channel` (list of channel name strings).
2. Confirm the post is published via `read_metadata(post_id)`. If not, surface and stop.
3. For each channel in the list:
   a. Call `channel_status(channel=<channel>)` to verify connection.
   b. Call `read_metadata` + `read_section` (or use preloaded data) to retrieve content.
   c. Adapt formatting for the target channel — thread for Twitter, shorter intro for LinkedIn, code-block conventions for Dev.to.
   d. Call `release_post(post_id, channel=<channel>)` to syndicate.
4. Report per-channel success or failure. Don't abort the whole flow on one channel's failure.

## Error Handling

If the post is not published, call `handle_ambiguity(level='confirmation', observation='Source post is still draft — release first, then syndicate?')`.

If `channel_status` fails for a channel, mark it failed in the output and continue with the rest.

If `release_post` fails for a channel, retry ONCE; then surface the failure and continue.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — confirm published status.
- `read_section(post_id, sec_id)` — load content for per-channel adaptation.
- `release_post(post_id, channel)` — actual syndicate call.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Output

```json
{
  "post_id": "...",
  "title": "...",
  "syndications": [
    {"channel": "Medium", "status": "published", "url": "...", "notes": "..."},
    {"channel": "LinkedIn", "status": "failed", "notes": "auth expired"}
  ]
}
```

## Few-shot examples

### Example 1: Two-channel syndication

Resolved Details:
- post_id: abcd0123, status: published
- channel: ['Medium', 'LinkedIn']

Trajectory:
1. `read_metadata(post_id=abcd0123)` → status=published.
2. `channel_status('Medium')` → ok.
3. `release_post(post_id=abcd0123, channel='Medium')` → `_success=True`.
4. `channel_status('LinkedIn')` → `{_success: False, _error: 'auth_expired'}`.

Final reply:
```json
{
  "post_id": "abcd0123",
  "title": "Synthetic Data Generation",
  "syndications": [
    {"channel": "Medium", "status": "published", "url": "https://medium.com/...", "notes": "Live with adapted formatting."},
    {"channel": "LinkedIn", "status": "failed", "notes": "Auth expired — reconnect to retry."}
  ]
}
```
