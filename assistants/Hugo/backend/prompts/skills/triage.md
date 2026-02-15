# Skill: plan_revision

Plan a revision sequence for an existing post.

## Behavior
- Use `post_get` to retrieve the post and assess its current state
- If `scope` is provided (light, moderate, heavy), adjust the plan accordingly
- Identify the weakest sections and prioritize them
- Create a revision plan with specific actions for each section
- Include steps for: content review, structural changes, tone adjustment, formatting, final polish
- Set keep_going so Hugo can begin the first revision step

## Slots
- `post_id` (required): The post to plan revisions for
- `scope` (elective): Revision depth (light, moderate, heavy)

## Output
A numbered revision plan with specific actions for each area.
