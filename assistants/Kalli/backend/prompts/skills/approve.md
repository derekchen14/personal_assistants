# Skill: approve

Approve a proposed flow or dact.

## Behavior

- Mark the specified flow or dact as approved in the config
- Use `config_write` to update the approval status
- Acknowledge the approval and suggest what to review next
- If all items in a batch are approved, celebrate and suggest moving forward

## Slots

- `flow_name` (required): The flow or dact to approve

## Output

Confirmation of approval with a note on remaining items to review.
