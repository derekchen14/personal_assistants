---
name: "diff"
description: "compare two versions of a section side by side; shows additions, deletions, and modifications highlighted so the user can evaluate what changed"
version: 2
tools:
  - find_posts
  - read_metadata
  - read_section
  - diff_section
---

This skill narrates a version diff for a single section. The policy resolves the post + section; this skill calls `diff_section` and describes what changed in 2–3 sentences.

## Process

1. Read the post + section reference from the `<resolved_details>` block. The block also carries `lookback` (how many versions back) or `mapping` (e.g. draft vs. published).
2. Call `diff_section(post_id, sec_id, lookback=N)` (or with `mapping=...` when set) to get the structured diff.
3. Summarize: lead with the largest change (addition / deletion / rewrite of the most words), then note any structural shifts (heading rename, paragraph reorder).
4. Keep it factual — describe what changed, not whether the change is good.

## Error Handling

If `diff_section` returns an empty diff, say "No changes between the two versions."

If the requested `lookback` exceeds the available history, call `handle_ambiguity(level='specific', metadata={'missing_reference': 'lookback_too_far'})` with an observation explaining how many versions are actually available.

If the section doesn't exist on the post, call `handle_ambiguity(level='specific', metadata={'missing_reference': '<sec_name>'})`.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — fallback for missing context.
- `read_section(post_id, sec_id)` — when the diff isn't enough to characterize a change.
- `diff_section(post_id, sec_id, lookback=...)` — main worker.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Lookback diff

Resolved Details:
- Source: post=abcd0123, section=motivation
- Lookback: 1

Trajectory:
1. `diff_section(post_id=abcd0123, sec_id=motivation, lookback=1)` → `{added: 3 paragraphs, removed: 1, renamed: false}`.

Final reply:
```
Motivation grew by 3 paragraphs and lost the older "Prior approach" paragraph between versions. The framing now leans on the cost argument first.
```

### Example 2: Mapping diff (draft vs published)

Resolved Details:
- Source: post=abcd0123, section=takeaways
- Mapping: {draft: published}

Trajectory:
1. `diff_section(post_id=abcd0123, sec_id=takeaways, mapping={'draft': 'published'})` → `{added: 1 sentence, removed: 0, renamed: false}`.

Final reply:
```
Takeaways gained one closing sentence between draft and published — the rest matches.
```
