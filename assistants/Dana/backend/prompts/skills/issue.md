# Skill

Detect data quality issues — outliers, anomalies, typos, or inconsistencies across columns.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Use `column_analyze` to profile each target column.
- Run detection checks based on the issue type:
  - Outliers: flag numeric values beyond 2 standard deviations (or user threshold).
  - Typos: use fuzzy matching to find likely misspellings in text columns.
  - Anomalies: detect unusual patterns, unexpected nulls, or format inconsistencies.
- If no type is specified, run all checks.
- Report a summary of issues found, grouped by type, with row numbers and sample values.

## Slots

- `dataset` (required): The dataset to diagnose.
- `column` (optional): A specific column to check. If omitted, check all columns.
- `type` (elective): The issue type — outlier, typo, anomaly, all.

## Output

A `list` of detected issues grouped by type.
