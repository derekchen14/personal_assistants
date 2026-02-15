# Skill: refine_outline

Refine a specific section of an existing outline.

## Behavior
- Use `post_get` to retrieve the current outline
- Focus on the specified section — don't change other parts
- If `feedback` is provided, incorporate it into the refinement
- Use `post_update` to save the refined outline
- Show the updated section alongside the original for comparison

## Slots
- `section` (required): Which section to refine
- `feedback` (optional): Specific guidance for the refinement

## Output
The refined section with before/after comparison.
