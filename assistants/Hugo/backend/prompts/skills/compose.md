# Skill: compose

Transform a section's outline bullets into polished prose paragraphs.

## Behavior
1. Use `read_metadata` with `include_outline: true` to get the post structure
2. Use `read_section` to load the target section's outline content
3. Use `convert_to_prose` to get an initial prose draft from the bullets
4. Use `write_text` to refine the prose if needed
5. Use `revise_content` to save the final prose to the section
6. Match the tone and style of existing sections in the post

## Important
- The policy saves the result automatically — just output the prose section text.
- Use the post title and surrounding sections for style consistency.
- While `read_metadata` can be used to get post IDs, the post title has been resolved for you within "Resolved entities". The mapping of section titles to section IDs can also be found there. You are encouraged to use these provided IDs rather than executing extra tool calls to get this information.

## Slots
- `source` (required): The post and section to compose (e.g., source.post + source.sec)
- `instructions` (optional): Specific instructions for the section

## Output
The composed prose section displayed as a card.
