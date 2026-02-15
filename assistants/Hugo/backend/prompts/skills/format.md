# Skill: format_post

Format a blog post for publication.

## Behavior
- Use `post_get` to retrieve the current post
- Apply formatting: headings, subheadings, bullet points, blockquotes, code blocks as appropriate
- If `format` slot specifies a style (markdown, html, plain), format accordingly
- Use `content_format` to apply the formatting
- Use `post_update` to save the formatted version
- Add meta elements if missing: title tag, excerpt, categories
- Suggest `publish_post` or `preview_published` as next steps

## Slots
- `post_id` (required): The post to format
- `format` (elective): Target format style (markdown, html, plain)

## Output
The formatted post content displayed as a card.
