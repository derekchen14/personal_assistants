This skill produces a standalone summary paragraph for a post. The policy preloads the full post content (title + outline) into `<resolved_details>` plus an optional `length` hint. Read directly from the block; only call `read_section` if you need extra detail beyond what was preloaded.

## Process

1. Read the post title and outline from the `<resolved_details>` block.
2. Identify three things to include in the summary: (a) the core argument, (b) the target audience, (c) the main takeaways.
3. Apply the length hint when set. Default is ~75 words. If `length < 30`, write a one-sentence hook instead of a paragraph.
4. If the post is a stub (≤ 2 short sections), summarize what exists and note it's incomplete.

## Error Handling

If the post body is empty or unreadable, call `execution_error(violation='empty_output', message='post body is empty')`.

If the user named a section that doesn't exist, call `handle_ambiguity(level='specific', metadata={'missing': 'section', 'reason': 'invalid_value'})`.

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

### Example 4: Named section does not exist

Resolved Details:
- Source: post=c0918a44 ("Designing Idempotent APIs")
- User asked: "Summarize just the Retries section."

Trajectory:
1. The preloaded outline lists Motivation, Keys, and Failure Modes, with no Retries section.
2. `handle_ambiguity(level='specific', metadata={'missing': 'section', 'reason': 'invalid_value'})`. Name the sections that exist, then end turn.

### Example 5: Read a section for extra detail

Resolved Details:
- Source: post=c0918a44 ("Designing Idempotent APIs")
- Outline: Motivation, Keys, Failure Modes
- Length: 90

Trajectory:
1. `read_section(post_id=c0918a44, sec_id='failure-modes')` → the outline preview was thin on the retry-storm example, so pull the prose.
2. `summarize_text(content=<title + outline + failure-modes prose>, max_words=90)` → distilled paragraph below.

Final reply:
```
"Designing Idempotent APIs" makes the case that safe retries hinge on stable idempotency keys, not clever server logic. Written for backend engineers building payment and ordering flows, it walks through key generation, storage windows, and the failure modes that bite when two requests race, including the retry-storm pattern that turns one timeout into a flood.
```
