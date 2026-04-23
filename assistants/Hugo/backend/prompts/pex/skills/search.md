---
name: "search"
description: "look up vetted FAQs and curated editorial guidelines; the unstructured equivalent of a style manual"
version: 2
tools:
  - find_posts
---

This skill looks up vetted editorial guidelines and FAQ content. It runs as an Internal sub-agent — its result is consumed by a downstream flow, never narrated to the user directly.

## Process

1. Read the user's query from the `<resolved_details>` block.
2. Call `find_posts(query=<query>)` to retrieve matching items.
3. If the user provided a `count` slot, limit the results accordingly. Default to 5.
4. Return a structured list summary so the caller can use it as scratchpad context.

## Error Handling

If `find_posts` fails, call `execution_error(violation='tool_error', message=<reason>, failed_tool='find_posts')`.

If the query is missing or empty, call `handle_ambiguity(level='specific', metadata={'missing_slot': 'query'})`.

## Tools

### Task-specific tools

- `find_posts(query, ...)` — keyword search across the editorial corpus.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Looking up a style guideline

Resolved Details:
- Query: "house style for em dashes"

Trajectory:
1. `find_posts(query='house style em dash')` → 2 matches.

Final reply:
```
Found 2 references on em dash usage in the house style guide.
```
