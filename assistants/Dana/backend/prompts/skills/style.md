# Skill

Apply conditional formatting, colors, borders, and highlighting to a table view.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Parse the condition into a rule (e.g., "values > 1000", "column = 'Error'").
- Apply the formatting to matching cells or rows — color, bold, borders, background.
- Default to red highlight if no format is specified.
- Show a preview of the styled table with a count of affected cells.

## Slots

- `dataset` (required): The dataset to format.
- `condition` (required): The rule for which cells to format.
- `format` (elective): The visual style — red, green, bold, border, background color.

## Output

A `table` with conditional formatting applied.
