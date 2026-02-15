# Skill: adjust_tone

Adjust the tone or style across a blog post.

## Behavior
- Use `post_get` to retrieve the current post
- If `tone` slot is provided, shift the writing toward that tone (e.g., casual, professional, witty, authoritative)
- If no tone specified, ask the user what tone they want
- Apply the tone adjustment consistently across all sections
- Use `content_generate` for the rewrite and `post_update` to save
- Preserve factual content and structure while changing voice
- Check memory for previously stored tone preferences

## Slots
- `tone` (elective): Target tone (casual, professional, witty, etc.)
- `post_id` (required): The post to adjust

## Output
The tone-adjusted content with a note on the changes applied.
