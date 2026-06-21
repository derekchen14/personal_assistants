---
name: "dismiss"
description: "decline Hugo's proactive suggestion without providing feedback; Hugo notes the preference and moves on without further prompting"
version: 2
---

This skill acknowledges the user dismissing a previous suggestion. Reply briefly, note the dismissal in scratchpad so similar suggestions don't repeat, and offer something else.

## Process

1. Identify what's being dismissed from `<recent_conversation>` (usually the prior agent turn).
2. Reply in 1 sentence — neutral acknowledgment, no defensiveness.
3. Optionally offer one alternative ("Want me to do X instead?").
4. Write a small scratchpad entry under `dismiss` so future `suggest` flows can avoid the same recommendation.

## Error Handling

If the dismissal target is unclear (no prior agent suggestion in history), reply with a generic acknowledgment and skip the scratchpad write.

## Tools

### General tools

- `manage_memory(**params)` — write the dismissal note.
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Dismiss a topic suggestion

Recent conversation:
- Agent: "Want me to brainstorm follow-ups on the simulators post?"
- User: "No thanks."

Trajectory: `manage_memory(action='write', key='dismiss', value={'suggestion': 'simulators_followups'})` → noted so future suggest flows skip this branch.

Final reply:
```
Got it. Want me to look at something else, or are we done for now?
```
