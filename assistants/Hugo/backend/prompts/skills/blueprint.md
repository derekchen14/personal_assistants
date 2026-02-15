# Skill: plan_post

Plan the full workflow for creating a blog post.

## Behavior
- Break down the post creation into concrete steps
- If `topic` is provided, tailor the plan to that topic
- Include steps for: research, outline, drafting, revision, formatting, publishing
- Estimate which steps the user can skip based on their experience level
- Use `post_search` to check for related existing content
- Present the plan as a numbered checklist
- Set keep_going so Hugo can start executing the first step

## Slots
- `topic` (optional): The topic for the planned post

## Output
A numbered step-by-step plan for creating the post.
