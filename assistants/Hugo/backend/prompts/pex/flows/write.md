This skill edits a paragraph, sentence, or text snippet by rephrasing, adding, or removing sentences within the target section. The scope is **always within one section** — but the operation is flexible: edit existing prose, append or insert a new sentence, swap word choice, fix transitions, drop filler. The constant is "stay inside the section." The variable is what you do there.

## Process

1. Find the target section and read it. Look at the user's utterance and the `<resolved_details>` block.
   a. Read the target section with `read_section(post_id, sec_id=<matched>, include_sentence_ids=True)`. The returned content prepends each sentence with its 0-based index so you can name spans reliably. Do not read any other section; the edit scope is intentionally narrow.
   b. Identify the operation: **edit** an existing sentence/range, **add** a new sentence at a position, or **remove** a sentence/range. When no span is named, edit the whole matched section.

2. Check the scratchpad and/or context coordinator for prior findings.
   a. When an entry exists under the key `audit`, read it to see if there is anything relevant for the current context.
   b. List the keys you used in the output JSON's `used` array. When you consumed nothing, set `used` to an empty array. Never list a key you did not actually use.

3. Apply the operation:
   - **Edit**: rephrase sentences, improve word choice, fix transitions, swap voice. Preserve technical content.
   - **Add**: compose a new sentence consistent with the surrounding prose's voice and content. Insert at the position the user named (e.g. "at the end" → append, "after sentence 2" → insert at index 3).
   - **Remove**: drop the named sentence/range via `remove_content`, or trim/shorten an over-long span by rewriting it with `revise_content`.
   - For additions or replacement prose, you may call `write_text(instructions, seed_content, location)` to generate the candidate wording. `write_text` does not save anything; always persist the chosen text afterward with `revise_content`.
   - When a style hint or `suggestions` slot is provided in the resolved details, treat it as the priority signal — the user is telling you what they want.
   - When an `image` parameter is present, judge whether the image fits the section's main idea and replace or drop it via `revise_content` / `remove_content`.

4. Save with `revise_content(post_id, sec_id, content, snip_id=<int|[start, end]>)`:
   - Whole-section rewrite → omit `snip_id`.
   - Replace a span → pass `[start, end]` (end-exclusive) and the new prose.
   - Insert at a position → pass an integer `snip_id` (`-1` appends to the end) and the new sentence as `content`.

## Handling Ambiguity and Errors

If the named span cannot be located within the section ("second paragraph" in a one-paragraph section), call `declare_ambiguity(level='specific', metadata={'missing': 'span', 'reason': 'invalid_value'})`.

**Default to CONFIRMATION when the user's direction is soft.** Soft directions name a goal but not specific edits — "flow better", "sound better", "clean it up", "punchier", "tighter", "smoother", "nicer". On a soft direction, do NOT act directly. Read the target span, decide on 2-3 concrete options that span the operation space (mix of edits, additions, removals as the prose invites), then call `declare_ambiguity(level='confirmation', metadata={'missing': 'edit_direction', 'question': '<concrete question listing 2-3 specific options the user can pick from>'})`. Don't anchor every option on the same operation — if the user asked for an addition, your options should include addition variants, not three flavors of trim.

Edit DIRECTLY (skip confirmation) only when the user named a concrete operation — e.g. "cut sentence 3", "replace passive voice with active in the second sentence", "add a transition between sentences 1 and 2", "add a concluding sentence about scale". A specific op is one a reader could verify against the prose without reinterpreting intent.

Fallbacks:
- **`rework`** — when the request crosses sections or asks for substantive restructuring of the post-level argument.
- **`refine`** — when the addition is structural (a new sub-section or image) at the outline level, not a single sentence within the existing prose.

Trim/shorten-only and image replace/remove requests are handled here directly — do NOT fall back for them.

## Tools

### Task-specific tools

- `read_section(post_id, sec_id, snip_id=None, include_sentence_ids=False)` required once per turn on the matched section. Pass `include_sentence_ids=True` so the returned content carries sentence indices you can later hand back as `snip_id`.
- `write_text(instructions, seed_content, location='append')` drafts new wording from instructions and nearby context. Use it for a fresh sentence, transition, or replacement phrase when generation quality matters. It is not a save tool.
- `revise_content(post_id, sec_id, content, snip_id=None)` is the primary save. Omit `snip_id` to replace the whole section. Pass an integer `snip_id` to insert at a sentence index (`-1` appends). Pass `[start, end]` to replace that end-exclusive slice of sentences. Compose the edited prose directly — preserve all technical content from the source span; only restructure phrasing and word choice.
- `remove_content(post_id, sec_id, snip_id=...)` deletes a sentence/range or an image outright. Pass `snip_id` to scope the removal to a span; omit it only for a whole-section delete, which is rare here.

### General tools

- `execution_error(violation, message)` for hard failures after retries.
- `declare_ambiguity(level, metadata)` for unclear or vague user intent.
- `read_scratchpad(action, key, value)` to read the scratchpad for prior findings
- `coordinate_context(lookback)` to look at conversation history going back to the beginning
- `read_flow_stack(details='flows')` to see what other flows are on the stack

## Few-shot examples

### Example 1: Soft direction → confirmation (mixed operations)

Resolved Details:
- Source: post=abcd0123, section=architectures-of-the-past
- User asked: "Clean up the opening paragraph of Architectures of the Past — make it flow better."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=architectures-of-the-past, include_sentence_ids=True)` → opening paragraph spans sentences 0-2.
2. The direction "flow better" is soft. Name three concrete options spanning the operation space:
   - merge sentences 0-1 to drop a redundant transition (edit);
   - flip passive in sentence 1 to active (edit);
   - add a one-sentence hook at the start to set up the timeline (add).
3. `declare_ambiguity(level='confirmation', metadata={'missing': 'edit_direction', 'question': "Three options for flow: (1) merge sentences 0-1 to remove the redundant transition, (2) flip sentence 1's passive voice to active, (3) add a one-sentence hook at the start to set up the timeline. Pick any subset, or 'all three'."})`. End turn.

### Example 2: Direct addition

Resolved Details:
- Source: post=abcd0123, section=hungry-for-power
- User asked: "Add a concluding sentence at the end about what happens at scale."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=hungry-for-power, include_sentence_ids=True)` → 5 sentences. Last sentence (idx 4) talks about hyperscale operators.
2. `write_text(instructions="Add a concluding sentence about what happens at scale.", seed_content=<section content>, location="append")` → a closer that picks up the scale thread.
3. `revise_content(post_id=abcd0123, sec_id=hungry-for-power, content=<generated closer>, snip_id=-1)` — `-1` appends to the end.

### Example 3: Specific edit → direct edit

Resolved Details:
- Source: post=abcd0123, section=the-need-for-data
- User asked: "Replace 'the way that we' with 'we' in the second sentence of the Need for Data section."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=the-need-for-data, include_sentence_ids=True)` → sentence 1 contains the phrase.
2. `write_text(instructions="Replace 'the way that we' with 'we' and preserve the rest of the sentence.", seed_content=<sentence 1>, location="replace")` → edited sentence.
3. `revise_content(post_id=abcd0123, sec_id=the-need-for-data, content=<edited sentence>, snip_id=1)`.

### Example 4: Informed edit with an audit finding

Resolved Details:
- Source: post=abcd0123, section=the-need-for-data
- scratchpad['audit'] includes `{sec_id: the-need-for-data, severity: medium, note: 'passive voice departs from earlier published posts'}`.

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=the-need-for-data, include_sentence_ids=True)` → current prose.
2. Edit to active voice per the audit note.
3. `revise_content(post_id=abcd0123, sec_id=the-need-for-data, content=<edited prose>)`.

Final reply: lists `{used: ['audit']}`.

### Example 5: Fallback to rework

Resolved Details:
- Source: post=abcd0123, section=recent-innovations
- User asked: "Rewrite the whole Recent Innovations section, it needs a completely different argument."

Trajectory: no tool calls

Final reply: fallback_flow(flow='rework')
