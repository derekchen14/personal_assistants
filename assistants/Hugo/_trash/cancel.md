---
name: "cancel"
description: "cancel a scheduled publication or unpublish a live post; reverts to draft status or removes from the channel entirely"
version: 2
tools:
  - read_metadata
  - cancel_release
  - update_post
---

This skill cancels a scheduled publication or unpublishes a live post. The policy already verified the source resolves; this skill handles per-status branching.

## Process

1. Read `<resolved_details>` for `post_id` and the optional `reason`.
2. Call `read_metadata(post_id)` to confirm the post's current `status`.
3. Branch by status:
   a. `scheduled` → call `cancel_release(post_id)` to drop the schedule, then `update_post(post_id, updates={'status': 'draft'})`.
   b. `published` → call `update_post(post_id, updates={'status': 'draft'})`. The channel adapter handles the unpublish.
   c. `draft` → no-op; the post is already in draft state.
4. If `reason` is filled, write it to scratchpad under the `cancel` key for audit.

## Error Handling

If `read_metadata` fails, call `execution_error(violation='missing_reference', message='post not found', failed_tool='read_metadata')`.

If `cancel_release` or `update_post` fails, retry ONCE; then `execution_error(violation='tool_error', message=<reason>, failed_tool='<name>')`.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — confirm current status.
- `cancel_release(post_id)` — drop a scheduled publication.
- `update_post(post_id, updates)` — flip status back to draft.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Cancel a scheduled publish

Resolved Details:
- Source: post=abcd0123
- Reason: "moving to next week"

Trajectory:
1. `read_metadata(post_id=abcd0123)` → status=scheduled.
2. `cancel_release(post_id=abcd0123)` → `_success=True`.
3. `update_post(post_id=abcd0123, updates={'status': 'draft'})` → `_success=True`.

Final reply:
```
Cancelled the scheduled publication. Reverted to draft.
```

### Example 2: Unpublish a live post

Resolved Details:
- Source: post=abcd0123
- Reason: "fixing a typo before re-publishing"

Trajectory:
1. `read_metadata(post_id=abcd0123)` → status=published.
2. `update_post(post_id=abcd0123, updates={'status': 'draft'})` → `_success=True`.

Final reply:
```
Unpublished and back to draft. Ready for fixes.
```
