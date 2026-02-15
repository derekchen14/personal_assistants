# Skill: search_posts

Search existing blog posts by keyword or topic.

## Behavior
- Use `post_search` with the user's query to find matching posts
- Present results with title, status, and a brief excerpt
- If no results found, suggest broadening the search or browsing topics
- If `count` slot is provided, limit results accordingly (default: 5)

## Slots
- `query` (required): Search keyword or phrase
- `count` (optional): Max number of results to return

## Output
A list of matching posts with title, status, and excerpt.
