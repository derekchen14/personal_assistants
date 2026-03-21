# Skill: summarize

Synthesize a post into a short paragraph capturing its core argument, audience, and takeaways.

## Behavior
- Use `post_get` to retrieve the full post content
- Produce a concise standalone paragraph covering: core argument, target audience, main takeaways
- Apply the length hint if provided (defaults to ~75 words)
- If the post is a stub with little content, summarize what exists and note it is incomplete
- If the post has no title, synthesize from content alone
- If length is very short (< 30 words), produce a one-sentence hook instead

## Slots
- `source` (required): The post to summarize
- `length` (optional): Target word count for the summary

## Output
A short summary paragraph suitable for excerpts, SEO descriptions, or pre-reads before writing a follow-up.
