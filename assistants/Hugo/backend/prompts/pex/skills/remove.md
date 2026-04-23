---
name: "remove"
description: "remove a section from the post, delete a draft or note"
version: 2
tools:
  - delete_post
  - remove_content
  - read_metadata
---

This skill removes a section from a post, or deletes an entire draft / note. Published posts are never deletable.

## Process

1. Read `<resolved_details>` for `source` (post target) and `type` (one of: `section`, `draft`, `note`, `post`, `paragraph`).
2. Call `read_metadata(post_id)` to confirm the target exists and check its `status`.
3. **Section removal** (`type=section` or `type=paragraph`): call `remove_content(post_id, sec_id, target=...)`.
4. **Draft / note deletion** (`type=draft` or `type=note`): verify `status` is `draft` or `note`, then call `delete_post(post_id)`.
5. **Whole-post deletion** (`type=post`): only allowed when status is `draft` or `note`. Reject if `status=published` (see Error Handling).

## Error Handling

If the user asks to delete a published post (`type=post` and `status=published`), call `handle_ambiguity(level='confirmation', observation='That post is already published. Want to unpublish it first, or cancel?')`.

If the named section doesn't exist on the post, call `handle_ambiguity(level='specific', metadata={'missing_reference': '<sec_name>'})`.

If `delete_post` or `remove_content` fails, retry ONCE; then `execution_error(violation='tool_error', message=<reason>, failed_tool='<name>')`.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — confirm target + status before destructive action.
- `remove_content(post_id, sec_id, target)` — remove a section or paragraph in place.
- `delete_post(post_id)` — full deletion of a draft or note.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Remove a section

Resolved Details:
- Source: post=abcd0123, section=takeaways
- Type: section

Trajectory:
1. `read_metadata(post_id=abcd0123)` → exists, draft.
2. `remove_content(post_id=abcd0123, sec_id=takeaways)` → `_success=True`.

Final reply:
```
Removed the Takeaways section from "Building User Simulators".
```

### Example 2: Delete a draft

Resolved Details:
- Source: post=ef012345
- Type: draft

Trajectory:
1. `read_metadata(post_id=ef012345)` → exists, status=draft.
2. `delete_post(post_id=ef012345)` → `_success=True`.

Final reply:
```
Deleted the draft "Quantum Agents" — gone for good.
```

### Example 3: Reject deletion of published post

Resolved Details:
- Source: post=published_xyz
- Type: post

Trajectory:
1. `read_metadata(post_id=published_xyz)` → status=published.
2. `handle_ambiguity(level='confirmation', observation='That post is already published. Want to unpublish first, or cancel?')` → no tool call.
