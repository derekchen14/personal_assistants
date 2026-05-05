---
name: "polish"
description: "editing of a specific paragraph, sentence or phrase; improves word choice, tightens sentences, fixes transitions, and smooths flow without changing meaning or structure. The scope is within a single paragraph or image, not across the whole post"
version: 3
tools:
  - read_metadata
  - read_section
  - revise_content
---

This skill polishes a paragraph, sentence, or text snippet by rephrasing sentences, improving word choice, and fixing transitions. The main goal is to eliminate any signs of AI slop while preserving meaning and structure.

## Process

1. Find the target section and read it. Look at the user's utterance and the `<resolved_details>` block.
   a. Read the target section with `read_section(post_id, sec_id=<matched>, include_sentence_ids=True)`. The returned content prepends each sentence with its 0-based index so you can name spans reliably. Do not read any other section; polish scope is intentionally narrow.
   b. Identify the sentence or range of sentences the user named. When no span is named, polish the whole matched section.

2. Check the scratchpad and/or context coordinator for prior findings.
   a. When entries exist under the keys `audit`, `inspect`, or `check` read them to see if there is anything relevant for the current context.
   b. List the keys you used in the output JSON's `used` array. When you consumed nothing, set `used` to an empty array. Never list a key you did not actually use.

3. Polish the span: rephrase sentences, improve word choice, fix transitions, remove filler. 
   a. Preserve meaning and paragraph structure.
   b. When a style hint is provided in the resolved details, treat it as the priority signal over style inferred from the current prose; the user is saying the current style is not what they want.

4. Save with `revise_content(post_id, sec_id, content, snip_id=<int|[start, end]>)`. For whole-section polish, call it without `snip_id`. For a specific span, pass a start and end range for `snip_id` to replace the previous content.

## Handling Ambiguity and Errors

If the named span cannot be located within the section ("second paragraph" in a one-paragraph section), call `handle_ambiguity(level='specific', metadata={'missing': 'span', 'reason': 'invalid_value'})`.

**Default to CONFIRMATION when the user's direction is soft.** Soft directions name a goal but not specific edits — "flow better", "sound better", "clean it up", "punchier", "tighter", "smoother", "nicer". On a soft direction, do NOT polish directly. Instead, read the target span, decide on 2-3 concrete edits you'd consider, then call `handle_ambiguity(level='confirmation', metadata={'missing': 'polish_direction', 'question': '<concrete question listing the 2-3 specific edits as options the user can pick from or accept wholesale>'})`. The skill's job here is to surface the options, not to act on a guess.

Polish DIRECTLY (skip confirmation) only when the user named a concrete edit — e.g. "cut sentence 3", "replace passive voice with active in the second sentence", "add a transition between sentences 1 and 2". A specific edit is one a reader could verify against the prose without having to reinterpret the user's intent.

If the user's request implies substantive revision (expand, restructure, weave in suggestions) rather than word-level polish, emit a fallback to `rework`. If the request is about trimming or shortening, emit a fallback to `simplify`.

## Tools

### Task-specific tools

- `read_section(post_id, sec_id, snip_id=None, include_sentence_ids=False)` required once per turn on the matched section. Pass `include_sentence_ids=True` so the returned content carries sentence indices you can later hand back as `snip_id`.
- `revise_content(post_id, sec_id, content, snip_id=None)` is the primary save. Omit `snip_id` to replace the whole section. Pass an integer `snip_id` to insert at a sentence index (`-1` appends). Pass `[start, end]` to replace that end-exclusive slice of sentences. Compose the polished prose directly — preserve all technical content from the source span; only restructure phrasing and word choice.

### General tools

- `execution_error(violation, message)` for hard failures after retries.
- `handle_ambiguity(level, metadata)` for unclear or vague user intent.
- `manage_memory(action, key, value)` to read the scratchpad for prior findings
- `coordinate_context(lookback)` to look at conversation history going back to the beginning
- `call_flow_stack(action='read', details='flows')` to see what other flows are on the stack

## Few-shot examples

### Example 1: Soft direction → confirmation

Resolved Details:
- Source: post=abcd0123, section=architectures-of-the-past
- User asked: "Clean up the opening paragraph of Architectures of the Past — make it flow better."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=architectures-of-the-past, include_sentence_ids=True)` → opening paragraph spans sentences 0-2.
2. The direction "flow better" is soft — name three concrete fixes the prose actually invites:
   - merge sentences 0-1 to drop a redundant transition;
   - flip passive in sentence 1 ("was used by") to active;
   - tighten sentence 2 by replacing "the way that we" with "we".
3. `handle_ambiguity(level='confirmation', metadata={'missing': 'polish_direction', 'question': "Three options for flow: (1) merge sentences 0-1 to remove the redundant transition, (2) flip the passive voice in sentence 1 to active, (3) tighten sentence 2's 'the way that we' to 'we'. Pick any subset, or 'all three'."})`. End turn.

### Example 2: Specific edit → direct polish

Resolved Details:
- Source: post=abcd0123, section=the-need-for-data
- User asked: "Replace 'the way that we' with 'we' in the second sentence of the Need for Data section."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=the-need-for-data, include_sentence_ids=True)` → sentence 1 contains the phrase.
2. `revise_content(post_id=abcd0123, sec_id=the-need-for-data, content=<sentence 1 with 'the way that we' → 'we'>, snip_id=1)`.

### Example 3: Informed polish with an audit finding

Resolved Details:
- Source: post=abcd0123, section=the-need-for-data
- scratchpad['audit'] includes `{sec_id: the-need-for-data, severity: medium, note: 'passive voice departs from earlier published posts'}`.

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=the-need-for-data, include_sentence_ids=True)` → current prose.
2. Polish to active voice per the audit note.
3. `revise_content(post_id=abcd0123, sec_id=the-need-for-data, content=<polished prose>)`.

Final reply: lists `{used: ['audit']}`.

### Example 4: Fallback to rework

Resolved Details:
- Source: post=abcd0123, section=recent-innovations
- User asked: "Rewrite the whole Recent Innovations section, it needs a completely different argument."

Trajectory: no tool calls

Final reply: call_flow_stack(action='fallback', details='rework')
