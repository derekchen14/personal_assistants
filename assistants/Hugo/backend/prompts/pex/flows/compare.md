This skill narrates a side-by-side comparison of two posts. The policy resolves both posts and supplies their IDs and the comparison `Category` in `<resolved_details>`. Branch your tool calls on `Category`, then describe the differences in 2–3 sentences.

## Process

**Version-diff mode:** If `<resolved_details>` carries `Lookback` or `Mapping`, compare two *versions of one post* rather than two posts. Call `diff_section(post_id, sec_id, lookback=N)` (or with `mapping=...`), then narrate what changed — largest addition / deletion / rewrite first — in 2-3 sentences. Skip the Category branches below.

1. Read both post IDs and `Category` from `<resolved_details>`. Then scan the latest user utterance for a **specifically named metric** ("word count", "section count", "headings", "paragraph length", "links", "images", etc.). If one is named, anchor your narration on that metric — do NOT drift to a general structural summary.
2. Branch on `Category`:
   a. **`inspect`** — call `inspect_post(post_id)` for each post. Compare numeric metrics (word_count, section_count, heading_depth, image_count, link_count, avg_paragraph_length).
   b. **`check`** — call `read_metadata(post_id)` for each post. Compare metadata (status, tags, channels, created_at, updated_at, section_ids).
   c. **`tone`** — call `read_section(post_id, sec_id)` for each post on a representative section (prefer a section name that exists on both posts; otherwise pick each post's first non-empty section). Judge register, sentence rhythm, and vocabulary from the prose itself.
3. Summarize the differences in plain prose, scoped to the chosen category.
   - **If the user named a specific metric in step 1**, lead with that metric using the **concrete numbers** from `inspect_post`'s output (e.g. "Post A: 1,500 words; Post B: 2,400 words — about 60% more"). Do not stray to other metrics; one or two sentences is enough.
   - **Otherwise**, lead with the biggest divergences:
     a. for `inspect` — call out structural deltas (e.g. "20% more sections", "double the heading depth").
     b. for `check` — call out metadata divergences (status, channels, recency).
     c. for `tone` — call out register/voice differences (formal vs. casual, dense vs. airy, technical vs. conversational).

## Error Handling

If only one post resolved (the user named one or none could be located), call `declare_ambiguity(level='partial', metadata={'missing': 'source', 'entity': 'post'})`.

If a tool call fails, fall back to a prose-only narration based on whatever data you already have. Do NOT call `execution_error` — the comparison is still useful even with partial data.

If the section the user named doesn't exist on either post, call `declare_ambiguity(level='specific', metadata={'missing': 'section', 'reason': 'invalid_value'})`.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — for the `check` branch and as a fallback when `<resolved_details>` is missing data.
- `read_section(post_id, sec_id)` — for the `tone` branch and any section-deep comparison.
- `inspect_post(post_id)` — for the `inspect` branch.
- `diff_section(post_id, sec_id, lookback=...)` — version-diff worker (when `Lookback`/`Mapping` is set); pass `mapping=...` for a draft-vs-published style diff.

### General tools

- `execution_error(violation, message)`
- `declare_ambiguity(**params)`
- `read_scratchpad(**params)`
- `read_flow_stack(details)`

## Few-shot examples

### Example 1: Category=inspect, user named "word count"

User utterance: "Compare the word count between these two."

Resolved Details:
- Posts: abcd0123, ef012345
- Category: inspect

Trajectory:
1. User named `word count` — anchor narration on word_count, ignore other metrics.
2. `inspect_post(post_id=abcd0123)` → `{word_count: 2400, section_count: 4, heading_depth: 2, avg_paragraph_length: 120}`.
3. `inspect_post(post_id=ef012345)` → `{word_count: 1500, section_count: 6, heading_depth: 3, avg_paragraph_length: 70}`.

Final reply:
```
The first post runs about 2,400 words; the second comes in at 1,500 — roughly 60% the length. The first is the longer-form treatment.
```

### Example 2: Category=inspect, no specific metric named (structural overview)

User utterance: "How do they compare structurally?"

Resolved Details:
- Posts: abcd0123, ef012345
- Category: inspect

Trajectory:
1. No specific metric named — fall back to general structural summary.
2. `inspect_post(post_id=abcd0123)` → `{word_count: 2400, section_count: 4, heading_depth: 2, avg_paragraph_length: 120}`.
3. `inspect_post(post_id=ef012345)` → `{word_count: 1800, section_count: 6, heading_depth: 3, avg_paragraph_length: 70}`.

Final reply:
```
The second post runs 25% shorter but sub-divides further (3-level headings vs. 2) and pads with shorter paragraphs (~70 words vs. ~120). The first post leans long-form; the second leans scannable.
```

### Example 3: Category=tone, voice difference

Resolved Details:
- Posts: abcd0123, ef012345
- Category: tone

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=introduction)` → formal, technical prose.
2. `read_section(post_id=ef012345, sec_id=introduction)` → conversational, anecdote-led prose.

Final reply:
```
The first post opens in a measured, technical register — definitions before examples. The second leads with an anecdote and stays conversational. Same topic, very different voices.
```

### Example 4: Category=check, metadata divergence

Resolved Details:
- Posts: abcd0123, ef012345
- Category: check

Trajectory:
1. `read_metadata(post_id=abcd0123)` → `{status: 'published', tags: ['ml','agents'], updated_at: '2026-04-12'}`.
2. `read_metadata(post_id=ef012345)` → `{status: 'draft', tags: ['ml'], updated_at: '2026-05-01'}`.

Final reply:
```
The first is already published with broader tagging (ml + agents); the second is still a draft, narrower-tagged, and more recently edited. Worth lining up tags before shipping the second.
```
