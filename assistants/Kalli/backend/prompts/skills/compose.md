# Skill: compose

Review composed flows generated from the dact grammar.

## Behavior

- Read approved dacts from `config_read` (section: "dacts")
- Generate flows by composing 2-3 dacts per flow following the beam search process:
  - Each flow = verb + noun (+ optional adjective)
  - DAX codes are hex compositions of dact hex values
  - Target: ~48 flows across all 7 intents
- Present flows grouped by intent with: name, DAX code, description, slots, output type
- If `intent_filter` slot is set, show only flows for that intent
- Use `config_write` to save composed flows to the "flows" section

## Slots

- `intent_filter` (optional): Show flows only for this intent

## Output

A structured list of composed flows for the user to review.
