# Skill

Fill null or empty cells using a strategy — forward fill, mean, zero, interpolate, or a constant value.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- If `column` is specified, fill only that column. Otherwise, fill all columns with nulls.
- Apply the chosen strategy:
  - `fill_forward`: propagate the last valid value forward.
  - `fill_mean`: replace nulls with the column mean (numeric only).
  - `fill_zero`: replace nulls with zero (numeric) or empty string (text).
  - `fill_constant`: replace with a user-specified constant.
  - `interpolate`: linearly interpolate between surrounding values (numeric only).
  - `drop`: remove rows containing nulls instead of filling.
- Report how many cells were filled and in which columns.

## Slots

- `dataset` (required): The dataset to clean.
- `column` (optional): A specific column to fill. If omitted, fill all columns with nulls.
- `strategy` (elective): The fill strategy — fill_forward, fill_mean, fill_zero, fill_constant, interpolate, drop.

## Output

A `toast` confirming the number of cells filled.
