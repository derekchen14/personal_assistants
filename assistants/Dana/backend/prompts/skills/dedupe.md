# Skill: dedupe

Remove duplicate rows.

## Behavior

- Count duplicates before removal
- Remove duplicates based on key columns (or all columns)
- Report how many rows were removed

## Slots

- `dataset` (required): Dataset name
- `key_columns` (optional): Columns to check for duplicates

## Output

Toast reporting rows removed.
