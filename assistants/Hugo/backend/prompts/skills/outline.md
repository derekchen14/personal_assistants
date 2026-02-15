# Skill: generate_outline

Generate outline options for a blog post topic.

## Behavior
- Generate 2-3 distinct outline approaches for the given topic
- Each outline should have 4-7 sections with brief descriptions
- Vary the approaches (e.g., listicle vs narrative vs how-to)
- If `depth` slot is provided, adjust detail level accordingly
- Use `post_search` to check for existing posts on similar topics and differentiate
- Number each outline so the user can easily select one
- After presenting, prompt the user to pick one via `select_outline`

## Slots
- `topic` (required): The blog post topic
- `depth` (optional): Level of detail (brief, standard, detailed)

## Output
A list of 2-3 outline options, each with numbered sections.
