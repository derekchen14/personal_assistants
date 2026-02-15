# Skill: entity

Define the key entities grounded in the user's domain concepts.

## Behavior

- Each domain typically has 3 key entities (nouns the assistant works with)
- Help the user identify their entities by asking:
  - What are the core data objects in your domain?
  - What does your assistant create, read, update, or delete?
- Use `config_write` to save to the "entities" section
- Explain that entities become dact nouns in the flow grammar

## Slots

- `entities` (required): List of entity definitions

## Output

Confirm the entity definitions and explain how they'll be used in flow composition.
