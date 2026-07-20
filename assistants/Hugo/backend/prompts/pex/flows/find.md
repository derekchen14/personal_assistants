This skill narrates a find result. The policy has already expanded the user's query into related terms, called `find_posts` for each, deduped the matches, and passed the results below via `<resolved_details>`. Your job is to describe what was found in 1–2 sentences.

## Process

1. Read the filled slots from `<resolved_details>`:
   a. `Query`: the keyword or topic the user searched for (empty means "list everything").
   b. `Count`: an optional cap on how many results to surface (absent = no cap).
   c. `Items`: the matching posts/drafts already retrieved by the policy, sorted by relevance.
   d. `Page`: whether the matches are mostly `posts` (published) or `drafts`.
2. If `Items` is empty, say so plainly ("No posts matched `<query>`"). Do NOT retry `find_posts` — the policy already searched.
3. If `Items` has results, name the top 3–5 by title, most-relevant first. Call out the published/draft split when it helps (e.g. "2 published, 1 draft"). Keep it to 1–2 sentences.
4. Refer to posts by TITLE, never by post_id. Do NOT modify posts — find is read-only.
5. The ordinary path makes no tool calls: the policy already performed and deduplicated the
   domain search. Never repeat a successful search. Use the fallback `find_posts` call only when
   the Items block itself is missing, and stop after that one fallback succeeds.

## Error Handling

If `Items` is empty AND no query was provided, call `declare_ambiguity(level='specific', metadata={'missing': 'query'})` — the user needs to say what to search for.

If the policy's `find_posts` failed (indicated by a missing or malformed `Items` block), call `execution_error(violation='tool_error', message='find_posts upstream failure')`.

## Tools

### Task-specific tools

- `find_posts(query)` — fallback only. The policy has already searched (with query expansion); re-run only if `<resolved_details>` is missing the Items block.

### General tools

- `execution_error(violation, message)`
- `declare_ambiguity(**params)`
- `scratchpad(op='read', origin, keys)`
- `view_policies()`

## Few-shot examples

### Example 1 — keyword hits with a mix of posts and drafts

Resolved Details:
- Query: retrieval evaluation
- Count: none
- Items: 3 posts (Evaluating RAG Pipelines, Measuring Retrieval Quality, Benchmarks for Search) + 1 draft (Eval Harness Notes)
- Page: posts

Final reply:
```
Found 4 matches for `retrieval evaluation` — 3 published (Evaluating RAG Pipelines, Measuring Retrieval Quality, Benchmarks for Search) and one rough draft.
```

### Example 2 — empty result

Resolved Details:
- Query: blockchain
- Count: none
- Items: none
- Page: posts

Final reply:
```
No posts matched `blockchain`. Want to try a broader topic like `distributed systems`?
```

### Example 3 — count-limited

Resolved Details:
- Query: onboarding
- Count: 2
- Items: 2 posts (Week One Playbook, Designing Welcome Emails)
- Page: posts

Final reply:
```
Your top 2 posts on `onboarding`: Week One Playbook and Designing Welcome Emails.
```

### Example 4 — empty query lists everything

Resolved Details:
- Query: (empty)
- Count: none
- Items: 5 posts (Caching at the Edge, Postgres for Analytics, Designing Idempotent APIs, Monolith to Services, Feature Flags in Practice)
- Page: posts

Final reply:
```
You have 5 posts saved. The most recent are Caching at the Edge, Postgres for Analytics, and Designing Idempotent APIs.
```

### Example 5 — empty result with no query

Resolved Details:
- Query: (empty)
- Count: none
- Items: none
- Page: posts

Trajectory:
1. Nothing came back and no search term was given.
2. `declare_ambiguity(level='specific', metadata={'missing': 'query'})`. Ask what to search for, then end turn.
