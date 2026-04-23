---
name: "preference"
description: "set a persistent writing preference stored in Memory Manager (L2); preferred tone, default post length, heading style, Oxford comma usage, or channel defaults"
version: 2
---

This skill confirms that a writing preference was saved. The policy has already extracted the key/value and persisted it; this skill narrates the result.

## Process

1. Read the saved key + value from `<resolved_details>` (the policy preloads the parsed setting).
2. Reply in 1 sentence confirming what was saved and how it will affect future writing.
3. Common preferences worth highlighting: word-count targets, heading style, paragraph length, vocabulary level, Oxford comma, channel defaults.

## Error Handling

If the key/value pair is incomplete or contradictory in `<resolved_details>`, call `handle_ambiguity(level='confirmation', observation='Got partial input — should I save just the key, or wait for the value?')`.

## Tools

### General tools

- `manage_memory(**params)` — fallback if the policy didn't already persist.
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Save a tone default

Resolved Details:
- Setting: tone = "conversational, second-person"

Trajectory: upstream `manage_memory(action='write', key='preference.tone', value='conversational, second-person')` already persisted the setting; the skill narrates the confirmation.

Final reply:
```
Saved — future drafts will default to a conversational, second-person tone unless you ask for something different.
```

### Example 2: Save a word-count target

Resolved Details:
- Setting: target_word_count = 1200

Final reply:
```
Locked in 1200 words as the target. I'll size new outlines and drafts around that.
```
