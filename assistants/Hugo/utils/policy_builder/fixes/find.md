# Fixes — `find` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/find.md`
- Relevant sections: § Persistence calls, § Frame shape, § Skill-policy contract mismatch, § List block metadata
- Primary SUMMARY.md themes: **T1 (skill/policy contract confusion)**, **T3 (output-shape drift)**, **T5 (cross-turn findings channel)**
- Theme feedbacks: `inventory/_theme3_feedback.md § find`, `inventory/_theme5_feedback.md § find`

## Changes that landed

### Skill file deleted — `find` is fully deterministic

- **What changed:** `backend/prompts/skills/find.md` was deleted. The policy (`backend/modules/policies/research.py :: find_policy`, lines ~167-224) is already deterministic: it reads the `query` ExactSlot and `count` LevelSlot, generates 3-4 related search terms via `_expand_query` (an LLM call inside the policy, not a skill), loops `find_posts` across those terms, dedupes by `post_id`, applies the optional count limit, and returns a list block. No `llm_execute`, no skill delegation.
- **Why:** `_theme3_feedback.md § find` resolved the Theme 1 mismatch exactly this way — the skill's "expand query and run 3 queries" instruction duplicated work the policy already did, and the skill's JSON contract was never parsed. Per the user's feedback ("we should not display things differently based on the number of returned results. We should always just loop through the list items. Enrich does not seem needed."), the enrichment proposal was also dropped.
- **Theme:** Theme 1 (skill/policy contract confusion). Theme 3 (output-shape drift) falls out for free — no skill, no drift.
- **Files touched:**
  - `backend/prompts/skills/find.md` (deleted)
  - `backend/modules/policies/research.py` — `find_policy` keeps the pre-existing deterministic body; no branching by result count

### Single list block, no per-count branches

- **What changed:** Per (d) feedback in `_theme3_feedback.md § find`, the policy no longer special-cases `n == 0` (empty thoughts, no block) or `n == 1` (one card block via `read_metadata`). Every non-error return path is a `DisplayFrame(origin='find')` with one list block carrying all items. A `page` hint (`'posts'` if published-count >= draft-count else `'drafts'`) is computed for the list block so the UI can pick a layout; `expanded_ids` is set when `n <= 8` so the frontend can opt into inline previews.
- **Why:** The user explicitly asked for a single, uniform shape so downstream consumers (step 12 audit, any Plan chain) don't branch on result count. Simpler template logic, fewer eval variants.
- **Files touched:**
  - `backend/modules/policies/research.py` — `find_policy` lines ~194-204

### Scratchpad write under AD-1 convention

- **What changed:** After the list block is built, `find_policy` writes to scratchpad under key `'find'` with the required fields `version: '1'`, `turn_number: context.turn_id`, `used_count: 0`, plus `query` (the verbatim user-entered term) and `items`. Each `items` entry is a projection of the `find_posts` hit: `{post_id, title, status, preview}`.
- **Why:** Theme 5 / AD-1. Downstream audit (step 12) needs `post_id + title + status + preview` per the user's answer in `_theme5_feedback.md § find`. No re-fetch required; polish at step 13 can also walk this list to decide which prior posts to cite.
- **Theme:** Theme 5 (cross-turn findings channel).
- **Files touched:**
  - `backend/modules/policies/research.py` — `find_policy` lines ~208-223

## Architectural decisions applied

- **AD-1** (scratchpad channel) — producer write under key `'find'`, convention-compliant (`version`, `turn_number=context.turn_id`, `used_count=0`, plus payload).
- **AD-5** (terminology) — policy "calls a tool" repeatedly for the expanded queries; no "fires" / "triggers" language.

> **Part 2 alignment.** This fix aligns with [§ 8 Determinism boundaries](../best_practices.md#8-determinism-boundaries) and [§ 9 Cross-turn state / findings channel](../best_practices.md#9-cross-turn-state--findings-channel). See [Deterministic Core, Agentic Shell — davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html) on deterministic discovery (no skill needed once the policy already expands queries and dedupes) and [State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026) on writing structured projections (`post_id + title + status + preview`) so downstream consumers use active memory rather than re-querying.

## Open follow-ups

- `_expand_query` still costs one LLM call per `find` invocation before any `find_posts` call. For short single-word queries this is overkill; consider skipping expansion when the query is one token long. Not urgent.
- The `page` hint is a UI concern bleeding into the policy. If more `page` values show up, push the heuristic into the frontend / RES template instead.
- Eval step 13 rubric does not yet assert that `memory.read_scratchpad()['find']['items']` contains a non-empty list of `post_id`/`title` projections — add in Part 4.
