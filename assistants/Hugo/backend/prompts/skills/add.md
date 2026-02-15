# Skill: add_section

Add a new section to an existing blog post.

## Behavior
- Determine where to insert the new section based on `position` slot
- Use `post_update` to add the section to the post structure
- Write a brief placeholder or full content depending on context
- Update the outline to reflect the new section

## Slots
- `title` (required): Title for the new section
- `position` (optional): Where to insert (beginning, end, after section X)

## Output
Confirmation of the added section with its position in the post.
