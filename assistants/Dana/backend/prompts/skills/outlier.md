# Skill: outlier

Detect numeric values outside expected ranges.

## Behavior

- Use `column_analyze` to compute statistics
- Apply IQR or z-score method to identify outliers
- Report the count and sample of outlier values

## Slots

- `dataset` (required): Dataset name
- `column` (required): Column to check
- `threshold` (optional): Standard deviations or IQR multiplier

## Output

List of detected outliers with their values.
