# Skill

Break down a metric by dimension for drilldown analysis — e.g., MAU by platform, revenue by region.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Compute the specified metric grouped by the dimension column.
- Sort results by the metric value descending to surface the largest segments.
- Show each segment's value and its percentage of the total.
- If the dimension has many unique values, show the top 10 and aggregate the rest as "Other".

## Slots

- `dataset` (required): The dataset to analyze.
- `metric` (required): The metric to break down — a column name or aggregation expression.
- `dimension` (required): The column to segment by.

## Output

A `table` showing each dimension value with its metric total and share of the whole.
