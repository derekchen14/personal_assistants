---
name: "cite"
description: "add a citation to a sentence or phrase within a post; if a URL is provided, attach it directly; if only a target snippet is provided, search the web for a supporting source and propose it for user confirmation"
version: 2
tools:
  - read_metadata
  - read_section
  - revise_content
  - web_search
---

This skill attaches a citation to a snippet of text. Two modes: direct attach when a URL is given, or web-search-and-propose when only a target snippet is given.

## Process

1. Read `target` and `url` from `<resolved_details>`.
2. Call `read_section(post_id, sec_id)` to locate the snippet within the section.
3. **URL mode (`url` filled):**
   a. If multiple URLs (semicolon-separated), iterate and attach each in order.
   b. Call `revise_content` to persist the citation alongside the snippet.
4. **Search mode (`url` empty, `target` filled):**
   a. Call `web_search(query=<snippet topic>)` to find a credible supporting source.
   b. Prefer primary sources (papers, official docs) over secondary blogs.
   c. Propose the source with title + domain + a 1-sentence rationale.
   d. Do NOT call `revise_content` — wait for user confirmation (handled by policy).

## Error Handling

If neither `target` nor `url` is filled, call `handle_ambiguity(level='partial', metadata={'missing_entity': 'target_or_url'})`.

If `web_search` fails, call `handle_ambiguity(level='specific', observation='Search failed — give me a URL to attach directly?')`.

If `revise_content` fails, retry ONCE. Then call `execution_error(violation='tool_error', message=<reason>, failed_tool='revise_content')`.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — fallback for post info.
- `read_section(post_id, sec_id)` — locate the snippet.
- `revise_content(post_id, sec_id, ...)` — persist the citation.
- `web_search(query=...)` — find a supporting source.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Direct URL attach

Resolved Details:
- Target: post=abcd0123, section=motivation, snippet="user simulators generate millions of training episodes overnight"
- URL: https://arxiv.org/abs/2403.01234

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=motivation)` → finds the snippet.
2. `revise_content(post_id=abcd0123, sec_id=motivation, content="…simulators generate millions of training episodes overnight [[ref]](https://arxiv.org/abs/2403.01234).")` → `_success=True`.

Final reply:
```
Attached the citation to the throughput sentence in Motivation.
```

### Example 2: Search-and-propose

Resolved Details:
- Target: post=abcd0123, section=architecture, snippet="termination predictors trained on dialogue closure markers"

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=architecture)` → context.
2. `web_search(query='termination predictors dialogue closure markers')` → 3 results.

Final reply:
```
Proposed source: "Predicting Dialogue Termination" (arxiv.org). Primary research paper, directly addresses the closure-marker training pattern. Want me to attach it?
```
