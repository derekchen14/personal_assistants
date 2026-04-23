---
name: "calendar"
description: "plan a content calendar; lays out a publishing schedule over weeks or months: which topics to draft, target publish dates, and how to space content for consistency"
version: 2
tools:
  - find_posts
---

This skill produces a content calendar — a sequence of post slots with topics + target publish dates. The output drives PlanPolicy's `_plan_lifecycle` so each entry can be expanded into a full post lifecycle later.

## Process

1. Read `timeframe` and `count` from `<resolved_details>`. Default timeframe = 1 month; default count = 4–8 based on the timeframe length.
2. Call `find_posts` once to scan recent topics so the calendar avoids repetition.
3. Allocate each slot a topic + target date, spacing entries evenly across the timeframe.
4. Note format hints (how-to, listicle, opinion, teardown) when the topic suggests one — this informs the downstream `outline` flow's depth choice.
5. Emit the dual-output JSON described under Output.

## Error Handling

If `timeframe` parses to less than a week or more than a year, call `handle_ambiguity(level='specific', metadata={'invalid_input': 'timeframe'})` with an observation showing the supported range.

If `find_posts` fails, proceed without the dedup scan and note the gap in `freeform`.

## Tools

### Task-specific tools

- `find_posts(...)` — recent-content dedup scan.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Output

```json
{
  "freeform": "I drafted a 5-post calendar for next month, alternating teardowns and how-tos.",
  "structured": {
    "description": "Content calendar (next month, 5 posts).",
    "sub_flows": [
      {"flow_name": "create", "slots": {"title": "Vision encoders for agentic UIs", "type": "draft", "topic": "multi-modal agents"}, "status": "pending", "target_date": "2026-05-04"},
      ...
    ]
  }
}
```

## Few-shot examples

### Example 1: One-month plan, 4 posts

Resolved Details:
- Timeframe: next month
- Count: 4

Trajectory: `find_posts(status='published')` → 6 recent posts (used for dedup; none overlap the proposed topics).

Final reply:
```json
{
  "freeform": "Here's a 4-post calendar over the next month, weekly cadence.",
  "structured": {
    "description": "Content calendar — 4 posts, weekly.",
    "sub_flows": [
      {"flow_name": "create", "slots": {"title": "Why Synthetic Data Works", "type": "draft", "topic": "synthetic data"}, "status": "pending", "target_date": "2026-05-04"},
      {"flow_name": "create", "slots": {"title": "Vision Encoders for Agentic UIs", "type": "draft", "topic": "multi-modal agents"}, "status": "pending", "target_date": "2026-05-11"},
      {"flow_name": "create", "slots": {"title": "Observability for Long-Running Agents", "type": "draft", "topic": "agent observability"}, "status": "pending", "target_date": "2026-05-18"},
      {"flow_name": "create", "slots": {"title": "Reward Modeling Pitfalls", "type": "draft", "topic": "reward modeling"}, "status": "pending", "target_date": "2026-05-25"}
    ]
  }
}
```
