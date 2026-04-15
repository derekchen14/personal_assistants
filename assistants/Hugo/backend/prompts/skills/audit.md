# Skill: audit

Audit a post for voice and style consistency against the user's previous writing.

## Behavior
1. `find_posts` to locate reference posts (published) for comparison. Limit to `reference_count` if filled, else 5.
2. `compare_style` to compare the target post's metrics against the references.
3. `editor_review` to check the post content against the editorial style guide.
4. `inspect_post` to get structural metrics.
5. Flag inconsistencies in tone, terminology, formatting, and voice.
6. This is **read-only** — do not edit the post. The policy handles threshold confirmation before any edits.

## Output
Respond with **JSON** in this shape:

```json
{
  "post_id": "...",
  "title": "...",
  "style_score": 0.82,
  "tone_match": "mostly consistent",
  "sections_affected": 2,
  "total_sections": 5,
  "findings": [
    "<short finding>",
    "<short finding>"
  ],
  "suggestions": [
    "<actionable suggestion>"
  ]
}
```

## Few-shot example

User: "Check if the synthetic data post matches my usual writing style"

Correct tool trajectory:
1. `find_posts(query='', status='published')` → returns 5 published posts.
2. `compare_style(post_id=..., references=[...])` → returns `{style_score: 0.78, sections_affected: 2}`.
3. `editor_review(post_id=...)` → returns findings.

Correct final reply:
```json
{
  "post_id": "abc123",
  "title": "Synthetic Data Generation for Classification",
  "style_score": 0.78,
  "tone_match": "mostly consistent",
  "sections_affected": 2,
  "total_sections": 5,
  "findings": [
    "Motivation uses longer sentences than prior posts (avg 28 words vs 18)",
    "Takeaways omits the signature bullet summary that your other posts use"
  ],
  "suggestions": [
    "Tighten Motivation's opening with polish",
    "Add a 3-bullet summary at the end of Takeaways"
  ]
}
```

## Slots
- `source` (required): The post to audit.
- `reference_count` (optional): How many previous posts to compare against.
- `threshold` (optional): Percentage of sections affected that triggers confirmation. Default 0.2.

## Important
- `Resolved entities` gives you `post_id` — use it instead of extra `read_metadata` calls.
- This flow never calls `revise_content`, `write_text`, or any other write tool — the policy escalates to the user if the threshold is exceeded.
