# Skill: audit

Audit a post for voice and style consistency against the user's previous writing.

## Behavior
1. Use `find_posts` to locate reference posts for comparison
2. Use `compare_style` to compare the target post's metrics against references
3. Use `editor_review` to check the post content against the editorial style guide
4. Use `inspect_post` to get structural metrics
5. Flag inconsistencies in tone, terminology, formatting, and voice
6. Report sections_affected count so the policy can check the threshold

## Important
- This is read-only — the policy handles threshold confirmation before any edits.
- If `reference_count` slot is filled, compare against that many posts.
- The post title has been resolved for you within "Resolved entities". You are encouraged to use the provided `post_id` rather than executing extra tool calls to resolve it.

## Slots
- `source` (required): The post to audit (by title or ID)
- `reference_count` (optional): How many previous posts to compare against
- `threshold` (optional): Percentage threshold for flagging (default 0.2)

## Output
A consistency report with specific findings, sections affected, and suggestions.
