# Skill: expand

Plan to add a batch of new flows at once.

## Behavior

- Analyze current flow catalog for coverage gaps
- Propose a batch of new flows targeting the specified intent or count
- Push edge flows (compose, suggest_flow) for the expansion process

## Slots

- `intent_filter` (optional): Focus expansion on this intent
- `count` (optional): How many new flows to add
