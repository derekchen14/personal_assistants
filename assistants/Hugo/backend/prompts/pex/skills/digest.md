---
name: "digest"
description: "plan a multi-part blog series; splits a broad theme into installments, defines the narrative arc, assigns subtopics to each part, and sets a suggested publication sequence"
version: 2
tools:
  - find_posts
---

This skill splits a broad theme into a multi-part series. Output drives PlanPolicy's `_plan_lifecycle` — each part becomes a `create` sub_flow with its own subtopic.

## Process

1. Read `theme` (required) and `part_count` from `<resolved_details>`. Default `part_count` = 3–5 based on theme breadth.
2. Call `find_posts(query=<theme>)` to check what already exists; weave existing posts into the series arc rather than duplicating.
3. Design a coherent arc: opener (frame the problem), middle parts (build out one subtopic each), closer (synthesis or call-to-action).
4. For each part: subtopic, angle, connection to prior/next parts.
5. Emit dual-output JSON.

## Error Handling

If `theme` is missing, call `handle_ambiguity(level='specific', metadata={'missing_slot': 'theme'})`.

If `part_count` is outside [2, 12], call `handle_ambiguity(level='specific', metadata={'invalid_input': 'part_count'})`.

## Tools

### Task-specific tools

- `find_posts(query=<theme>)` — dedup against existing series content.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Output

```json
{
  "freeform": "I split the theme into 4 parts, opening with the problem, then walking through each component, and closing with deployment notes.",
  "structured": {
    "description": "4-part series on agentic observability.",
    "sub_flows": [
      {"flow_name": "create", "slots": {"title": "Why agents need observability", "type": "draft", "topic": "observability for agents"}, "status": "pending", "part": 1, "arc_role": "opener"},
      ...
    ]
  }
}
```

## Few-shot examples

### Example 1: 4-part series

Resolved Details:
- Theme: observability for long-running agents
- Part_count: 4

Trajectory: `find_posts(query='observability for long-running agents')` → 1 prior post on metrics; the series weaves around it instead of duplicating.

Final reply:
```json
{
  "freeform": "Here's a 4-part series: problem framing, then logging, metrics, and tracing in turn.",
  "structured": {
    "description": "4-part series on observability for long-running agents.",
    "sub_flows": [
      {"flow_name": "create", "slots": {"title": "Why long-running agents need observability", "type": "draft"}, "status": "pending", "part": 1, "arc_role": "opener"},
      {"flow_name": "create", "slots": {"title": "Structured logging for agent turns", "type": "draft"}, "status": "pending", "part": 2, "arc_role": "build"},
      {"flow_name": "create", "slots": {"title": "Metrics that catch silent regressions", "type": "draft"}, "status": "pending", "part": 3, "arc_role": "build"},
      {"flow_name": "create", "slots": {"title": "End-to-end traces across multi-turn flows", "type": "draft"}, "status": "pending", "part": 4, "arc_role": "closer"}
    ]
  }
}
```
