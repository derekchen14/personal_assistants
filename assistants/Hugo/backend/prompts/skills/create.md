# Skill: create_post

Start a new blog post or note from scratch.

## Behavior
- Use `post_create` to initialize a new post with the given title
- Pass the `type` slot value ("draft" or "note") to `post_create` as the `type` parameter — do NOT default to draft if the user asked for a note
- If `topic` is provided, generate a brief initial outline
- Store the new post ID in scratchpad for reference
- Suggest next steps: `generate_outline` for structure, `brainstorm` for ideas, or `expand_content` to start writing directly

## Slots
- `title` (required): The post title
- `type` (required): "draft" for a full blog post, "note" for a shorter snippet
- `topic` (optional): Topic description for initial outline

## Output
Confirmation of the new post/note creation with post ID and next step suggestions.
