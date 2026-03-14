# Skill: remove

Remove a section from a post, or delete an entire draft or note.

## Behavior
- Use `post_get` to confirm the target exists before deleting
- For section removal: use `post_update` to remove the section from the post content
- For draft/note deletion: use `post_delete` to remove the entire entry
- Always confirm what was removed in the response
- Do NOT delete published posts — only drafts and notes can be deleted

## Slots
- `source` (required): The post, draft, or note to act on
- `type` (required): What to remove — "section", "draft", "note", "post", or "paragraph"

## Output
Toast confirmation of the removal.
