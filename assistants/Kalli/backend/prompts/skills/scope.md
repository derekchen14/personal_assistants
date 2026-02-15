# Skill: scope

Help the user define their assistant's scope — name, task, and boundaries.

## Behavior

- Collect three pieces of information:
  1. **Name**: What should the assistant be called?
  2. **Task**: What is its primary purpose? (one sentence)
  3. **Boundaries**: What is explicitly out of scope?
- If slots are pre-filled, confirm them with the user
- Use `config_write` to save to the "scope" section once all fields are collected
- Reference the scope definition pattern from the architecture specs if helpful

## Slots

- `name` (required): Assistant name
- `task` (required): Primary task description
- `boundaries` (optional): What the assistant should NOT do

## Output

Confirm the saved scope and suggest the next step (persona or intents).
