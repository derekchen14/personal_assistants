This skill answers questions about metrics and metadata. The user wants numbers or facts about their content — word count, section count, reading time, image count, post size, tags, featured image, publication/edit/scheduled dates, channels, status — for one post or across the library. Gather the data with your read tools, then report it in 1–2 sentences.

## Process

1. Read the filled slots from `<resolved_details>`:
   a. `Source`: the post to inspect (may be empty for library-wide questions like "how many posts did I publish last month?").
   b. `Metrics`: the specific metrics or metadata fields the user asked about.
   c. `Threshold`: an optional bound — when present, say whether the metric is above or below it.
2. Post-scoped question → call `read_metadata(post_id)`; it returns title, status, tags, dates, and per-section summaries with sentence counts. Derive what the user asked for (e.g. section count = number of sections; reading time from word count).
3. Library-wide question → call `find_posts` (optionally filtered) and count or aggregate over the results.
4. Channel question (where is it published, is the channel live) → call `channel_status`.
5. If `Threshold` is filled, compare and state the verdict plainly ("1,840 words — over your 1,500 limit").
6. Report the numbers directly. Do NOT modify posts — inspect is read-only.

## Error Handling

If the question names a post you cannot resolve, call `declare_ambiguity(level='partial', metadata={'missing': 'source', 'entity': 'post'})`.

If a read tool fails outright, call `execution_error(violation='tool_error', message='<which tool> failed')`.

## Tools

### Task-specific tools

- `read_metadata(post_id, include_outline, include_preview)` — the primary source for post-scoped metrics and metadata.
- `find_posts(query, tags, status)` — library-wide counts and date-filtered questions.
- `channel_status(channel)` — publishing-channel facts.

### General tools

- `execution_error(violation, message)`
- `declare_ambiguity(**params)`
- `read_scratchpad(**params)`
- `read_flow_stack(details)`

## Few-shot examples

### Example 1 — single-post metrics

Resolved Details:
- Source: post 8a9b0c1d (Designing Idempotent APIs)
- Metrics: word count, reading time

Trajectory: `read_metadata(post_id='8a9b0c1d')` → sections with sentence counts → derive ~1,400 words, ~6 minutes.

Final reply:
```
Designing Idempotent APIs runs about 1,400 words — roughly a 6-minute read.
```

### Example 2 — library-wide count

Resolved Details:
- Source: (empty)
- Metrics: posts published last month

Trajectory: `find_posts(status='published')` → filter by publication date → 3 match.

Final reply:
```
You published 3 posts last month: Caching at the Edge, Postgres for Analytics, and Feature Flags in Practice.
```

### Example 3 — threshold check

Resolved Details:
- Source: post 4b5c6d7e (Week One Playbook)
- Metrics: word count
- Threshold: 1500

Trajectory: `read_metadata(post_id='4b5c6d7e')` → ~1,840 words → compare against 1,500.

Final reply:
```
Week One Playbook is about 1,840 words — over your 1,500-word target by ~340.
```

### Example 4 — metadata facts

Resolved Details:
- Source: post d1e2f3a4 (Threat Modeling Basics)
- Metrics: status, channels

Trajectory: `read_metadata(post_id='d1e2f3a4')` → status draft, no channels yet.

Final reply:
```
Threat Modeling Basics is still a draft — it hasn't gone out on any channel.
```

### Example 5 — unresolvable post

Resolved Details:
- Source: (empty)
- Metrics: image count

Trajectory:
1. The question is post-scoped ("how many images does it have?") but no post resolves from context.
2. `declare_ambiguity(level='partial', metadata={'missing': 'source', 'entity': 'post'})`. Ask which post, then end turn.
