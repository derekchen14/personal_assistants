# Skill: simplify

Reduce the complexity of a section, paragraph, or image.

## Behavior
1. Use `read_metadata` to load the post context
2. Use `read_section` to load the target section's content
3. For text: shorten sentences, reduce paragraph length, remove redundancy — preserve meaning
4. For images (when `image` slot is filled): propose a simpler alternative or removal
5. Use `revise_content` to save the simplified version
6. Use `remove_content` to strip unnecessary sections or lines
7. Use `write_text` if a passage needs to be fully rewritten simpler

## Important
- The policy saves the result automatically — just output the simplified section text.
- While `read_metadata` can be used to get post IDs, the post title has been resolved for you within "Resolved entities". The mapping of section titles to section IDs can also be found there. You are encouraged to use these provided IDs rather than executing extra tool calls to get this information.

## Slots
- `source` (required): Section or note to simplify
- `image` (elective): Image to simplify or remove

## Output
The simplified content with a brief explanation of what was reduced.
