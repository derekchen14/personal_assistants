---
name: "search"
description: "look up vetted FAQs about Hugo (capabilities, scope, privacy, channels, voice tooling); used to answer meta-questions about the assistant"
version: 3
tools:
  - search_faqs
---

This skill looks up vetted FAQ content about Hugo itself. It runs as an Internal sub-agent — its result is consumed by a downstream flow (typically `chat`) and is never narrated to the user directly.

## Process

1. Read the user's query from the `<resolved_details>` block.
2. Call `search_faqs(query=<query>, top_k=3)` to retrieve the top FAQ matches by semantic relevance.
3. Return a structured summary capturing the top match's question + answer, plus a count of remaining matches.

## Error Handling

If `search_faqs` fails, call `execution_error(violation='tool_error', message=<reason>, failed_tool='search_faqs')`.

If the query is missing or empty, call `handle_ambiguity(level='specific', metadata={'missing': 'query'})`.

## Tools

### Task-specific tools

- `search_faqs(query, top_k=3)` — LLM-rerank lookup over the FAQ corpus. Returns up to `top_k` matches, each with `question`, `answer`, and a 0.0–1.0 relevance `score`.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Capability question

Resolved Details:
- Query: "what can Hugo do for me"

Trajectory:
1. `search_faqs(query='what can Hugo do for me', top_k=3)` → 3 matches; top score 0.94.

Final reply:
```
Top FAQ: "What can Hugo do for me?" — Hugo handles the full blogging lifecycle (research, drafting, revising, publishing). 2 adjacent matches available.
```

### Example 2: Privacy question

Resolved Details:
- Query: "how is my data handled"

Trajectory:
1. `search_faqs(query='how is my data handled', top_k=3)` → 1 match; score 0.88.

Final reply:
```
Top FAQ: "How does Hugo handle my privacy?" — Draft content stays local; only short, scoped prompts go to the LLM.
```
