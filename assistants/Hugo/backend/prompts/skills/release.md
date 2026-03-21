# Skill: release

Publish a post to a specific platform channel.

## Behavior
1. Use `read_metadata` to verify the post exists and is in draft status
2. Use `channel_status` to verify the target channel is connected and available
3. Use `release_post` to publish to the specified platform
4. Use `update_post` to flip the post status to "published" on success
5. If publication fails, explain the error and suggest fixes

## Important
- The policy flips post status to published automatically after success.
- Verify draft status before attempting release.
- While `read_metadata` can be used to get post IDs, the post title has been resolved for you within "Resolved entities". The mapping of section titles to section IDs can also be found there. You are encouraged to use these provided IDs rather than executing extra tool calls to get this information.

## Slots
- `source` (required): The post to publish (by title or ID)
- `channel` (required): The platform channel to publish to

## Output
Confirmation of successful publication with platform details.
