# Skill: cross_post

Cross-post content to a specific channel.

## Behavior
- Use `channel_list` to verify the target channel is connected
- If not connected, inform the user and suggest setting it up
- Use `post_get` to retrieve the post content
- Adapt the content format for the target channel if needed (e.g., thread for Twitter, shorter for LinkedIn)
- Use `release_post` with the target channel
- Report success or failure

## Slots
- `channel` (required): Target channel (medium, twitter, linkedin, etc.)
- `source` (optional): The post (by title or ID) to cross-post (uses most recent if not specified)

## Output
Confirmation of cross-posting with channel-specific details.
