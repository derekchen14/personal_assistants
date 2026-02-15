# Skill: revise

Update a previously defined config section.

## Behavior

- Use `config_read` to get the current value of the section
- Apply the update using `config_write` with merge=True
- Show the before and after values
- Confirm the change with the user

## Slots

- `section` (required): Config section to update
- `field` (required): Specific field within the section
- `value` (required): New value
