# Skill

Format values into the correct form — emails, phone numbers, addresses, dates, or custom patterns.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Use `column_analyze` to inspect current values and detect the dominant pattern.
- Apply the specified pattern (or infer the best one from the data):
  - Emails: lowercase, trim whitespace, validate structure.
  - Phone numbers: normalize to a standard format (e.g., (xxx) xxx-xxxx).
  - Addresses: standardize abbreviations (St → Street, Ave → Avenue).
  - Dates: parse mixed formats into a consistent pattern (e.g., YYYY-MM-DD).
  - Custom: apply a user-specified regex or template.
- Report how many values were reformatted and show before/after examples.

## Slots

- `dataset` (required): The dataset to clean.
- `column` (required): The column to format.
- `pattern` (elective): The target pattern — email, phone_us, date_iso, address, or a custom regex.

## Output

A `toast` confirming the number of values reformatted.
