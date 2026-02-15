# Skill: accept_revision

Accept and finalize a revision to a blog post.

## Behavior
- Confirm the revision is accepted
- Use `post_update` to mark the post's revision as finalized
- If `comment` is provided, store it in scratchpad as a note
- Clear any pending revision state from the flow stack
- Suggest next steps: `format_post` to prepare for publication, or `publish_post` to go live

## Slots
- `post_id` (required): The post whose revision is accepted
- `comment` (optional): Note about the accepted revision

## Output
Confirmation that the revision is finalized.
