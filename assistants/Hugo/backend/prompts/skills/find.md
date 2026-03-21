# Skill: find

Find posts, drafts, and notes matching the user's query.

## Behavior
- Use `find_posts` to search by keyword, tags, or status
- Expand the user's query with synonyms to improve recall (e.g., "travel" → also try "traveling", "trip")
- Deduplicate results by post_id before presenting
- If `count` slot is specified, limit results to that number
- Present results with title, status, and a brief relevance note

## Slots
- `topic` (required): Topic or keyword to search for
- `count` (optional): Max number of results

## Output
A list of matching posts with relevance descriptions.
