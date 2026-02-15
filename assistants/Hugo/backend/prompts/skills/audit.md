# Skill: check_consistency

Check consistency of a post with the user's previous writing.

## Behavior
- Use `post_get` to retrieve the target post
- Use `post_search` to find previous posts for comparison
- If `reference_count` is provided, compare against that many posts
- Check: tone consistency, terminology, formatting patterns, voice
- Report inconsistencies and suggest fixes

## Slots
- `post_id` (required): The post to check
- `reference_count` (optional): How many previous posts to compare against

## Output
A consistency report with specific findings and suggestions.
