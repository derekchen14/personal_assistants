# Skill: find

Find posts, drafts, and notes matching the user's query.

## Behavior
1. `find_posts(query=<query>)` to search.
2. Expand the user's query with synonyms in your candidate terms (e.g. "augmentation" → also try "synthetic data", "data generation"). Run at most 3 queries; deduplicate by `post_id`.
3. If `count` is set, limit results to that many.
4. Skim each item's `preview_snippet` to write a one-line relevance note.

## Output
Respond with **JSON** in this shape:

```json
{
  "query": "...",
  "count": 3,
  "results": [
    {"post_id": "...", "title": "...", "status": "draft|published|note", "relevance": "<one-line note>"}
  ]
}
```

If no results, set `results: []` and add a `notes` field explaining no matches.

## Few-shot example

User: "Search for posts about data augmentation"

Correct tool trajectory:
1. `find_posts(query='data augmentation')` → 2 hits.
2. `find_posts(query='synthetic data')` → 1 additional hit.

Correct final reply:
```json
{
  "query": "data augmentation",
  "count": 3,
  "results": [
    {"post_id": "abc123", "title": "Synthetic Data Generation for Classification", "status": "draft", "relevance": "Covers LLM-based augmentation as the primary technique."},
    {"post_id": "def456", "title": "Hard Negatives in Retrieval", "status": "published", "relevance": "Brief section on augmenting negatives via paraphrase."},
    {"post_id": "ghi789", "title": "Mixup for Tabular Data", "status": "published", "relevance": "Direct take on a classical augmentation method."}
  ]
}
```

## Slots
- `query` (required): The search keyword/phrase.
- `count` (optional): Cap on result count.

## Important
- Do not invent results. If `find_posts` returns no items for any expanded term, return an empty `results` list.
- Prefer recall over precision on the first call; the user can ask follow-ups to narrow.
