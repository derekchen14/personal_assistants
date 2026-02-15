# Skill: revise_flow

Revise an in-progress flow design.

## Behavior

- Look up the specified flow in the config
- Apply the requested change to the specified field (slots, output, description, etc.)
- Use `config_write` to save the updated flow definition
- Show the updated flow definition

## Slots

- `flow_name` (required): Flow to revise
- `field` (required): What to change (slots, output, description, edge_flows)
