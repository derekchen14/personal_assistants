# Skill: read_spec (Internal)

Internally read a spec file to answer a user's question.

## Behavior

- This is an internal flow — do not produce user-facing output
- Use `spec_read` to get the content
- Store relevant excerpts in scratchpad for the response generator

## Slots

- `spec_name` (required): Spec to read
- `section` (optional): Section to extract
