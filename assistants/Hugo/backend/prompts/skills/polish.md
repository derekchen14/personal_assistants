# Skill: polish

Improve a section's prose for clarity, word choice, rhythm, and conciseness.

## Behavior
1. Use `read_metadata` to load the post context
2. Use `read_section` to load the target section's current content
3. Improve word choice, tighten sentences, fix transitions, and remove filler
4. Use `write_text` if you need to rewrite a passage
5. Use `find_and_replace` for targeted word/phrase swaps
6. Use `revise_content` to save the polished version

## Important
- The policy saves the result automatically — just output the revised section text.
- Do not change the meaning or structure — only improve the prose.
- Preserve paragraph breaks and heading structure.
- While `read_metadata` can be used to get post IDs, the post title has been resolved for you within "Resolved entities". The mapping of section titles to section IDs can also be found there. You are encouraged to use these provided IDs rather than executing extra tool calls to get this information.

## Slots
- `source` (required): The post and section to polish
- `style_notes` (optional): Specific style guidance

## Output
The polished section text with notes on key changes.
