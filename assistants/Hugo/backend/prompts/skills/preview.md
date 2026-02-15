# Skill: preview_published

Preview how a post will look when published.

## Behavior
- Use `post_get` to retrieve the full post content
- Use `content_format` to render a publication-ready preview
- If `platform` is specified, adapt the preview for that platform's format
- Show the preview with title, formatted body, metadata, and estimated read time
- Highlight any issues that should be fixed before publishing (missing images, broken links, etc.)
- Suggest `format_post` for fixes or `publish_post` to go live

## Slots
- `post_id` (required): The post to preview
- `platform` (optional): Preview for a specific platform's format

## Output
A formatted preview of the post as it will appear when published.
