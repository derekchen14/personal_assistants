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

If neither `target` nor `url` is filled, call `handle_ambiguity(level='partial', metadata={'missing': 'target'})`.

If `web_search` fails, call `handle_ambiguity(level='specific', metadata={'missing': 'url'}, observation='Search failed — give me a URL to attach directly?')`.

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

### Example 3: Multiple URLs attached in order

Resolved Details:
- Target: post=9d2c7a40, section=scheduling, snippet="the scheduler evicts pods under memory pressure"
- URL: https://kubernetes.io/docs/concepts/scheduling-eviction/; https://kubernetes.io/docs/tasks/administer-cluster/out-of-resource/

Trajectory:
1. `read_section(post_id=9d2c7a40, sec_id=scheduling)` → finds the eviction snippet.
2. `revise_content(post_id=9d2c7a40, sec_id=scheduling, content="…evicts pods under memory pressure [[ref]](https://kubernetes.io/docs/concepts/scheduling-eviction/) [[ref]](https://kubernetes.io/docs/tasks/administer-cluster/out-of-resource/).")` → `_success=True`.

Final reply:
```
Attached both Kubernetes docs pages to the eviction sentence in Scheduling.
```

### Example 4: Neither target nor URL given

Resolved Details:
- Source: post=4f8e1b60
- User asked: "Add a citation somewhere in the sharding post."

Trajectory:
1. Neither `target` nor `url` is filled in the resolved details.
2. `handle_ambiguity(level='partial', metadata={'missing': 'target'})`. Ask which sentence needs the source, then end turn.

### Example 5: Save fails after retry

Resolved Details:
- Target: post=c3a90f22, section=backoff, snippet="exponential backoff with jitter avoids thundering herds"
- URL: https://aws.amazon.com/builders-library/timeouts-retries-and-backoff-with-jitter/

Trajectory:
1. `read_section(post_id=c3a90f22, sec_id=backoff)` → finds the snippet.
2. `revise_content(...)` → `_success=False`. Retry once → still `_success=False`.
3. `execution_error(violation='tool_error', message='revise_content failed twice on the backoff citation', failed_tool='revise_content')`. End turn.
