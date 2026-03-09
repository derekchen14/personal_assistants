# Skill: datatype

Validate and cast column types.

## Behavior

- Check the current type of the column
- Cast to the requested type (or suggest one if not specified)
- Report success or errors

## Slots

- `dataset` (required): Dataset name
- `column` (required): Column to cast
- `type` (elective): Target type (int, float, str, datetime)

## Output

Toast confirming the type change.
