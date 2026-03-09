# Skill

Check data against validation rules — enum constraints, allowed ranges, and business rules.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- If `rules` are provided, check each rule against the data:
  - Type constraints: ensure column values match expected types.
  - Range checks: flag values outside min/max bounds.
  - Enum constraints: verify values belong to an allowed set (e.g., status must be active, inactive, or pending).
  - Business rules: apply domain-specific validation logic (e.g., end_date must be after start_date).
- Flag invalid values and report how many were found, with examples.

## Slots

- `dataset` (required): The dataset to validate.
- `column` (optional): A specific column to target. If omitted, apply to all relevant columns.
- `rules` (optional): Validation rules to check — type, range, enum, business logic.

## Output

A `toast` confirming the number of values flagged as invalid.
