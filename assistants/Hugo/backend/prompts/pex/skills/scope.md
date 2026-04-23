---
name: "scope"
description: "plan topic research before writing; defines what information to gather, which previous posts to reference, and what questions to answer before drafting begins"
version: 2
tools:
  - find_posts
  - brainstorm_ideas
---

This skill plans the pre-draft research for a new post. Output drives `_plan_lifecycle`: a sequence of `find` / `inspect` / `summarize` flows that gather the context the user needs before outlining.

## Process

1. Read `topic` (required) from `<resolved_details>`.
2. Call `find_posts(query=<topic>)` to surface what the user has already written nearby.
3. Decompose the research into a small set of questions the post must answer (3–5).
4. Map each question to a sub_flow: `find` for prior-art lookup, `inspect` for a specific existing post, `summarize` for digesting a related post.
5. Emit dual-output JSON. Each sub_flow's `slots` should be pre-populated with the query or post_id needed.

## Error Handling

If `topic` is missing or one-word with no context, call `handle_ambiguity(level='specific', metadata={'missing_slot': 'topic'})`.

## Tools

### Task-specific tools

- `find_posts(query=<topic>)` — prior-art scan.
- `brainstorm_ideas(topic, ...)` — when the user wants angle ideation as part of scope.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Output

```json
{
  "freeform": "Three research steps: dedupe prior posts, summarize the closest match, then brainstorm angles.",
  "structured": {
    "description": "Pre-draft research for <topic>.",
    "sub_flows": [
      {"flow_name": "find",      "slots": {"query": "<topic>"}, "status": "pending"},
      {"flow_name": "summarize", "slots": {"source": {"post": "<closest_post_id>"}}, "status": "pending"},
      {"flow_name": "outline",   "slots": {"topic": "<topic>"}, "status": "pending"}
    ]
  }
}
```

## Few-shot examples

### Example 1: New topic, prior-art exists

Resolved Details:
- Topic: vision encoders for agents

Trajectory: `find_posts(query='vision encoders for agents')` → 2 related posts (Building User Simulators, Multi-modal Pipelines).

Final reply:
```json
{
  "freeform": "Two related posts already — let me summarize 'Multi-modal Pipelines' first, then we'll outline.",
  "structured": {
    "description": "Pre-draft research for 'vision encoders for agents'.",
    "sub_flows": [
      {"flow_name": "summarize", "slots": {"source": {"post": "ef012345"}}, "status": "pending"},
      {"flow_name": "outline",   "slots": {"topic": "vision encoders for agents"}, "status": "pending"}
    ]
  }
}
```
