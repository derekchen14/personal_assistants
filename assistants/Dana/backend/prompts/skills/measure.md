# Skill: measure

Compute a scalar metric.

## Behavior

- Use `column_analyze` or `sql_execute` to compute the metric
- Support count, sum, mean, median, min, max
- Display as a card with the metric value

## Slots

- `dataset` (required): Dataset name
- `column` (required): Column to measure
- `metric` (elective): Metric to compute (count, sum, mean, etc.)

## Output

Card showing the computed metric.
