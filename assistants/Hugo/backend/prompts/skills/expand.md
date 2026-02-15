# Skill: expand_content

Expand an outline into full prose for a blog post.

## Behavior
- Use `post_get` to retrieve the current post and its outline
- If `section` slot is provided, expand only that section; otherwise expand all sections
- Write in the user's preferred tone (check memory for preferences)
- Use `content_generate` to produce the prose
- Use `post_update` to save the expanded content back to the post
- Maintain consistent voice across sections
- Include transitions between sections for flow

## Slots
- `post_id` (required): The post to expand
- `section` (optional): Specific section to expand

## Output
The expanded prose content displayed as a card.
