# Skill

Find and replace values across a column — by exact match or regex pattern.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Search the specified column for all occurrences of `find`.
- Replace each match with `replacement`.
- Support both exact string matching and regex patterns.
- Report how many values were replaced and show a few before/after examples.
- If no matches are found, inform the user.

## Slots

- `dataset` (required): The dataset to modify.
- `column` (required): The column to search in.
- `find` (required): The value or pattern to find.
- `replacement` (required): The value to replace matches with.

## Output

A `toast` confirming the number of replacements made.
