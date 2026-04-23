---
name: "polish"
description: "editing of a specific paragraph, sentence or phrase; improves word choice, tightens sentences, fixes transitions, and smooths flow without changing meaning or structure. The scope is within a single paragraph or image, not across the whole post"
version: 3
tools:
  - read_metadata
  - read_section
  - write_text
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

If the named span cannot be located within the section ("second paragraph" in a one-paragraph section), call `handle_ambiguity(level='specific', metadata={'missing_reference': <span>})`.

If any resolved detail is vague enough that the polish direction would be a guess, call `handle_ambiguity(level='confirmation')`.

If the user's request implies substantive revision (expand, restructure, weave in suggestions) rather than word-level polish, emit a fallback to `rework`. If the request is about trimming or shortening, emit a fallback to `simplify`.

## Tools

### Task-specific tools

- `read_section(post_id, sec_id, snip_id=None, include_sentence_ids=False)` required once per turn on the matched section. Pass `include_sentence_ids=True` so the returned content carries sentence indices you can later hand back as `snip_id`.
- `write_text(prompt)` for calling an LLM to generate some examples. The tool returns prose; you should still save through `revise_content`.
- `revise_content(post_id, sec_id, content, snip_id=None)` is the primary save. Omit `snip_id` to replace the whole section. Pass an integer `snip_id` to insert at a sentence index (`-1` appends). Pass `[start, end]` to replace that end-exclusive slice of sentences.

### General tools

- `execution_error(violation, message)` for hard failures after retries.
- `handle_ambiguity(level, metadata)` for unclear or vague user intent.
- `manage_memory(action, key, value)` to read the scratchpad for prior findings
- `coordinate_context(lookback)` to look at conversation history going back to the beginning
- `call_flow_stack(action='read', details='flows')` to see what other flows are on the stack

## Few-shot examples

### Example 1: Basic polish on a named paragraph

Resolved Details:
- Source: post=abcd0123, section=architectures-of-the-past
- User asked: "Clean up the opening paragraph of Architectures of the Past."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=architectures-of-the-past, include_sentence_ids=True)` → current prose with sentence indices.
2. `revise_content(post_id=abcd0123, sec_id=architectures-of-the-past, content=<polished opening>, snip_id=[0, 3])` (sentences 0-2).

### Example 2: Informed polish with an audit finding

Resolved Details:
- Source: post=abcd0123, section=the-need-for-data
- scratchpad['audit'] includes `{sec_id: the-need-for-data, severity: medium, note: 'passive voice departs from earlier published posts'}`.

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=the-need-for-data, include_sentence_ids=True)` → current prose.
2. Polish to active voice per the audit note.
3. `revise_content(post_id=abcd0123, sec_id=the-need-for-data, content=<polished prose>)`.

Final reply: lists `{used: ['audit']}`.

### Example 3: Fallback to rework

Resolved Details:
- Source: post=abcd0123, section=recent-innovations
- User asked: "Rewrite the whole Recent Innovations section, it needs a completely different argument."

Trajectory: no tool calls

Final reply: call_flow_stack(action='fallback', details='rework')
