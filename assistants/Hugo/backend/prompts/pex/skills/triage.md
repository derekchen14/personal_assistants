---
name: "triage"
description: "plan a revision sequence; examines a draft and prioritizes which sections need rework, polish, or restructuring; produces an ordered checklist of revision tasks"
version: 2
tools:
  - read_metadata
  - inspect_post
---

This skill examines a draft and produces an ordered revision plan. Output drives `_plan_lifecycle`: each prioritized issue becomes a Revise-intent sub_flow (rework / polish / tone / simplify / remove).

## Process

1. Read `source` (post) and optional `scope` (light / moderate / heavy) from `<resolved_details>`.
2. Call `inspect_post(post_id)` to surface metrics: word count per section, structural issues, style flags.
3. Prioritize by severity: structural issues first (`rework`), then content issues (`simplify` / `remove`), then polish (`polish` / `tone`).
4. Match `scope` to the cutoff: `light` = 1–2 actions, `moderate` = 3–4, `heavy` = ≥5.
5. Emit dual-output JSON.

## Error Handling

If `source` is missing or doesn't resolve to a post, call `handle_ambiguity(level='partial', metadata={'missing_entity': 'post'})`.

If `inspect_post` fails, fall back to a coarse plan based on metadata only and note the gap in `freeform`.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — basic post info if inspect fails.
- `inspect_post(post_id)` — section-level metrics and issue flags.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Output

```json
{
  "freeform": "Three revision steps: rework Architecture, simplify Process, then polish.",
  "structured": {
    "description": "Moderate revision sweep for 'Building User Simulators'.",
    "sub_flows": [
      {"flow_name": "rework",   "slots": {"source": {"post": "abcd0123", "sec": "architecture"}}, "status": "pending"},
      {"flow_name": "simplify", "slots": {"source": {"post": "abcd0123", "sec": "process"}}, "status": "pending"},
      {"flow_name": "polish",   "slots": {"source": {"post": "abcd0123"}}, "status": "pending"}
    ]
  }
}
```

## Few-shot examples

### Example 1: Heavy scope, mixed issues

Resolved Details:
- Source: post=abcd0123
- Scope: heavy

Trajectory: `inspect_post(post_id='abcd0123')` → `structural_issues=['heading_hierarchy']`, `wordy_sections=['process', 'architecture']`.

Final reply:
```json
{
  "freeform": "Heavy pass: rework heading hierarchy, simplify two sections, polish, then audit.",
  "structured": {
    "description": "Heavy revision sweep — 5 actions.",
    "sub_flows": [
      {"flow_name": "rework",   "slots": {"source": {"post": "abcd0123"}}, "status": "pending"},
      {"flow_name": "simplify", "slots": {"source": {"post": "abcd0123", "sec": "process"}}, "status": "pending"},
      {"flow_name": "simplify", "slots": {"source": {"post": "abcd0123", "sec": "architecture"}}, "status": "pending"},
      {"flow_name": "polish",   "slots": {"source": {"post": "abcd0123"}}, "status": "pending"},
      {"flow_name": "audit",    "slots": {"source": {"post": "abcd0123"}}, "status": "pending"}
    ]
  }
}
```
