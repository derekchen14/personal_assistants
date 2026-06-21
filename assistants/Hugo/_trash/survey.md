---
name: "survey"
description: "view configured publishing channels and their health; lists connected channels (WordPress, Medium, etc.), API status, last sync date, and credential validity"
version: 2
tools:
  - list_channels
  - channel_status
---

This skill enumerates the configured publishing channels and their health. Read-only.

## Process

1. Call `list_channels()` to get the configured channel set.
2. For each channel, call `channel_status(channel=<name>)` to verify connection.
3. Render a list with channel name, status (connected / failing / not configured), and last sync date.
4. Highlight which channels are ready for publishing right now.
5. Suggest a follow-up: `syndicate` for cross-posting, `schedule` for a scheduled release.

## Error Handling

If `list_channels` returns nothing, return a short message explaining how to set up channels.

If a `channel_status` call fails, mark that channel as "status unknown" in the output and continue with the rest.

## Tools

### Task-specific tools

- `list_channels()` — enumerate configured channels.
- `channel_status(channel)` — health check per channel.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Healthy mix

Trajectory:
1. `list_channels()` → ['blog', 'Substack', 'LinkedIn'].
2. `channel_status('blog')` → ok.
3. `channel_status('Substack')` → ok.
4. `channel_status('LinkedIn')` → `{_success: False, _error: 'auth_expired'}`.

Final reply:
```
**Channels:**
- blog — connected (last sync: today)
- Substack — connected (last sync: yesterday)
- LinkedIn — auth expired; reconnect from settings

Ready to publish: blog, Substack. Want to syndicate or schedule?
```

### Example 2: No channels configured

Trajectory:
1. `list_channels()` → [].

Final reply:
```
No publishing channels configured yet. Want me to walk through setup for the primary blog?
```
