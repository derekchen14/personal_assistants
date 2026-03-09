# Skill: filter

Subset rows matching a condition.

## Behavior

- Convert the condition to a SQL WHERE clause or pandas query
- Use `sql_execute` or `python_execute` to filter
- Display matching rows

## Slots

- `dataset` (required): Dataset name
- `condition` (required): Filter condition

## Output

Table with filtered rows.
