# Skill: decline

Reject a proposed flow or dact with an optional reason.

## Behavior

- Mark the specified flow or dact as declined in the config
- Use `config_write` to update the status
- If a reason is given, store it for future reference
- Suggest alternatives or ask what the user would prefer instead
- Do not push back on the rejection — respect the user's judgment

## Slots

- `flow_name` (required): The flow or dact to reject
- `reason` (optional): Why it was rejected

## Output

Acknowledgment of the rejection and a prompt for what the user wants instead.
