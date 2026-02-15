# Skill: intent

Help the user define a domain-specific intent for their assistant.

## Behavior

- Every assistant gets 3 universal intents for free: Plan, Converse, Internal
- The user needs to define 4 domain-specific intents
- Each intent needs:
  1. **Name**: Short, verb-like (e.g., Explore, Provide, Design, Deliver)
  2. **Description**: What the user is trying to do
  3. **Abstract slot**: Which POMDP slot it maps to (Read, Prepare, Transform, Schedule)
- Use `config_write` to save each intent to the "intents" section
- Explain the abstract slot mapping if the user is unfamiliar

## Slots

- `intent_name` (required): Name of the intent
- `description` (required): What it does
- `abstract_slot` (elective): POMDP mapping (Read/Prepare/Transform/Schedule)

## Output

Confirm the intent definition and show how many more are needed.
