---
name: "simplify"
description: "reduce complexity of a section or note; shorten paragraphs, simplify sentence structure, remove redundancy; image simplification means replacing with a simpler alternative or removing entirely"
version: 2
tools:
  - read_metadata
  - read_section
  - revise_content
  - remove_content
  - write_text
---

## Process

1. If the starter includes a `<section_content>` block, use it directly — it is the target section preloaded by the policy. Call `read_section(post_id, sec_id, include_sentence_ids=True)` when you need sentence indices to target a span; the returned content prepends each sentence with its 0-based index.
2. Identify the exact span the starter names — a sentence ("opening sentence"), a range of sentences ("second paragraph"), a whole section ("shorten this section"), or an image. Follow the Revise intent's scope discipline: narrowest interpretation wins when the user didn't specify.
3. Shorten sentences, reduce paragraph length, remove redundancy. **Preserve the meaning.**
4. Save via `revise_content`:
   a. For a single-sentence replacement, pass `snip_id=<index>` and `content=<the replacement sentence>`.
   b. For a range of sentences, pass `snip_id=[start, end]` (end-exclusive) and `content=<the replacement text>`.
   c. For a whole-section simplify, omit `snip_id` and pass the whole revised section as `content`.
   d. If `revise_content` fails, retry ONCE before returning the error JSON.

### Branching

- **Starter has `Source (section)` filled**: edit that section. Follow scope discipline inside the section — if the user named a sentence or a paragraph, pass `snip_id` scoped to those sentences; the tool replaces only that slice. For a whole-section simplify, omit `snip_id`.
- **Starter has `Image` filled with a clear operation verb** (replace, remove): carry it out via `revise_content` (replace) or `remove_content` (remove). Do NOT use `insert_media` — the image slot signals replace/remove, not insert.
- **Starter has `Image` filled but no operation verb**: reply with the `needs_clarification` JSON shape below and make NO tool calls. The policy surfaces this as a confirmation-level ambiguity.
- **Starter has `Guidance` filled**: treat as a soft preference. Honor it while keeping the primary goal (simplification) intact. Note trade-offs in the summary if the two conflict.

## Tools

- `read_section(post_id, sec_id, snip_id=None, include_sentence_ids=False)` — fallback when no `<section_content>` block was preloaded. Pass `include_sentence_ids=True` when you need sentence indices to target a span. Never edit a span you haven't read.
- `revise_content(post_id, sec_id, content, snip_id=None)` — save simplified content. Omit `snip_id` for a whole-section replace; pass an integer to target one sentence, or `[start, end]` (end-exclusive) to replace a range. This skill owns persistence. Retry once on failure.
- `remove_content(post_id, sec_id, target)` — remove an image or block outright. Only when the user explicitly asked to remove.

## Output

Reply with JSON in one of the shapes below.

Success:
```json
{
  "target": "<section or span name>",
  "before": "<the exact prior text of the edited span>",
  "after": "<the simplified text that was saved>",
  "summary": "<one sentence describing what you cut>"
}
```

Needs clarification:
```json
{
  "target": "<section or span name>",
  "needs_clarification": "<short sentence stating what's unclear>"
}
```

Error (retry exhausted):
```json
{
  "target": "<section or span name>",
  "error": "<reason>"
}
```

## Few-shot examples

### Example — paragraph simplification

Starter parameters:
- Source: post=abcd0123, section=breakthrough-ideas
- User asked: "The second paragraph of Breakthrough Ideas is too wordy. Cut a sentence or two."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=breakthrough-ideas, include_sentence_ids=True)` → section with sentence indices prepended so the skill can target them.
2. Paragraph 2 spans sentences 3-5. Rewrite them as two tighter sentences.
3. `revise_content(post_id=abcd0123, sec_id=breakthrough-ideas, content=<two tighter sentences>, snip_id=[3, 6])`.

Final reply:
```json
{
  "target": "Breakthrough Ideas — paragraph 2",
  "before": "We started experimenting with synthetic data generation by using large language models to produce training examples, which turned out to work surprisingly well because it let us sidestep the manual labelling bottleneck.",
  "after": "We used LLMs to generate training examples, sidestepping the labelling bottleneck.",
  "summary": "Collapsed two clauses into one; dropped the hedge 'surprisingly well'."
}
```

### Example — image, operation clear

Starter parameters:
- Image: process/hero
- User asked: "The hero image in Process is too complex. Replace it with something clearer."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=process)` → section with image reference.
2. `revise_content(post_id=abcd0123, sec_id=process, content=<section with simpler image reference>)`.

Final reply:
```json
{
  "target": "Process — image",
  "before": "<image type: hero; description: complex flowchart with 12 nodes>",
  "after": "<image type: hero; description: simplified 3-step flowchart>",
  "summary": "Replaced multi-node flowchart with three sequential steps."
}
```

### Example — image, operation unclear

Starter parameters:
- Image: process/hero
- User asked: "Simplify the image in the Process section."

No operation verb. Make NO tool calls.

Final reply:
```json
{
  "target": "Process — image",
  "needs_clarification": "replace with a simpler alternative, or remove the image entirely?"
}
```
