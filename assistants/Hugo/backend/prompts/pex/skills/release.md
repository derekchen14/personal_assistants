---
name: "release"
description: "publish the post to the primary blog; makes the post live immediately on the main channel. Use syndicate to cross-post, promote to amplify reach after publishing"
version: 3
tools:
  - read_metadata
  - channel_status
  - release_post
---

This skill publishes a post to one or more channels. For each channel, check availability first, then release. Results are collected in a structured JSON response that names the status and URL per channel. The policy flips the post status after the skill returns, so focus on channel orchestration and the output shape.

## Process

1. Read the post identifier and channel list from `<resolved_details>`. The channel list is an array of channel names such as `['Substack']` or `['Substack', 'LinkedIn']`. Process each channel independently so that one channel's failure does not abort the rest.

2. For each channel in the list, in order:
  a. Call `channel_status(channel=<name>)` to verify the channel is authenticated and reachable
  b. If the status call returns `_success=False`, record the channel as failed with the returned error note and move on to the next channel without calling `release_post`.

3. When the status call completes, call `release_post(post_id, channel=<name>)` to publish.
  a. On successful publication, record the returned URL and status as part of the return list.
  b. On failure, do not retry `release_post` on failure unless the user explicitly asked for a retry. Surface the failure and let the user decide whether to re-run the release.
  c. In either case, return a valid JSON object with the results and end the turn.

## Handling Ambiguity and Errors

If `channel_status` returns `_success=False`, do NOT call `release_post` for that channel. Surface the channel as failed in the output and continue with the remaining channels.

If `release_post` fails, surface the error in the output for that channel and continue with the remaining channels. Do not abort the whole flow.

If the channel list resolves to empty and no default is configured, call `handle_ambiguity(level='specific', metadata={'missing_slot': 'channel'})`.

## Tools

### Task-specific tools

- `channel_status(channel)` is the gate before every `release_post` call. It verifies authentication and reachability, and a `_success=False` return means that channel is terminal for this turn. The policy retries the status check up to three times on network errors before giving up because channel APIs are external and prone to transient failures.
- `release_post(post_id, channel)` performs the publish. Call once per channel after the status gate succeeds. Record the URL and status returned by the tool. A failure is not retried automatically, since publish is a side-effecting call where silent retry risks a double-post; record the failure in the output and let the user re-invoke if they want a retry.
- `read_metadata(post_id)` is a fallback helper when `<resolved_details>` is missing post fields, which is rare. Skip it in the common case.

### General tools

- `execution_error(violation, message)` when a tool fails in a way that should surface as a policy-layer error frame rather than a per-channel failure row.
- `handle_ambiguity(level, metadata)` when the channel list resolves to empty and no default channel is configured.
- `manage_memory(action, key, value)` to read a per-channel token when the user has stored authentication preferences there.
- `call_flow_stack(action='read', details='flows')` to check whether a `syndicate` or `promote` flow is already queued behind this release. When one is, trim the release output to the primary channel so the downstream flow handles amplification.

## Output Shape

Always a `releases` array, one entry per channel attempted — single-channel publishes produce a single-element array. Every release entry carries the same four keys (`channel`, `status`, `url`, `notes`); set `url` to `null` on failure.

```json
{
  "post_id": "...",
  "title": "...",
  "releases": [
    {"channel": "Substack", "status": "published", "url": "...", "notes": "..."},
    {"channel": "LinkedIn", "status": "failed", "url": null, "notes": "auth expired"}
  ]
}
```

## Few-shot examples

### Example 1: Single-channel publish

Resolved Details:
- post_id: abcd0123, title: "User Simulators for Training RL Agents"
- channel: ['Substack']

Trajectory:
1. `channel_status(channel='Substack')` → `{_success: True, ok: True}`.
2. `release_post(post_id=abcd0123, channel='Substack')` → `{_success: True, url: 'https://substack.com/p/user-simulators-for-training-rl-agents'}`.

Final reply:
```json
{
  "post_id": "abcd0123",
  "title": "User Simulators for Training RL Agents",
  "releases": [
    {
      "channel": "Substack",
      "status": "published",
      "url": "https://substack.com/p/user-simulators-for-training-rl-agents",
      "notes": "Published successfully; ready to syndicate."
    }
  ]
}
```

### Example 2: Multi-channel, one fails

Resolved Details:
- post_id: abcd0123, title: "User Simulators for Training RL Agents"
- channel: ['Substack', 'LinkedIn']

Trajectory:
1. `channel_status(channel='Substack')` → ok.
2. `release_post(post_id=abcd0123, channel='Substack')` → `{_success: True, url: 'https://substack.com/p/user-simulators'}`.
3. `channel_status(channel='LinkedIn')` → `{_success: False, _error: 'auth_expired'}`.
4. Skip `release_post` for LinkedIn.

Final reply:
```json
{
  "post_id": "abcd0123",
  "title": "User Simulators for Training RL Agents",
  "releases": [
    {"channel": "Substack", "status": "published", "url": "https://substack.com/p/user-simulators", "notes": "Live."},
    {"channel": "LinkedIn", "status": "failed", "url": null, "notes": "Auth expired, reconnect and retry."}
  ]
}
```
