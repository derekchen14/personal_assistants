---
name: "outline"
description: "generate an outline including section headings, key bullet points, estimated word counts, and suggested reading order"
version: 3
stages:
  - propose
  - direct
tools:
  - find_posts
  - brainstorm_ideas
  - generate_outline
---

This skill describes how to generate a fresh outline for a post. You operate in one of two modes, signaled by the `stage` field in `<resolved_details>`: `propose` means produce three candidate outlines as options for the user to pick from; `direct` means to save the chosen outline via `generate_outline()`.

## Process

### Propose mode

1. Confirm that `stage='propose'` from `<resolved_details>`.
   a. Use the `<resolved_details>` block to see the post metadata.
   b. Do not call `read_metadata()` unless absolutely necessary.
2. Emit exactly 3 outline options as markdown unless instructed otherwise by the user. Use the strict format `### Option N` then `## <section title>` and a 1 to 2 sentence description per section. Each option should have 3-5 sections. No trailing commentary.
3. Do not call `generate_outline`. End the turn by returning the text you just wrote.

### Direct mode

1. Confirm that `stage='direct'` from `<resolved_details>`.
2. Read the section list from `<resolved_details>`. These are the sections of the outline.
3. Draft bullets per section honoring the depth value. Depth 2 is flat bullets. Depth 3 adds `### Sub-section` headings with bullets under each. Depth 4 goes further to `### Sub-section` + `- bullet` + `  * sub-bullet`.
4. Call `generate_outline(post_id, content=<markdown outline>)` to save. End the turn.

## Handling Ambiguity and Errors

If in propose mode you find yourself wanting to call `generate_outline`, stop: the user has not yet chosen an option. Re-emit the three options as text instead.

If in direct mode `generate_outline` fails, the policy will retry once automatically. A second failure surfaces as a `tool_error` frame; do not attempt a third call from the skill.

If the topic cannot be extracted from the conversation and no sections were supplied, call `handle_ambiguity(level='specific', metadata={'missing_slot': 'topic'})`.

## Tools

### Task-specific tools

- `generate_outline(post_id, content)` is for direct mode only, exactly once at the end of the turn. Pass the full markdown outline; the tool replaces any existing outline.
- `find_posts(query)` call this tool at most once to scan for existing posts on the topic. Use it to vary angles (propose) or to ground against prior work (direct). If it returns nothing, proceed without it.

### General tools

- `execution_error(violation, message)` for hard failures.
- `handle_ambiguity(level, metadata)` for cases where the user's request is genuinely unclear.
- `manage_memory(action, key, value)` to read or write session scratchpad and user preferences.
- `call_flow_stack(action='read')` to check whether a compose or refine is queued behind this outline so the generated bullets match what the next flow will consume.

## Output

### Propose mode

Markdown text with three options in this strict format:

```
### Option 1
## <section title>
One or two sentences describing what this section covers.

## <section title>
...

### Option 2
...

### Option 3
...
```

### Direct mode

After `generate_outline` saves, the final reply is a one-sentence acknowledgement ("Saved a 4-section outline for <title>."). The card block rendered by the policy carries the structured data.

## Few-shot examples

### Example 1: Propose on a fresh post

Resolved Details:
- stage: propose
- topic: "User Simulators for training RL agents"
- sections: []

Trajectory:
1. Emit three outline options with distinct angles (academic survey / engineering walkthrough / practitioner checklist). No tool calls.

### Example 2: Direct mode with user-named sections (depth defaults to 2)

Resolved Details:
- stage: direct
- sections: ["The Need for Data", "Architectures of the Past", "Recent Innovations", "Generating Rewards"]
- depth: (unfilled, defaults to 2)

Trajectory:
1. Draft sections and bullet points for each of the 4 sections
2. `generate_outline(post_id=abcd0123, content=<markdown with ## Section + bullets>)`.

### Example 3: Direct mode via propose-then-pick with depth 2

Resolved Details:
- stage: direct
- proposals: (user picked Option 2)
- depth: 3

Trajectory:
1. Take the sections from the chosen option.
2. Draft sub-sections and bullets per section.
3. `generate_outline(post_id=abcd0123, content=<markdown with ## Section + ### Sub-section + bullets>)`.
