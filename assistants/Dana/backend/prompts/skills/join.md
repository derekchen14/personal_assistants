# Skill: join

Combine two tables on a shared key.

## Behavior

- Use `merge_run` to join left and right datasets
- Default to inner join if how is not specified
- Show the first few rows of the result

## Slots

- `left` (required): Left dataset name
- `right` (required): Right dataset name
- `key` (required): Column to join on
- `how` (elective): Join type (inner, left, right, outer)

## Output

Table showing the merged result.
