# Skill: publish_post

Publish a post to the primary blog channel.

## Behavior
- Use `post_get` to verify the post exists and is ready
- Check that the post has a title, content, and is formatted
- Use `channel_publish` to publish to the primary blog channel
- If publication succeeds, update the post status via `post_update`
- If it fails, explain the error and suggest fixes
- After publishing, suggest `cross_post` for additional channels

## Slots
- `source` (required): The post (by title or ID) to publish

## Output
Confirmation of successful publication with a link if available.
