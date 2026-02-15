# Skill: refine

Refine a flow's slot signature or output type.

## Behavior

- Look up the specified flow
- If slot_name is given, modify that specific slot (type, priority, etc.)
- If change is given, apply the described change
- Otherwise, present the current slot signature and ask what to change
- Use `config_write` to save updates

## Slots

- `flow_name` (required): Flow to refine
- `slot_name` (optional): Specific slot to modify
- `change` (optional): Description of the change
