# Skill

Summarize a specific chart or table in plain language.

## Behavior

- Reference a specific chart or table that the user is asking about.
- Provide a clear, concise summary of what the artifact shows.
- Highlight key takeaways, notable patterns, and practical implications.
- Use examples from the loaded data if available.
- This flow is grounded to a specific artifact (chart, table, query result) — NOT the overall analysis process (that is the `explain` flow in Converse).
- Suggest follow-up actions based on the findings.

## Slots

- `dataset` (required): The dataset the artifact belongs to.
- `chart` (elective): The specific chart to summarize.
- `table` (elective): The specific table to summarize.

## Output

A `card` with the summary, key takeaways, and suggested next steps.
