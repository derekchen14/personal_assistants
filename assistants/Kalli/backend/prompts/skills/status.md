# Skill: status

Show the current state of the assistant config being built.

## Behavior

- Use `config_read` (no section) to get the full config state
- Summarize which sections are defined and which are still needed
- If a specific section was requested (via the `section` slot), show that section's details
- Indicate overall progress as a percentage or phase

## Output

A structured summary: sections defined, sections remaining, overall progress.
