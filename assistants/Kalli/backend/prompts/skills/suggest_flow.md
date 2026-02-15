# Skill: suggest_flow

Suggest new flows that could be added to the catalog.

## Behavior

- Analyze the current flow catalog for gaps
- Generate suggestions based on the user's domain intents and entities
- If intent_hint is given, focus suggestions on that intent
- Present each suggestion with: name, DAX code, description, rationale

## Slots

- `intent_hint` (optional): Focus suggestions on this intent
