# Skill: create_post

Start a new blog post or note from scratch.

## Behavior
- Use `post_create` to initialize a new post with the given title:
  * should be in `Proper Case`, rather than `lower case`
  * should be concise and catchy, rather than copying the user's input verbatim
- Pass the `type` slot value ("draft" or "note") to `post_create` as the `type` parameter — do NOT default to draft if the user asked for a note
- If `topic` is provided, generate a brief initial outline
- Store the new post ID in scratchpad for reference
- Suggest next steps: `generate_outline` for structure, `brainstorm` for ideas, or `expand_content` to start writing directly

## Slots
- `title` (required): The post title
- `type` (required): "draft" for a full blog post, "note" for a shorter snippet
- `topic` (optional): Topic description for initial outline

## Output
Respond with **JSON** in this shape:

```json
{
  "post_id": "...",
  "title": "...",
  "type": "draft" | "note",
  "next_steps": ["outline", "brainstorm", "compose"]
}
```

## Few-shot examples

User: "I want to make a new draft about synthetic data generation for classification tasks. Can you set it up?"

Correct tool trajectory:
1. `create_post(title='Synthetic Data Generation for Classification', type='draft')` → returns `{post_id: 'abc123'}`.

Correct final reply:
```json
{
  "post_id": "abc123",
  "title": "Synthetic Data Generation for Classification",
  "type": "draft",
  "next_steps": ["outline", "brainstorm"]
}
```

User: "I just learned about a whole bunch of birds in the Amazon rainforest. Let's create a post about them!"

Correct tool trajectory:
1. `create_post(title='Birds of the Amazon Rainforest', type='draft')` → returns `{post_id: 'def456'}`.

Correct final reply:
```json
{
  "post_id": "def456",
  "title": "Birds of the Amazon Rainforest",
  "type": "draft",
  "next_steps": ["outline", "brainstorm"]
}
```
