# Skill: preference

Set a user preference for how the build process works.

## Behavior

- Accept a key-value preference (e.g., "verbosity": "concise", "auto_suggest": "on")
- Store the preference using the memory manager
- Acknowledge the change and explain how it will affect future interactions

## Slots

- `key` (required): Preference name
- `value` (required): Preference value
