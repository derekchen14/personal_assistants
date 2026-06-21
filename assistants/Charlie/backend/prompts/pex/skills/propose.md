---
name: "propose"
description: "generate 2-3 targeted alternatives to fill a placeholder gap in existing content, presented inline for the user to pick; like brainstorm but scoped to a specific slot in a draft"
version: 1
tools:
  - read_metadata
  - read_section
  - revise_content
---

This skill fills a placeholder gap — a `<fill in here>` marker, a `[TODO]`, or an obviously blank slot — inside ONE existing section. You generate **2-3 distinct alternatives yourself** and present them as plain text for the user to choose from. You do NOT write content with a tool during generation; the candidates are your own prose. The user's pick lands later, on a follow-up action turn, via `revise_content`.

## Process

1. Read the target section. From the user's utterance and the `<resolved_details>` block, identify the section and the gap inside it.
   a. `read_section(post_id, sec_id=<matched>, include_sentence_ids=True)` to load the surrounding prose so each alternative fits the voice and flows from what precedes the gap.
   b. Locate the placeholder (`<fill in here>`, `[TODO]`, an empty bullet, a trailing colon with nothing after it). If no gap is obvious, ask (see Ambiguity).

2. Generate 2-3 alternatives that genuinely differ — vary the angle, length, or emphasis, not just the wording. Each must be a drop-in replacement for the gap that reads naturally in context. Keep them tight: the user is picking a direction, not editing an essay.

3. Present them as your text response, one per line, numbered. Do NOT call a write tool — the policy renders your lines as a clickable selection and inserts the user's choice via `revise_content` on the next turn.

## Handling Ambiguity and Errors

- If you cannot find a gap in the section, call `handle_ambiguity(level='specific', metadata={'missing': 'gap', 'reason': 'unclear_value'})` and name what you looked for.
- If the section itself can't be located, call `handle_ambiguity(level='partial', metadata={'missing': 'source', 'entity': 'section'})`.

## Tools

### Task-specific tools

- `read_metadata(post_id, include_outline=True)` to see the section list when the gap's location is described loosely.
- `read_section(post_id, sec_id, include_sentence_ids=True)` is required — the surrounding prose anchors the alternatives.
- `revise_content(post_id, sec_id, content, snip_id=None)` is NOT called during generation; it lands the user's pick on the follow-up turn.

### General tools

- `handle_ambiguity(level, metadata)` when the gap or section is unclear.
- `coordinate_context(lookback)` to pull earlier conversation if the gap references it.

## Few-shot examples

### Example 1: Fill a marked gap

Resolved Details:
- Source: post=abcd0123, section=the-tradeoffs
- User asked: "Fill in the `<fill in here>` in the Tradeoffs section."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=the-tradeoffs, include_sentence_ids=True)` → the gap sits right after a sentence introducing latency costs.
2. Generate three drop-in alternatives, each completing the thought from a different angle (cost, reliability, developer experience).

Final reply (no write tool — the policy turns these into a selection):
1. "...but the latency tax compounds: every hop adds milliseconds the user feels."
2. "...yet the bigger cost is operational — each new service is another pager rotation."
3. "...though the real friction is for developers, who now debug across three boundaries instead of one."
