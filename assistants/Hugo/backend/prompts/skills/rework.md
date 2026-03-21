# Skill: rework

Expand or restructure an entire section's prose — deeper development, not sentence-level edits.

## Behavior
1. Use `read_metadata` to load the post context and section IDs
2. Use `read_section` to load the target section's current content
3. Expand the section with richer detail, examples, or narrative per the user's instructions
4. Use `revise_content` to save the expanded version

## Important
- The policy saves the result automatically — just output the revised section text.
- Rework changes the substance and depth of a section, not just word choice.
- Preserve paragraph breaks and heading structure.
- While `read_metadata` can be used to get post IDs, the post title has been resolved for you within "Resolved entities". The mapping of section titles to section IDs can also be found there. You are encouraged to use these provided IDs rather than executing extra tool calls to get this information.

## Slots
- `source` (required): The post and section to rework
- `instructions` (optional): Specific guidance for the expansion

## Output
The expanded section text with notes on what was added.
