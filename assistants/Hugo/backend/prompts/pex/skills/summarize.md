---
name: "summarize"
description: "synthesize a post into a short paragraph capturing the core argument, target audience, and main takeaways; useful for excerpts, SEO descriptions, or pre-reads before writing a follow-up"
version: 2
tools:
  - read_metadata
  - read_section
  - summarize_text
---

This skill produces a standalone summary paragraph for a post. The policy preloads the full post content (title + outline) into `<resolved_details>` plus an optional `length` hint. Read directly from the block; only call `read_section` if you need extra detail beyond what was preloaded.

## Process

1. Read the post title and outline from the `<resolved_details>` block.
2. Identify three things to include in the summary: (a) the core argument, (b) the target audience, (c) the main takeaways.
3. Apply the length hint when set. Default is ~75 words. If `length < 30`, write a one-sentence hook instead of a paragraph.
4. If the post is a stub (≤ 2 short sections), summarize what exists and note it's incomplete.

## Error Handling

If the post body is empty or unreadable, call `execution_error(violation='empty_output', message='post body is empty')`.

If the user named a section that doesn't exist, call `handle_ambiguity(level='specific', metadata={'missing_reference': '<sec>'})`.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — fallback when `<resolved_details>` is missing data.
- `read_section(post_id, sec_id)` — only when needing prose beyond the preloaded outline.
- `summarize_text(content, max_words)` — optional helper if you want the LLM to pre-distill before composing the final summary.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Standard summary

Resolved Details:
- Source: post=abcd0123 ("Building User Simulators")
- Outline: Motivation, Process, Architecture, Evaluation
- Length: 75

Trajectory: `summarize_text(content=<preloaded outline>, max_words=75)` → distilled paragraph below.

Final reply:
```
"Building User Simulators" argues that synthetic conversations unlock RL-agent training at scales human testing can't reach. Aimed at ML engineers wiring up agentic systems, the post lays out a four-component pipeline (intent sampler, response generator, termination predictor, evaluator) and reports a 12% lift in task-completion when the simulator's trajectories feed downstream RLHF.
```

### Example 2: Short hook (length < 30)

Resolved Details:
- Source: post=abcd0123
- Length: 20

Final reply:
```
A four-stage pipeline turns synthetic conversations into RL training data — and lifts agent task completion by 12%.
```

### Example 3: Stub post

Resolved Details:
- Source: post=ef012345 ("Multi-modal Models")
- Outline: Motivation (3 bullets only)

Final reply:
```
"Multi-modal Models" is a stub: only the Motivation section has content, framing why text-only agents miss visual context. The Architecture, Examples, and Takeaways sections are still empty.
```
