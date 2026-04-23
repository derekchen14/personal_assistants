---
name: "compare"
description: "compare style or structure across two or more posts; sentence length, paragraph density, heading patterns, vocabulary, and tonal consistency"
version: 2
tools:
  - read_metadata
  - read_section
  - compare_style
---

This skill narrates a side-by-side comparison of two posts. The policy has resolved both posts and pre-fetched their metadata into `<resolved_details>`. Your job is to call `compare_style` (when applicable), then describe the differences in 2–3 sentences.

## Process

1. Read both post summaries from the `<resolved_details>` block.
2. Call `compare_style(left=<post_id_1>, right=<post_id_2>)` to get structural metrics (heading depth, paragraph length, vocabulary overlap).
3. Call `read_section` for any specific section the user named, on whichever side needs deeper detail.
4. Summarize the differences in plain prose. Lead with the biggest divergence (e.g., "Left runs 30% shorter; right uses far more H3 sub-sections.") and note one similarity.

## Error Handling

If only one post resolved (the user named one or none could be located), call `handle_ambiguity(level='partial', metadata={'missing_entity': 'second_post'})`.

If `compare_style` fails, fall back to a prose-only narration based on the metadata in `<resolved_details>`. Do NOT call `execution_error` — the comparison is still useful without the structural metrics.

If the section the user named doesn't exist on either post, call `handle_ambiguity(level='specific', metadata={'missing_reference': '<section name>'})`.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — fallback when `<resolved_details>` is missing data.
- `read_section(post_id, sec_id)` — for section-deep comparisons.
- `compare_style(left, right)` — returns structural metrics.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Two posts, structural difference

Resolved Details:
- Left: Building User Simulators (4 sections, ~2400 words)
- Right: Why Synthetic Data Works (6 sections, ~1800 words)

Trajectory:
1. `compare_style(left=abcd0123, right=ef012345)` → `{heading_depth: {left: 2, right: 3}, avg_paragraph_words: {left: 120, right: 70}}`.

Final reply:
```
"Why Synthetic Data Works" runs 25% shorter but sub-divides further (3-level headings vs. 2). Both stay in the same conversational register — the difference is structural, not tonal.
```

### Example 2: Section-scoped comparison

Resolved Details:
- Left: Building User Simulators / Architecture
- Right: Why Synthetic Data Works / Architecture

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=architecture)` → 4 paragraphs.
2. `read_section(post_id=ef012345, sec_id=architecture)` → 2 paragraphs + diagram.

Final reply:
```
Both Architecture sections cover the same three components, but the simulators post argues from first principles while the synthetic-data post leads with a diagram.
```
