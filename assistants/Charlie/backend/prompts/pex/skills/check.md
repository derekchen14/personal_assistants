---
name: "check"
description: "check the technical metadata surrounding a post; category tags, has_featured_image, publication date, last edited date, scheduled date, channels, status: draft, scheduled, published, or unpublished"
version: 2
tools:
  - find_posts
  - channel_status
---

This skill narrates a status check across the user's drafts and posts. The policy has already called `find_posts` and passed the result via `<resolved_details>`. Your job is to summarize what was found in 1–2 sentences and suggest the next action.

## Process

1. Read the result set from the `<resolved_details>` block. It contains the count, the status filter (if any), and up to 10 titles.
2. Summarize: how many items match the filter, and the top 3 titles by relevance.
3. Suggest the next action. For drafts close to ready, propose `release` or `polish`. For unpublished posts older than a month, propose `promote`.
4. Keep the reply tight — 1–2 sentences plus the suggestion.

## Error Handling

If the result set is empty, say so plainly and suggest a broader query (e.g., drop the status filter).

If the policy upstream failed to call `find_posts`, call `execution_error(violation='tool_error', message='find_posts upstream failure', failed_tool='find_posts')`.

## Tools

### Task-specific tools

- `find_posts(status=...)` — fallback only. The policy normally has called this already.
- `channel_status(channel)` — when the user is asking specifically about channel readiness.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Drafts ready for publication

Resolved Details:
- Status: draft
- Items (3): Building User Simulators; Multi-modal Agents; Why Synthetic Data Works

Trajectory: upstream `find_posts(status='draft')` returned the 3 items above; no extra calls needed.

Final reply:
```
You have 3 drafts in flight. "Building User Simulators" looks closest to ready; want to release it next?
```

### Example 2: No matches

Resolved Details:
- Status: scheduled
- Items: none

Final reply:
```
Nothing scheduled right now. Want me to list everything in draft instead?
```
