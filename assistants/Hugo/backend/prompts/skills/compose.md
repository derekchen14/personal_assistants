# Skill: write_section

Write or rewrite a specific section of a blog post.

## Behavior
- Focus on the specified section only — don't modify other sections
- If `instructions` are provided, follow them closely
- Use `content_generate` to produce the section content
- Use `post_update` to save the section back to the post
- Match the tone and style of existing sections in the post
- Check memory for any writing preferences

## Slots
- `section` (required): Which section to write
- `instructions` (optional): Specific instructions for the section

## Output
The written section content displayed as a card.
