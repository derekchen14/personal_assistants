# Skill: add_section

Add a new section to an existing blog post.

## Behavior
1. Use `read_metadata` to load the post structure and current section IDs
2. Use `insert_section` to add the new section at the specified position
3. If no position is given, append at the end (before the last section)
4. The new section starts with a `## Heading` and empty content

## Important
- While `read_metadata` can be used to get post IDs, the post title has been resolved for you within "Resolved entities". The mapping of section titles to section IDs can also be found there. You are encouraged to use these provided IDs rather than executing extra tool calls to get this information.

## Slots
- `title` (required): Title for the new section
- `position` (optional): Where to insert (beginning, end, after section X)

## Output
Confirmation of the added section with its position in the post.
