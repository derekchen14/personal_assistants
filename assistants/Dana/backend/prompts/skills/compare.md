# Skill

Compare two variables, groups, or time periods using correlation, distribution overlay, or side-by-side statistics.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Determine the comparison method based on column types:
  - Two numeric columns: compute correlation coefficient, show scatter plot via `chart_render`.
  - One numeric + one categorical: show side-by-side box plots or grouped bar chart.
  - Two categorical: show a contingency table via `sql_execute`.
  - Two time periods: filter and compare statistics side by side.
- If `method` is specified, use that method regardless of column types.
- Present both the visualization and the numeric comparison in the response.

## Slots

- `dataset` (required): The dataset to analyze.
- `column_a` (required): First variable to compare.
- `column_b` (required): Second variable to compare.
- `method` (elective): Comparison method — correlation, distribution, grouped, contingency.

## Output

A `chart` block with the comparison visualization.
