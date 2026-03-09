# Skill

Compare values or groups across time — trends, period-over-period changes, and trajectories.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Identify the time column and value column from the dataset.
- If `group_by` is provided, split the data into separate series for each group.
- Use `chart_render` with line chart type to plot all series over time.
- Highlight directional patterns — upward, downward, or flat trends.
- Support period-over-period analysis when the user specifies comparison intervals.

## Slots

- `dataset` (required): The dataset to analyze.
- `column` (required): The value column to plot.
- `time_col` (required): The time/date column for the x-axis.
- `group_by` (optional): A column to group by for comparing multiple series over time.

## Output

A `chart` showing the trend lines with directional highlights.
