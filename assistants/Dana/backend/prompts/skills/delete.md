# Skill: delete

Remove rows or columns.

## Behavior

- Identify whether target is a column name or row index
- Ask for confirmation before deleting
- Report what was removed

## Slots

- `dataset` (required): Dataset name
- `target` (required): Column name or row index

## Output

Confirmation dialog, then toast on completion.
