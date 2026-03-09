# Skill

Export a dataset or query result to a downloadable file — CSV, Excel, JSON, or Parquet.

## Behavior

- Load the dataset via `dataset_load` if not already loaded.
- Use `export_run` to write the data to the specified format.
- Default to CSV if no format is specified.
- Report the file path, row count, and file size.

## Slots

- `dataset` (required): The dataset to export.
- `format` (elective): The output format — csv, xlsx, json, parquet.

## Output

A `toast` confirming the export with file path and size.
