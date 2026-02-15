# Skill: persona

Define the assistant's persona preferences — tone, name, style, colors.

## Behavior

- Collect persona attributes:
  1. **Name**: Already set in scope, confirm or override
  2. **Tone**: formal, conversational, playful, etc.
  3. **Response style**: concise, balanced, or verbose
  4. **Colors**: Optional brand colors for the UI
- Use `config_write` to save to the "persona" section
- If the user isn't sure, offer examples from the architecture spec

## Slots

- `name` (required): Assistant name
- `tone` (elective): Communication tone
- `response_style` (elective): How verbose responses should be
- `colors` (optional): Brand color palette

## Output

Confirm the persona settings and preview how the assistant would sound.
