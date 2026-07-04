---
name: "brainstorm"
description: "come up with new ideas or angles for a given topic, word, or phrase; may include hooks, opening lines, synonyms, or new perspectives the user can choose from"
version: 3
tools:
  - brainstorm_ideas
  - find_posts
  - search_notes
  - read_section
---

This skill produces creative angles for a topic, or alternative phrasings for a highlighted snippet. Which case applies depends on the filled slots: `topic` drives idea generation, `source.snip` drives phrase alternatives.

**Your turn ends only when you emit the JSON output described below. Tool calls are optional context-gathering — do not stop after a tool call.**

## Process

1. Read `<resolved_details>` for the active slots.
2. When `topic` is filled:
  a. If a `source` post is also resolved, you may call `read_section(post_id, sec_id)` once to gain context. Skip when no source is resolved.
  b. You may call `find_posts(query=<topic>)` or `search_notes(query=<topic>)` to check prior coverage. Do NOT call these tools if you already have enough material to ideate.
  c. If `ideas` is filled, treat its items as the user's own seed list — do NOT repeat them. Generate complementary ideas that extend the seeded direction.
  d. Emit the final JSON (see Output) as your last message. Produce 3–5 distinct, diverse ideas varying angle and style.
3. When `source.snip` is filled:
  a. Call `read_section(post_id, sec_id)` for surrounding tone context.
  b. Emit the final JSON (see Output) as your last message. Suggest 2–3 alternatives that match the post's existing tone.
4. Cap at 5 ideas / 3 alternatives. Fewer strong ideas beat many weak ones.

## Error Handling

If neither `topic` nor `source.snip` is filled, call `handle_ambiguity(level='specific', metadata={'missing': 'topic'})`.

Brainstorming is tolerant of tool gaps — if `read_section` or `find_posts` fails, fall back to LLM-only ideation based on the topic. Do NOT call `execution_error`.

## Tools

### Task-specific tools

- `brainstorm_ideas(topic=...)` — gathers prior coverage (posts + notes) for the topic, useful as a single dedup pass.
- `find_posts(query=...)` — dedup check against prior coverage.
- `search_notes(query=...)` — surface user's saved notes on the topic.
- `read_section(post_id, sec_id)` — fetch existing content for context (topic depth or snippet tone).

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Output

When `topic` is filled:
```json
{
  "topic": "...",
  "ideas": [
    {"title": "...", "hook": "<one-line thesis>"},
    ...
  ]
}
```

When `source.snip` is filled:
```json
{
  "original": "the highlighted phrase",
  "alternatives": ["option 1", "option 2", "option 3"]
}
```

## Few-shot examples

### Example 1: Topic angles

Resolved Details:
- Topic: synthetic data generation
- Source: post=abc12345

Trajectory:
1. `read_section(post_id='abc12345', sec_id='motivation')` → existing framing focuses on cost; leaves quality/QA gaps unaddressed.
2. `find_posts(query='synthetic data')` → 1 prior coverage post.

Final reply:
```json
{
  "topic": "synthetic data generation",
  "ideas": [
    {"title": "When synthetic data beats human labels", "hook": "A cost/quality tradeoff teardown"},
    {"title": "Denoising the noise you created", "hook": "How to QA synthetic training sets"},
    {"title": "Synthetic-first intent classifiers", "hook": "Lessons from shipping one in production"}
  ]
}
```

### Example 2: Topic angles seeded by the user

Resolved Details:
- Topic: sales playbook
- Ideas: ["prospecting", "qualifying", "closing"]

Trajectory:
1. `find_posts(query='sales playbook')` → no prior coverage.

Final reply:
```json
{
  "topic": "sales playbook",
  "ideas": [
    {"title": "Discovery rituals", "hook": "How top reps run the first 15 minutes"},
    {"title": "Objection handling under pressure", "hook": "Scripts vs. improvisation"},
    {"title": "Post-sale handoff", "hook": "Why deals churn after the win"}
  ]
}
```

### Example 3: Phrase alternatives

Resolved Details:
- Source: post=abcd0123, section=motivation, snippet="dirt cheap"

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=motivation)` → context (formal-to-conversational tone).

Final reply:
```json
{
  "original": "dirt cheap",
  "alternatives": ["radically cheap", "an order of magnitude cheaper", "vanishingly inexpensive"]
}
```

### Example 4: Neither topic nor snippet filled

Resolved Details:
- (no topic, no source snippet)

Trajectory:
1. Neither `topic` nor `source.snip` is present in the resolved details.
2. `handle_ambiguity(level='specific', metadata={'missing': 'topic'})`. Ask what to brainstorm about, then end turn.

### Example 5: Topic seeded by a saved note

Resolved Details:
- Topic: developer onboarding

Trajectory:
1. `search_notes(query='developer onboarding')` → a saved note on cutting time-to-first-commit.

Final reply:
```json
{
  "topic": "developer onboarding",
  "ideas": [
    {"title": "Time to first commit", "hook": "Treat the first pull request as the onboarding metric that matters"},
    {"title": "The buddy system, measured", "hook": "What pairing new hires with a mentor actually changes"},
    {"title": "Docs that survive contact", "hook": "Why setup guides rot and how to keep them honest"}
  ]
}
```
