# Skill

Estimate missing values from surrounding data — linear, polynomial, spline, or seasonal interpolation.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Use `column_analyze` to identify null positions and surrounding value patterns.
- Apply the chosen interpolation method:
  - `linear`: straight-line estimate between nearest non-null neighbors.
  - `polynomial`: fit a polynomial curve through surrounding values.
  - `spline`: smooth cubic spline through the data.
  - `seasonal`: detect repeating patterns and use the seasonal component to fill gaps.
- Default to linear if no method is specified.
- Report how many values were interpolated, the method used, and show before/after examples.

## Slots

- `dataset` (required): The dataset to clean.
- `column` (required): The column with missing values.
- `method` (elective): The interpolation method — linear, polynomial, spline, seasonal.

## Output

A `toast` confirming the number of values interpolated.
