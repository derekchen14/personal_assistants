---
name: "endorse"
description: "accept Hugo's proactive suggestion and trigger the corresponding action; e.g., a recommended edit, topic idea, or next step that Hugo offered via suggest"
version: 2
---

This skill acknowledges the user accepting a previous suggestion. Confirm what action will follow, in 1 sentence.

## Process

1. Identify what's being endorsed from `<recent_conversation>` (the prior agent suggestion).
2. Reply with a brief confirmation that names the next action ("Got it — outlining now.").
3. The downstream flow that actually executes the endorsed action will be stacked by the policy or routed by NLU; this skill just narrates the transition.

## Error Handling

If the endorsement target is unclear (no prior agent suggestion in history), reply with a neutral acknowledgment and ask what action they want.

## Tools

### General tools

- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Endorse an outline suggestion

Recent conversation:
- Agent: "Want me to outline the post on simulators?"
- User: "Yes please."

Trajectory: `call_flow_stack(action='read', details='flows')` → confirms the prior turn queued an `outline` follow-up; reply narrates the transition.

Final reply:
```
On it — outlining now.
```
