# Skill: release

Publish a post to a specific platform channel.

## Behavior
1. `channel_status(channel=<channel>)` to verify the channel is connected.
2. `release_post(post_id=..., channel=<channel>)` to publish.
3. The policy flips the post's status to `published` automatically after success.
4. If publication fails, surface the error and suggest a fix.

## Output
Respond with **JSON** in this shape:

```json
{
  "post_id": "...",
  "title": "...",
  "channel": "...",
  "status": "published" | "failed",
  "url": "https://...",
  "notes": "<one-sentence summary or error message>"
}
```

## Few-shot example

User: "Publish the synthetic data post to the blog"

Correct tool trajectory:
1. `channel_status(channel='blog')` → returns `{ok: true}`.
2. `release_post(post_id=..., channel='blog')` → returns `{url: "https://blog.example.com/synthetic-data"}`.

Correct final reply:
```json
{
  "post_id": "abc123",
  "title": "Synthetic Data Generation for Classification",
  "channel": "blog",
  "status": "published",
  "url": "https://blog.example.com/synthetic-data",
  "notes": "Published successfully; ready to syndicate."
}
```

## Slots
- `source` (required): The post to publish.
- `channel` (required): The destination channel (`blog`, `medium`, `linkedin`, etc.). Defaults to `mt1t` if not given.

## Important
- `Resolved entities` gives you `post_id` — use it instead of extra `read_metadata` calls.
- Do not retry `release_post` on failure unless the user explicitly asks. Explain the failure instead.
