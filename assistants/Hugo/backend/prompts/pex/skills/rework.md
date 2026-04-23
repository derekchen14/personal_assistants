---
name: "rework"
description: "major revision of draft content; restructures arguments, replaces weak sections, addresses reviewer comments. Scope can go across the whole post, or an entire section. For smaller changes, use polish instead"
version: 3
tools:
  - read_metadata
  - read_section
  - revise_content
  - insert_section
  - remove_content
---

This skill describes how to rework a blog post. While typically scoped to a single section, rework can also go across the whole post when changes are broad. Rework is substantive revision that restructures arguments, replaces weak content with stronger alternatives, or weaves in user suggestions. The target section's current prose is preloaded in the `<section_content>` block, so use it directly as your starting point.

## Process

1. Read the user's guidance from the `<resolved_details>` block. At least one of `changes`, `suggestions`, or `remove` will be filled, and possibly more than one.
   a. Focus on the user's latest utterance in `<recent_conversation>`. Prior turns serve as context only, and should not be acted upon.
   b. Never act on requests from prior turns. Those have already been handled.

2. Use the `<post_preview>` block as your starting view — it lists every section (title + first few lines). This is always available; you never need to call `read_metadata`.
   a. When the rework touches a single section, pull its full prose with `read_section(post_id, sec_id)` before editing.
   b. When the rework is structural (swap, reorder, move material across sections), `read_section` each target to capture current prose — you'll rebuild around it.
   c. The post_id, source section ids, and target section ids are pre-resolved in `<resolved_details>`; don't call `read_metadata`.

3. Apply the user's request in a deliberate order, one section at a time with `revise_content(post_id, sec_id, content=<reworked prose>)`:
   a. When `suggestions` is filled, address each item one at a time. Make the reasoning visible in the revised prose. A suggestion should change the section's argument or structure, not just swap a word.
   b. When `changes` is filled, apply the broader critique on top of the suggestions. Shape the prose to honor the critique while preserving the author's voice and cadence.
   c. When `remove` is filled, excise the named material. A concrete `remove` (a named paragraph, a specific argument) can be cut directly. A vague `remove` ("anything outdated", "whatever feels off") requires emitting the needs-clarification output shape; do not save.
   d. When the change is structural (swap two sections, reorder, move material across sections), use the full choreography: `read_section` each target to capture current prose → `remove_content` to cut → `insert_section` to re-insert at the new position with smoothed transitions → `revise_content` on adjacent sections to update their outgoing transitions. See Example 4.

## Handling Ambiguity and Errors

A `remove` that names a concrete span is actionable; a vague one ("anything outdated") is not. Emit the ambiguity with a 'specific' level of clarification and make no tool calls.

If `revise_content` fails twice, the policy will emit a `failed_to_save` error frame. Do not attempt a third call from the skill. Treat this as an error.

If the user's request reads as Polish (sentence cleanup, improved wording) or Simplify (trimming text) rather than Rework, emit the call_flow_stack(action='fallback'), while naming the correct flow. The policy re-routes through the flow stack.

## Tools

### Task-specific tools

- `revise_content(post_id, sec_id, content)` is the primary save for rework. The tool replaces the section's content wholesale with the prose you pass in, so include the full reworked section rather than the changed paragraphs alone. Retry once on transient failure.
- `remove_content(post_id, sec_id, target)` is for the narrower case where the section is mostly fine except for one identified piece. For "excise X and replace with Y", prefer a single `revise_content` with the updated prose in one call.
- `insert_section(post_id, after_sec, title)` is for adding a brand-new section when the rework genuinely needs one. The `after_sec` parameter anchors the new section's position; pass the id of the section that should come before it.

### General tools

- `execution_error(violation, message)` for hard failures after retries.
- `handle_ambiguity(level, metadata)` for genuinely unclear user intent.
- `manage_memory(action, key, value)` to read the audit scratchpad when prior findings exist for this section.
- `call_flow_stack(action='read', details='flows')` to see what flow follows rework, which sometimes informs whether to leave breadcrumbs for a subsequent polish.

## Output

Success (saved):
```json
{
  "target": "<section id>",
  "summary": "<one line describing what you did>",
  "added": ["<details>", "<details>"],
  "done": ["<suggestion name>", ...]
}
```

Needs clarification (vague `remove`):
```json
{
  "target": "<section name>",
  "needs_clarification": "remove target is vague, which specific content should be cut?"
}
```

Fallback (wrong flow):
```json
{
  "action": "fallback",
  "flow": "polish" | "simplify" | "remove",
  "reason": "<one line>"
}
```

## Few-shot examples

### Example 1: Expand with prose guidance

Resolved Details:
- Source: post=abcd0123, section=the-need-for-data
- Changes: "Flesh out the customer story about the medical transcription chatbot."

Trajectory:
1. Use the preloaded `<section_content>` of The Need for Data as the starting point.
2. `revise_content(post_id=abcd0123, sec_id=the-need-for-data, content=<expanded prose>)`.
3. Resolved details includes 'changes' rather than 'suggestions', so "done" key is not needed

Final reply:
```json
{
  "target": "the-need-for-data",
  "summary": "Four paragraphs with the medical-chatbot project, the labelling bottleneck, and the pivot to synthetic data.",
  "added": [
    "Concrete customer story (medical transcription chatbot)",
    "Specific pain point: 8 weeks per intent batch with three labellers",
    "Pivot moment: noticed labellers paraphrasing each other"
  ]
}
```

### Example 2: Process a suggestions list

Resolved Details:
- Source: post=abcd0123, section=recent-innovations
- suggestions: [explain_transformer_choice, add_timeline, describe_error_cases]

Trajectory:
1. Read the preloaded section content.
2. `revise_content(post_id=abcd0123, sec_id=recent-innovations, content=<revised prose with all 3 suggestions woven in>)`.

Final reply:
```json
{
  "target": "recent-innovations",
  "summary": "Rewrote Recent Innovations so the three suggestions land in order: why transformers, how the six-month build played out, and which failure modes we ran into.",
  "added": [
    "Rationale for transformers over LSTM-based simulators: long-context attention handles sparse reward signals across many turns",
    "Timeline: 6-week prototype on a single domain, 4-week generalization pass, 3-week eval-harness buildout",
    "Error cases: hallucinated actions that pass static checks, reward-hacking loops on under-specified goals, simulator-reality gap on mouse-input timings"
  ],
  "done": ["explain_transformer_choice", "add_timeline", "describe_error_cases"]
}
```

### Example 3: Vague removal request

Resolved Details:
- Source: post=abcd0123, section=architectures-of-the-past
- remove: "anything that feels outdated"

Trajectory: no tool calls.

Final reply:
```json
{
  "target": "architectures-of-the-past",
  "needs_clarification": "What does it mean for something to be outdated?"
}
```

### Example 4: Swap two sections and smooth the transitions

Resolved Details:
- Source: post=abcd0123 (whole-post scope; `<post_preview>` shows Motivation, Process, Ideas, Takeaways with first lines of each)
- changes: "Swap the order of Process and Ideas, and smooth the transition sentences so it still reads cleanly."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=process)` → current Process prose.
2. `read_section(post_id=abcd0123, sec_id=ideas)` → current Ideas prose.
3. `remove_content(post_id=abcd0123, sec_id=process)` — cut Process from its current slot.
4. `insert_section(post_id=abcd0123, sec_id=ideas, section_title='Process', content=<Process prose with the opening paragraph rewritten to flow from Ideas>)` — re-inserts Process after Ideas.
5. `revise_content(post_id=abcd0123, sec_id=ideas, content=<Ideas with its closing paragraph rewritten to hand off to Process>)` — smooth the outgoing transition.

Final reply:
```json
{
  "target": "whole-post",
  "summary": "Swapped Process and Ideas. New order: Motivation → Ideas → Process → Takeaways. Rewrote two transition paragraphs (Ideas outro, Process intro).",
  "added": [
    "Ideas now closes with a bridge into Process: 'With the direction set, the question becomes how to build it.'",
    "Process now opens where Ideas left off: 'Given those ideas, the implementation breaks down as follows.'"
  ]
}
```
