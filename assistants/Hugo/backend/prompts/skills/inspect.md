# Skill: inspect

Inspect a post and report its metrics.

## Behavior
1. Use `read_metadata` to load the post's title, status, and structure
2. Use `read_section` for each section to get content
3. Use `inspect_post` to compute word count, read time, section count, and readability
4. Use `check_readability` on individual sections if detailed analysis is needed
5. Use `check_links` to find and validate links and images
6. If `aspect` slot is filled, filter the report to that single metric
7. Present a clear summary of the post's current state

## Important
- While `read_metadata` can be used to get post IDs, the post title has been resolved for you within "Resolved entities". The mapping of section titles to section IDs can also be found there. You are encouraged to use these provided IDs rather than executing extra tool calls to get this information.

## Slots
- `source` (required): The post to inspect (by title or ID)
- `aspect` (optional): Specific metric to focus on (e.g., "readability", "links", "word count")

## Output
A metrics report with word count, read time, section count, readability score, and link status.
