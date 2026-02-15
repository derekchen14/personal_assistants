# Skill: deep_revise

Major revision of draft content based on feedback or quality review.

## Behavior
- Use `post_get` to retrieve the current post
- If `section` is specified, focus revision there; otherwise review the full post
- Analyze for: clarity, flow, argument strength, engagement, readability
- Use `content_generate` to produce the revised content
- Use `post_update` to save the revision
- Explain what was changed and why
- Preserve the author's voice while improving quality

## Slots
- `post_id` (required): The post to revise
- `section` (optional): Specific section to focus on

## Output
The revised content with a summary of changes made.
