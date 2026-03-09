# Skill: pipeline

Chain Transform flows into a reusable ETL sequence.

## Behavior

- Parse the steps into individual transform operations
- Execute each step in order
- Report the result of each step

## Slots

- `steps` (required): List of transform operations
- `dataset` (required): Source dataset

## Output

List of completed pipeline steps.
