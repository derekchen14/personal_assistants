# Skill: select_outline

Select and approve an outline to work with.

## Behavior
- Confirm the user's outline choice
- Store the selected outline in scratchpad for reference
- If the outline was previously generated, reference it by number
- Use `post_create` to initialize a draft post with the selected outline structure
- Suggest next steps: `expand_content` to start writing, or `refine_outline` to tweak first

## Slots
- `outline_id` (required): Which outline to select (number or description)

## Output
Confirmation of the selected outline with next step suggestions.
