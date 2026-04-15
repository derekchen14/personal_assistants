# Skill: brainstorm

Brainstorm new topic ideas for a post, alternatives for wording, or new angles for existing themes.

## Behavior

### Mode A — Topic / theme (when `topic` is filled)
- `brainstorm_ideas(topic=<topic>)` for creative angles.
- Optionally `find_posts(query=<topic>)` to avoid repeating what the user already wrote.
- Produce 3–5 distinct ideas. Vary format, audience, and angle.

### Mode B — Highlighted word or phrase (when `source.snip` is filled)
- The user highlighted a phrase; suggest 2–3 alternatives that match the post's tone.
- `read_section(post_id=..., sec_id=...)` if you need the surrounding context.

## Output
Respond with **JSON** in one of the two shapes below.

Mode A (topic):
```json
{
  "mode": "topic",
  "topic": "...",
  "ideas": [
    {"title": "...", "hook": "<one-line thesis>"},
    {"title": "...", "hook": "..."}
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

## Few-shot example

User: "Brainstorm some alternative angles for the synthetic data topic"

Correct tool trajectory:
1. `brainstorm_ideas(topic='synthetic data generation')` → returns candidate angles.
2. `find_posts(query='synthetic data')` → returns existing coverage.

Correct final reply:
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

## Slots
- `topic` (elective): Broad topic to brainstorm ideas about.
- `source` (elective): Post/section/snippet grounding when highlighting a phrase.

## Important
- Do not propose more than 5 ideas. Fewer strong ideas beat many weak ones.
- Match the user's stated interests and prior post themes.
