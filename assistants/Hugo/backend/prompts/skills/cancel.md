# Skill: cancel_publish

Cancel or unpublish a post.

## Behavior
- Use `post_get` to verify the post exists
- If published, explain the unpublish process
- If scheduled, cancel the scheduled publication
- Use `post_update` to update the post status
- If `reason` is provided, log it for reference

## Slots
- `post_id` (required): The post to cancel/unpublish
- `reason` (optional): Why the publication is being cancelled

## Output
Confirmation that the publication has been cancelled.
