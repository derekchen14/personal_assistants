# Skill: lookup

Look up a specific spec file or section from the architecture docs.

## Behavior

- Use `spec_read` with the `spec_name` slot to read the requested spec
- If a `section` slot is provided, pass it to extract just that heading
- Present the content in a clear, readable format
- If the spec is long, summarize the key points and offer to show specific sections

## Slots

- `spec_name` (required): Name of the spec file without .md extension
- `section` (optional): Specific heading to extract

## Output

The spec content, formatted for readability. Summarize if over 500 words.
