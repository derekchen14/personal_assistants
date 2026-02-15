# Skill: cross_post

Cross-post content to a specific platform.

## Behavior
- Use `platform_list` to verify the target platform is connected
- If not connected, inform the user and suggest setting it up
- Use `post_get` to retrieve the post content
- Adapt the content format for the target platform if needed (e.g., thread for Twitter, shorter for LinkedIn)
- Use `platform_publish` with the target platform
- Report success or failure

## Slots
- `platform` (required): Target platform (medium, twitter, linkedin, etc.)
- `post_id` (optional): The post to cross-post (uses most recent if not specified)

## Output
Confirmation of cross-posting with platform-specific details.
