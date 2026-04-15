# Skill: polish

Improve the prose of a **specific target** — a paragraph, sentence, or named span — for clarity, word choice, rhythm, and conciseness. Do not change meaning or structure.

## Behavior
1. **Find the target section.** Look at the user's utterance for a section name (e.g. "Motivation", "Process"). Match it to the `section_ids` list in `Resolved entities`. That single matched id is your target — ignore every other section.
2. **Read only the target section.** `read_section(post_id=..., sec_id=<matched>)`. Do NOT read any other section first; you do not need surrounding context to polish one span.
3. Identify the exact span inside that section (opening paragraph, specific sentence, transition). Polish only that span.
4. Tighten sentences, improve word choice, fix transitions, remove filler — preserve the meaning and paragraph structure.
5. Use `find_and_replace` for targeted word/phrase swaps; `write_text` if a sentence needs a full rewrite.
6. Use `revise_content(post_id=..., sec_id=<matched>, content=<whole section with only your polished span changed>)` to save.

## Scope discipline
- "Tighten the opening paragraph of Motivation" → polish only the first paragraph of the Motivation section. All later paragraphs stay exactly as they were.
- "Clean up the transitions in the intro" → polish the sentences that join paragraphs in the intro. Interior sentences stay.
- If the user names a section but not a span, polish the whole section.
- Never polish a section you did not `read_section` first.

## Output
Respond with **JSON** in this shape:

```json
{
  "target": "Motivation — opening paragraph",
  "before": "<the exact prior text of the edited span>",
  "after": "<the polished text that was saved>",
  "changes": ["<short description>", "<short description>"]
}
```

## Few-shot example

User: "Tighten the opening paragraph of the Motivation section — make it punchier."

Correct tool trajectory:
1. `read_section(post_id=..., sec_id='motivation')` → returns the full Motivation section.
2. Extract the first paragraph.
3. `revise_content(post_id=..., sec_id='motivation', content=<whole section with only para 1 polished>)`.

Correct final reply:
```json
{
  "target": "Motivation — opening paragraph",
  "before": "In our experience building an intent classification chatbot, we ran into the classic problem that manual labelling is extremely slow and expensive, which made it hard for us to iterate on the model as quickly as we wanted.",
  "after": "Building our intent classification chatbot, we hit the labelling wall: slow, expensive, and a brake on iteration.",
  "changes": ["Traded the long introductory clause for a punchy lead", "Collapsed 'slow and expensive' with the consequence into a single image"]
}
```

## Slots
- `source` (required): The post and section to polish. Includes `post` and `sec`.
- `style_notes` (optional): Specific style guidance (e.g. "punchier", "more formal").

## Important
- **Read only the section you are going to edit.** Reading every section first is a common wrong pattern — it wastes tool calls and dilutes attention. One `read_section` on the matched target, then edit, then save.
- The policy saves the result automatically once `revise_content` succeeds.
- Preserve headings, paragraph breaks, and list structures.
- `Resolved entities` gives you `post_id` and section IDs — use them instead of extra `read_metadata` calls.
- Do not change meaning; do not restructure. If the span needs restructuring, use `rework` instead.
