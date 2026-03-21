# Skill: refine

Refine an existing outline by adjusting headings, reordering sections, or incorporating feedback.

## Behavior
1. Use `read_metadata` with `include_outline: true` to load the current outline
2. Use `read_section` if you need to see the content of specific sections
3. Adjust headings, bullet points, and section order per the user's feedback
4. Use `write_text` if you need to generate new bullet points or descriptions
5. Format your revised outline using `## Section Title` headings with bullet points

## Important
- The policy saves the result automatically — just output the revised outline as markdown.
- Use `generate_outline` to save the outline if the policy doesn't persist it.
- When the user specifies exact bullet points, use those verbatim. Do not add or remove bullets beyond what was requested.
- Rephrase provided bullets only if the user explicitly asks to improve them, or to fix grammatical errors.
- While `read_metadata` can be used to get post IDs, the post title has been resolved for you within "Resolved entities". The mapping of section titles to section IDs can also be found there. You are encouraged to use these provided IDs rather than executing extra tool calls to get this information.

## Slots
- `source` (required): The post whose outline to refine
- `feedback` (optional): Specific guidance for the refinement

## Output
The refined outline in `## Heading` format with bullet points.
