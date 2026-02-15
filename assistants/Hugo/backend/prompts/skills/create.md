# Skill: create_post

Start a new blog post from scratch.

## Behavior
- Use `post_create` to initialize a new draft post with the given title
- If `topic` is provided, generate a brief initial outline
- Store the new post ID in scratchpad for reference
- Suggest next steps: `generate_outline` for structure, `brainstorm` for ideas, or `expand_content` to start writing directly

## Slots
- `title` (required): The post title
- `topic` (optional): Topic description for initial outline

## Output
Confirmation of the new post creation with post ID and next step suggestions.
