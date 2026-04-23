---
name: "brainstorm"
description: "come up with new ideas or angles for a given topic, word, or phrase; may include hooks, opening lines, synonyms, or new perspectives the user can choose from"
version: 2
tools:
  - brainstorm_ideas
  - find_posts
  - search_notes
  - read_section
---

This skill produces creative angles for a topic OR alternative phrasings for a highlighted phrase. Two modes, decided by which slot is filled.

## Process

1. Read `<resolved_details>` for the active slots:
   a. `topic` filled → Mode A (topic angles).
   b. `source.snip` filled → Mode B (phrase alternatives).
2. **Mode A — Topic angles:**
   a. Call `brainstorm_ideas(topic=<topic>)` for candidate angles.
   b. Optionally call `find_posts(query=<topic>)` to avoid duplicating prior coverage.
   c. Produce 3–5 distinct ideas, varying format, audience, and angle.
3. **Mode B — Phrase alternatives:**
   a. Call `read_section(post_id, sec_id)` if you need surrounding context for tone matching.
   b. Suggest 2–3 alternatives that match the post's existing tone.
4. Cap at 5 ideas / 3 alternatives. Fewer strong ideas beat many weak ones.

## Error Handling

If neither `topic` nor `source.snip` is filled, call `handle_ambiguity(level='partial', metadata={'missing_entity': 'topic_or_snippet'})`.

If `brainstorm_ideas` fails for Mode A, fall back to LLM-only ideation based on the topic. Do NOT call `execution_error` — brainstorming is tolerant of tool gaps.

## Tools

### Task-specific tools

- `brainstorm_ideas(topic=...)` — main worker for Mode A.
- `find_posts(query=...)` — dedup check against prior coverage.
- `search_notes(query=...)` — surface user's saved notes on the topic.
- `read_section(post_id, sec_id)` — context for Mode B tone matching.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Output

Mode A (topic):
```json
{
  "mode": "topic",
  "topic": "...",
  "ideas": [
    {"title": "...", "hook": "<one-line thesis>"},
    ...
  ]
}
```

Mode B (highlight):
```json
{
  "mode": "highlight",
  "original": "the highlighted phrase",
  "alternatives": ["option 1", "option 2", "option 3"]
}
```

## Few-shot examples

### Example 1: Topic angles

Resolved Details:
- Topic: synthetic data generation

Trajectory:
1. `brainstorm_ideas(topic='synthetic data generation')` → 5 candidate angles.
2. `find_posts(query='synthetic data')` → 1 prior coverage post.

Final reply:
```json
{
  "mode": "topic",
  "topic": "synthetic data generation",
  "ideas": [
    {"title": "When synthetic data beats human labels", "hook": "A cost/quality tradeoff teardown"},
    {"title": "Denoising the noise you created", "hook": "How to QA synthetic training sets"},
    {"title": "Synthetic-first intent classifiers", "hook": "Lessons from shipping one in production"}
  ]
}
```

### Example 2: Phrase alternatives

Resolved Details:
- Source: post=abcd0123, section=motivation, snippet="dirt cheap"

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=motivation)` → context (formal-to-conversational tone).

Final reply:
```json
{
  "mode": "highlight",
  "original": "dirt cheap",
  "alternatives": ["radically cheap", "an order of magnitude cheaper", "vanishingly inexpensive"]
}
```
