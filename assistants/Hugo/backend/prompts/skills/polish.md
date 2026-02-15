# Skill: polish_section

Polish and refine a specific section for clarity and style.

## Behavior
- Focus on sentence-level improvements: word choice, rhythm, conciseness
- If `style_notes` are provided, apply them specifically
- Use `content_format` to clean up formatting
- Use `post_update` to save the polished version
- Don't change the meaning or structure — only improve the prose
- Show a brief before/after comparison for key changes

## Slots
- `section` (required): The section to polish
- `style_notes` (optional): Specific style guidance

## Output
The polished section with notes on what was refined.
