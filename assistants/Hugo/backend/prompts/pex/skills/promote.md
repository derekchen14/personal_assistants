---
name: "promote"
description: "make a published post more prominent; pin to the top of the blog, mark as featured, announce to subscribers, or share to social channels and email lists. Amplifies reach after release or syndicate"
version: 2
tools:
  - read_metadata
  - promote_post
---

This skill amplifies the reach of an already-published post. Common promotion moves: pin to top of blog, mark as featured, send to email subscribers, share to social.

## Process

1. Read `<resolved_details>` for `post_id` and `channel` (optional — the promotion target).
2. Call `read_metadata(post_id)` to confirm the post is `published`. If not, surface and stop.
3. If `channel` is filled, target that channel directly. Otherwise present 2–3 promotion options the user can pick.
4. Call `promote_post(post_id, channel=<channel>, action=<pin|feature|email|social>)` for each move.
5. Report which channels were reached.

## Error Handling

If the post is not published yet, call `handle_ambiguity(level='confirmation', metadata={'missing': 'publish_status', 'question': "That post isn't published yet — release first, then promote?"})`.

If `promote_post` fails for a channel, retry ONCE; then surface the failure for that channel and continue with others.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — confirm published status.
- `promote_post(post_id, channel, action)` — execute the promotion.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Pin + email

Resolved Details:
- Source: post=abcd0123 (published)
- Channel: blog

Trajectory:
1. `read_metadata(post_id=abcd0123)` → status=published.
2. `promote_post(post_id=abcd0123, channel='blog', action='pin')` → `_success=True`.
3. `promote_post(post_id=abcd0123, channel='blog', action='email')` → `_success=True`.

Final reply:
```
Pinned to the top of the blog and sent to email subscribers (1,240 recipients).
```

### Example 2: Reject promotion of unpublished post

Resolved Details:
- Source: post=ef012345 (status=draft)

Trajectory:
1. `read_metadata(post_id=ef012345)` → status=draft.
2. `handle_ambiguity(level='confirmation', metadata={'missing': 'publish_status', 'question': "That post isn't published yet — release first, then promote?"})` → no tool call.
```

### Example 3: No channel named, present options

Resolved Details:
- Source: post=a17c8d90 (published)
- User asked: "Give the retrieval evaluation post a boost."

Trajectory:
1. `read_metadata(post_id=a17c8d90)` → status=published, no channel in the resolved details.

Final reply:
```
It's published and ready to amplify. A few options: pin it to the top of the blog, feature it on the homepage, or send it to email subscribers. Which do you want?
```

### Example 4: Social share to a named channel

Resolved Details:
- Source: post=a17c8d90 (published)
- Channel: twitter
- User asked: "Share it on Twitter."

Trajectory:
1. `read_metadata(post_id=a17c8d90)` → status=published.
2. `promote_post(post_id=a17c8d90, channel='twitter', action='social')` → `_success=True`.

Final reply:
```
Shared it to Twitter. The post link is queued in the thread.
```

### Example 5: One channel fails, continue with the rest

Resolved Details:
- Source: post=a17c8d90 (published)
- Channel: blog, email
- User asked: "Pin it and email the list."

Trajectory:
1. `read_metadata(post_id=a17c8d90)` → status=published.
2. `promote_post(post_id=a17c8d90, channel='blog', action='pin')` → `_success=True`.
3. `promote_post(post_id=a17c8d90, channel='email', action='email')` → `_success=False`. Retry once → still `_success=False`.

Final reply:
```
Pinned it to the top of the blog. The email send failed twice, so the subscriber blast did not go out. Want me to retry the email?
```
