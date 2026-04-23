---
name: "browse"
description: "browse posts by tag, topic, or status. Narrates search results; does not modify posts"
version: 2
tools:
  - find_posts
  - brainstorm_ideas
  - search_notes
---

This skill narrates a browse result. The policy has already called `find_posts` with the user's tags + target and passed the results below via `<resolved_details>`. Your job is to describe what was found in 1–2 sentences.

## Process

1. Read the filled slots from `<resolved_details>`:
   a. `Tags`: the search terms the user provided.
   b. `Target`: one of `tag` (search posts by tag), `note` (search notes), or `both`.
   c. `Items`: the results already retrieved by the policy.
2. If `Items` is empty, say so plainly ("No posts matched `<tags>`"). Do NOT retry `find_posts` — the policy already did its job.
3. If `Items` has results, narrate the top 3–5 by title. Highlight anything surprising (e.g. a recent publish, unexpected tag overlap) but keep it short.
4. Do NOT modify posts. Browse is read-only.

## Error Handling

If `Items` is empty AND no tags were provided, call `handle_ambiguity(level='specific', metadata={'missing_slot': 'tags'})` — the user needs to specify what to browse for.

If the policy's `find_posts` failed (indicated by a missing or malformed `Items` block), call `execution_error(violation='tool_error', message='find_posts upstream failure')`.

## Tools

### Task-specific tools

- `find_posts(query, tags, status)` — fallback only. The policy has usually already called this; re-run only if `<resolved_details>` is missing the Items block.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1 — tag hits with a few results

Resolved Details:
- Tags: ml, training
- Target: tag
- Items: 4 posts (Building User Simulators, Training an RL Agent, Dataset Curation Tips, Why Synthetic Data Works)

Trajectory: upstream `find_posts(tags=['ml','training'])` returned the 4 items above; the skill narrates without re-calling.

Final reply:
```
Found 4 posts tagged `ml, training`. Top matches: Building User Simulators, Training an RL Agent, Dataset Curation Tips.
```

### Example 2 — empty result

Resolved Details:
- Tags: quantum
- Target: tag
- Items: none

Final reply:
```
No posts matched tag `quantum`. Want to try a related tag like `physics` or `research`?
```

### Example 3 — mixed target (posts + notes)

Resolved Details:
- Tags: onboarding
- Target: both
- Items: 2 posts + 3 notes

Final reply:
```
Found 2 posts and 3 notes tagged `onboarding`. The posts include "Week One Playbook"; the notes are quick drafts from recent brainstorms.
```
