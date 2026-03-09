# Skill: update

Modify cell values or column types in place.

## Behavior

- Verify the dataset is loaded
- Apply the update to the specified column/row
- Report what was changed

## Slots

- `dataset` (required): Dataset name
- `column` (required): Column to update
- `row` (optional): Row index (all rows if omitted)
- `value` (required): New value

## Output

Toast confirming the update.
