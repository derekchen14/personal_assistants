# Skill: inspect

Inspect a post and report its metrics.

## Behavior
1. Use `inspect_post` to compute word count, read time, section count, readability.
2. Use `check_readability` on individual sections if the user asked about readability specifically.
3. Use `check_links` to find and validate links/images if the user asked about those.
4. Use `read_section` only if the LLM side needs raw content to answer.
5. If the `aspect` slot is filled, report only that metric; otherwise report the full summary.

## Output
Respond with **JSON** in this shape:

```json
{
  "post_id": "...",
  "title": "...",
  "metrics": {
    "word_count": 1234,
    "section_count": 5,
    "read_time_minutes": 6,
    "image_count": 2,
    "link_count": 8
  },
  "notes": "<one-sentence summary, e.g. 'Average section length ~250 words'>"
}
```

If `aspect` is filled, include only that key under `metrics` and omit the others.

## Few-shot example

User: "What are the metrics on the synthetic data post?"

Correct tool trajectory:
1. `inspect_post(post_id=...)` → returns `{word_count: 1320, section_count: 5, estimated_read_time: 7, image_count: 1, link_count: 4}`.

Correct final reply:
```json
{
  "post_id": "abc123",
  "title": "Synthetic Data Generation for Classification",
  "metrics": {
    "word_count": 1320,
    "section_count": 5,
    "read_time_minutes": 7,
    "image_count": 1,
    "link_count": 4
  },
  "notes": "Medium-length post, ~264 words per section, well-linked."
}
```

## Slots
- `source` (required): The post to inspect.
- `aspect` (optional): `word_count`, `num_sections`, `time_to_read`, `image_count`, `num_links`, `post_size`.
- `threshold` (optional): A reference value the user wants to compare against.

## Important
- `Resolved entities` gives you `post_id` and section IDs — use them instead of extra `read_metadata` calls.
- Do not compute metrics by reading every section manually — use `inspect_post` for the aggregate.
