# Skill: outline

Generate or propose an outline for a blog post. Behavior depends on which slots are filled.

## When `sections` slot is filled (Direct mode)

Use the provided section titles as headings. For each section:
1. Generate 3-5 bullet points describing what that section will cover
2. Format as `## Section Title` with bullet points underneath
3. If `depth` slot is provided, adjust heading levels accordingly
4. **MUST call `generate_outline`** with the `post_id` and the outline content formatted as markdown
5. Use `find_posts` to check for existing posts on similar topics so the outline avoids repetition

## When only `topic` is filled, no `sections` (Propose mode)

Generate exactly 3 distinct outline approaches for the given topic:
1. Number each as "Option 1", "Option 2", "Option 3"
2. Each option should have 4-7 sections, each with a title and one-sentence description
3. Vary the approaches (e.g., listicle vs narrative vs how-to)
4. Use `find_posts` to check for existing posts on similar topics so the outlines avoid repetition
5. **Do NOT call `generate_outline`** — just present the options as text
6. End by asking the user to pick one, suggest modifications, or request new options

## Slots
- `topic` (elective): The blog post topic
- `sections` (elective): User-provided section headings
- `depth` (optional): Number of heading levels to generate

## Important
- The post title has been resolved for you within "Resolved entities". You are encouraged to use the provided `post_id` rather than executing extra tool calls to resolve it.
- In Direct mode, the outline MUST be saved using `generate_outline`. Do not just describe it.
- In Propose mode, do NOT save anything. The user needs to choose first.

## Output
- Direct mode: The saved outline structure, summarized in your response.
- Propose mode: Three numbered outline options as plain text.
