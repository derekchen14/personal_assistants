# Skill: query

Run a SQL-like query against the data.

## Behavior

- Use `sql_execute` to run the query
- Display results as a table
- If query is natural language, convert to SQL first

## Slots

- `dataset` (required): Dataset name
- `query` (required): SQL query string

## Output

Table with query results.
