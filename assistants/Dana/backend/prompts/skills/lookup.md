# Skill

Find the definition of a metric, term, or concept in the semantic layer or business glossary.

## Behavior

- Search the semantic layer (stored definitions, business glossary, or column metadata) for the requested term.
- Use `memory_manager` to check if the term was previously defined via the `define` flow.
- Use `context_coordinator` to search conversation history for prior definitions.
- If found, present the definition with its formula, source, and any related metrics.
- If not found, explain that no definition exists and suggest the user define it via the `define` flow.

## Slots

- `term` (required): The metric, term, or concept to look up.
- `source` (optional): Where to search (e.g., "glossary", "semantic layer", "scratchpad").

## Output

A `card` block with the term definition, formula, and source.
