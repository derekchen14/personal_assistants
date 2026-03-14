# Skill: preview_published

Preview how a post will look when published.

## Behavior
- Use `post_get` to retrieve the full post content
- Use `content_format` to render a publication-ready preview
- If `channel` is specified, adapt the preview for that channel's format
- Show the preview with title, formatted body, metadata, and estimated read time
- Highlight any issues that should be fixed before publishing (missing images, broken links, etc.)
- Suggest `format_post` for fixes or `publish_post` to go live

## Slots
- `source` (required): The post (by title or ID) to preview
- `channel` (optional): Preview for a specific channel's format

## Output
A formatted preview of the post as it will appear when published.
