# Skill: diff_versions

Compare two versions of a post side by side.

## Behavior
- Use `post_get` to retrieve the post identified by `source`
- If `lookback` is set, compare the current version against that many versions ago (1=previous, 2=two ago)
- If `mapping` is set, compare the two content types specified (e.g. draft vs published)
- Use `diff_versions` to compute the differences
- Show a clear summary of what changed between versions
- Highlight additions, removals, and modifications

## Slots
- `source` (required): The post (by title or ID) to compare versions of
- `lookback` (elective): How many versions back to compare (1=previous, 2=two ago)
- `mapping` (elective): What to compare, as key-value (e.g. {"draft": "published"})

## Output
A comparison summary with highlighted changes and recommendations.
