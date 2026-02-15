# Skill: view_post

View a specific post or draft in detail.

## Behavior
- Use `post_get` with the provided `post_id` to retrieve the post
- Display the full content including title, sections, status, and metadata
- Store the post content in scratchpad for reference in subsequent turns
- If the post has issues or is incomplete, mention what could be improved
- Suggest relevant next actions based on the post's status (draft → revise, ready → publish)

## Slots
- `post_id` (required): The ID of the post to view

## Output
The full post content displayed as a card with title, body, and metadata.
