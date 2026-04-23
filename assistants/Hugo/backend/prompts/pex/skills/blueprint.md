---
name: "blueprint"
description: "plan the full post creation workflow from idea to publication; orchestrates Research, Draft, Revise, and Publish flows into a sequenced checklist with dependencies"
version: 2
---

This skill produces the orchestration plan for a full post lifecycle. The output drives `_plan_lifecycle` in PlanPolicy: the JSON `sub_flows` array is what gets pushed onto the flow stack one at a time.

## Process

1. Read the optional `topic` from `<resolved_details>` and the conversation history.
2. Decompose the lifecycle into ordered sub_flows. Standard sequence: `find` (or `inspect` if the user named an existing post) → `outline` → `compose` → `polish` → `release`. Insert `audit` before polish when the user wants quality gating.
3. For each sub_flow, populate the slot values you can pre-fill (e.g. `outline.topic` from the user's topic).
4. Skip steps the user can confidently bypass (e.g. skip `find` when they already named a post).
5. Emit the dual-output JSON described under Output.

## Error Handling

If the topic is too vague to plan against (one-word and no context), call `handle_ambiguity(level='specific', metadata={'missing_slot': 'topic'})`.

If a referenced sibling flow doesn't exist in the registry, call `execution_error(violation='invalid_input', message='unknown sub_flow <name>')`.

## Tools

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Output

JSON with two top-level keys: `freeform` (1-sentence prose for the user) and `structured` (the plan):

```json
{
  "freeform": "I'll outline, draft, polish, then publish.",
  "structured": {
    "description": "Full lifecycle for a new post on multi-modal agents.",
    "sub_flows": [
      {"flow_name": "outline", "slots": {"topic": "multi-modal agents"}, "status": "pending"},
      {"flow_name": "compose", "slots": {}, "status": "pending"},
      {"flow_name": "polish",  "slots": {}, "status": "pending"},
      {"flow_name": "release", "slots": {}, "status": "pending"}
    ],
    "ambiguities": [],
    "tool_calls": [],
    "verification": []
  }
}
```

## Few-shot examples

### Example 1: Fresh topic, full lifecycle

Resolved Details:
- Topic: multi-modal agents

Trajectory: `call_flow_stack(action='read', details='flows')` → confirms no in-progress lifecycle for this topic; the blueprint queues a fresh one.

Final reply:
```json
{
  "freeform": "I'll outline, draft, audit, polish, and release.",
  "structured": {
    "description": "Full post lifecycle for 'multi-modal agents'.",
    "sub_flows": [
      {"flow_name": "outline", "slots": {"topic": "multi-modal agents"}, "status": "pending"},
      {"flow_name": "compose", "slots": {}, "status": "pending"},
      {"flow_name": "audit",   "slots": {}, "status": "pending"},
      {"flow_name": "polish",  "slots": {}, "status": "pending"},
      {"flow_name": "release", "slots": {}, "status": "pending"}
    ]
  }
}
```
