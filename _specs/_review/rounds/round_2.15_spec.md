# Round 2.15 — Post-Reference Resolution

Maps to **Master Plan · Round 2 (PEX)**. Proposal spec — evidence comes from the 2026-07-18 eval
run (report `evals_20260718_095728.json`). Split out of round 2.14 because it lives in a
different layer: the content service's search and the policies' fuzzy resolver, not the
flow/stack machinery. Depends on nothing in 2.14 and blocks nothing there.

---

## 2.15.1 — Multi-word and nickname references never resolve

### Problem

Evidence: B02.C16 — eight turns, zero completed work. The user referred to "the grid-batteries
draft"; the standing post is titled differently, and every turn ended in a `missing_reference`
error artifact. "lightbulb inventors" likewise returned zero results. Once a reference misses,
there is no recovery path: the same unresolvable string is retried each turn and the conversation
never gets a foothold.

### Root cause

Three verified layers, each too literal:

1. **`find_posts` is a whole-phrase substring match** (`post_service.py:48-61`): the full query
   string must appear contiguously in title+category+tags, else in the post content. "grid
   batteries" matches nothing unless those exact adjacent words occur somewhere.
2. **`_resolve_post_id` only varies the query by status suffix** (`policies/base.py:82-98`): it
   tries the identifier as given and with trailing status words ("draft", "post", ...) stripped,
   then exact-title match, then first-result. No token splitting, no hyphen handling, no fuzzy
   title pass.
3. The research policy's `_expand_query` covers hyphens only, and `_resolve_post_id` does not go
   through it at all.

### Target changes

1. **`find_posts` matches metadata per token** (`post_service.py:48-54`): split the query on
   whitespace/hyphens; a post matches when EVERY token appears in the searchable string
   (title+category+tags). The whole-phrase content search stays as the fallback exactly as
   today — token-AND against full content would be noise.

   ```python
   tokens = query.replace('-', ' ').split()
   if not all(tok in searchable for tok in tokens):
       # fall through to the existing whole-phrase content search
   ```

2. **`_resolve_post_id` adds a fuzzy title pass before giving up** (`policies/base.py:89-99`),
   mirroring `_resolve_sec_id`'s use of difflib (`base.py:109`): after the candidate queries
   miss, list titles via `find_posts` (no query, raised limit) and take
   `difflib.get_close_matches(identifier.lower(), titles, n=1, cutoff=0.6)`. The de-hyphenated
   form of the identifier joins the candidate list so "grid-batteries" and "grid batteries"
   behave identically.

## 2.15.2 — `missing_reference` offers the near misses instead of a dead end

### Problem

When resolution fails, the error artifact says only "Could not find the specified post"
(`base.py:135-136`). The user has no way to know what Hugo CAN see, so they repeat the same
nickname and the loop continues — B02.C16's whole shape.

### Target change

Reuse the existing grounding-choices mechanics (round 2.13.1) — no new concepts: on a resolution
miss, `resolve_source_ids` runs one `find_posts` with the best single token of the reference (the
longest token, ties to the first) and, when items come back, writes them as `grounding.choices`
and asks a `partial` ambiguity listing the titles. The next turn's fill resolves the pick from
the shown candidates through the standing 2.13.1 path. When even the token query returns nothing,
the artifact lists the most recently updated posts as the choices instead, so the reply always
names real options.

### Verification

- Deterministic service checks: "grid batteries", "grid-batteries", and "batteries grid" all
  find the target post via token-AND; a one-token typo resolves through the fuzzy title pass;
  a nonsense reference produces choices, not a bare error.
- Replay B02.C16: turn 1 either resolves outright or asks with real titles; the conversation
  completes work by turn 3.

## Out of scope (recorded, not taken)

- Embedding or semantic search over post content — the 32-post library does not need it, and the
  eval speed doctrine rules out anything heavier than metadata scans.
- Nickname memory (persisting "grid-batteries" → post id after one resolution) — MEM territory;
  reconsider only if the choices path proves too chatty in live use.

## Verification

1. `run_suite.py --tests` green; existing service tests updated where the match rule changed.
2. Rerun B02.C16 (plus B03.C14 as the regression canary for ordinary finds) against
   `evals_20260718_095728.json`.

## Todo List

- [ ] **T1 — token-AND metadata match** in `find_posts` (`post_service.py:48-54`), hyphens
  normalized to spaces; whole-phrase content fallback unchanged.
- [ ] **T2 — fuzzy title pass** in `_resolve_post_id` (`policies/base.py:89-99`): de-hyphenated
  candidate + difflib close-match over the full title list before returning None.
- [ ] **T3 — near-miss choices on `missing_reference`**: `resolve_source_ids` writes
  `grounding.choices` from the best-token query (or the latest posts) and asks a `partial`
  ambiguity naming the titles (`base.py:133-137`).
- [ ] **T4 — replay B02.C16 + B03.C14** and record the before/after against
  `evals_20260718_095728.json`.
