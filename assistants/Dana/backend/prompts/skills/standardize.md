# Skill

Normalize inconsistent formats within a column — dates, capitalization, phone numbers, category spellings.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Use `column_analyze` to inspect current values and detect inconsistencies.
- Apply the specified format rule (or infer the best one from the data):
  - Dates: parse mixed formats into a consistent pattern (e.g., YYYY-MM-DD).
  - Text: apply title_case, lower, upper, or strip punctuation.
  - Phone numbers: normalize to a standard format.
  - Categories: map variant spellings to canonical values.
- Report how many values were changed and show before/after examples.

## Slots

- `dataset` (required): The dataset to clean.
- `column` (required): The column to standardize.
- `format` (elective): The target format — title_case, lower, upper, YYYY-MM-DD, phone_us.

## Output

A `toast` confirming the number of values standardized.
