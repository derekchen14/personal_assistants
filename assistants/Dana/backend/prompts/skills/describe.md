# Skill

Describe a dataset or column — show structure, types, statistics, and value distributions.

## Behavior

- If `column` is provided, focus on that single column: type, null count, unique count, min, max, mean, median, mode, and sample values. Use `column_analyze`.
- If `column` is not provided, describe the full dataset: row count, column names and types, null counts per column, and basic statistics for numeric columns. Use `dataset_load` to get the schema, then `column_analyze` on key columns.
- Present the results in a structured card with clear section headers.
- If the dataset is not loaded, load it first via `dataset_load`.

## Slots

- `dataset` (required): The dataset to describe.
- `column` (optional): A specific column to focus on. If omitted, describe the whole table.

## Output

A `card` block with the dataset or column description.
