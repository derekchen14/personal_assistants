# Skill: publish_post

Publish a post to the primary blog platform.

## Behavior
- Use `post_get` to verify the post exists and is ready
- Check that the post has a title, content, and is formatted
- Use `platform_publish` to publish to the primary blog platform
- If publication succeeds, update the post status via `post_update`
- If it fails, explain the error and suggest fixes
- After publishing, suggest `cross_post` for additional platforms

## Slots
- `post_id` (required): The post to publish

## Output
Confirmation of successful publication with a link if available.
