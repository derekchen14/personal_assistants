# Skill: aggregate

Group by a column and compute stats.

## Behavior

- Use `sql_execute` with GROUP BY
- Display the aggregated results

## Slots

- `dataset` (required): Dataset name
- `group_by` (required): Column to group by
- `metric` (elective): Aggregation function

## Output

Table with grouped results.
