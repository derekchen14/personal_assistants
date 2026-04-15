# Skill: simplify

Reduce the complexity of a **specific target** — a paragraph, a section, or an image — without expanding scope.

## Behavior
1. `read_metadata` to confirm the post structure if `Resolved entities` doesn't already give you the section IDs.
2. **Always** `read_section` on the target section BEFORE editing. Never write without reading.
3. Identify the exact span the user named (e.g. "second paragraph", "opening sentence"). If the user named a paragraph, edit only that paragraph — do NOT touch neighbouring paragraphs.
4. Shorten sentences, reduce paragraph length, remove redundancy. **Preserve the meaning.**
5. Use `revise_content` to save the simplified version back to the section.
6. For images (when `image` slot is filled): propose a simpler alternative or removal.

## Scope discipline
- "The second paragraph is too wordy" → edit the second paragraph only. Paragraphs 1 and 3 stay exactly as they were.
- "Shorten this section" (no paragraph named) → edit the whole section.
- If unclear whether the user means a single paragraph or the whole section, edit only the narrowest interpretation and note that the rest was left alone.

## Output
Respond with **JSON** in this shape:

```json
{
  "target": "Breakthrough Ideas — paragraph 2",
  "before": "<the exact prior text of the edited span>",
  "after": "<the simplified text that was saved>",
  "summary": "<one sentence describing what you cut>"
}
```

## Few-shot example

User: "The second paragraph of Breakthrough Ideas is too wordy. Cut a sentence or two."

Correct tool trajectory:
1. `read_section(post_id=..., sec_id='breakthrough-ideas')` → reads the full section.
2. Identify paragraph 2 inside the returned content.
3. `revise_content(post_id=..., sec_id='breakthrough-ideas', content=<whole section with only paragraph 2 simplified>)`.

Correct final reply:
```json
{
  "target": "Breakthrough Ideas — paragraph 2",
  "before": "We started experimenting with synthetic data generation by using large language models to produce training examples, which turned out to work surprisingly well because it let us sidestep the manual labelling bottleneck that had been slowing us down.",
  "after": "We used LLMs to generate training examples, sidestepping the labelling bottleneck.",
  "summary": "Collapsed two clauses into one; dropped the hedge 'surprisingly well'."
}
```

## Slots
- `source` (required): Section or note to simplify. Includes `post` and `sec`.
- `image` (elective): Image to simplify or remove.

## Important
- The policy saves the result automatically once `revise_content` succeeds.
- `Resolved entities` gives you `post_id` and section IDs — use them instead of extra `read_metadata` calls.
- Never edit a span you did not read. Never edit spans outside what the user named.
