# Fixes — `inspect` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/inspect.md`
- Relevant sections: § Persistence calls, § Frame shape, § Output shape mismatch, § No card block
- Primary SUMMARY.md themes: **T3 (output-shape drift)**, **T5 (cross-turn findings channel)**
- Theme feedbacks: `inventory/_theme3_feedback.md § inspect`, `inventory/_theme5_feedback.md § inspect`

## Changes that landed

### Skill file deleted — `inspect` is now fully deterministic

- **What changed:** `backend/prompts/skills/inspect.md` was deleted. The policy no longer calls `llm_execute`; `inspect_policy` (in `backend/modules/policies/research.py` lines ~132-165) resolves the post id, calls the `inspect_post` tool directly with an optional `metrics=[aspect]` filter, and returns a `DisplayFrame(origin='inspect', metadata={'metrics': metrics})`.
- **Why:** `_theme3_feedback.md § inspect` resolved this as "inspect flow likely doesn't need a skill. Once the slot is filled, it just calls the tool directly, which returns JSON." The skill's JSON contract was never enforced, and the policy already had the tool result in hand — the skill was pure indirection.
- **Theme:** Theme 3 (output-shape drift). The drift is eliminated by removing the LLM layer that produced it.
- **Files touched:**
  - `backend/prompts/skills/inspect.md` (deleted)
  - `backend/modules/policies/research.py` — `inspect_policy` rewritten to deterministic path
  - `backend/components/flow_stack/flows.py` — `InspectFlow.tools` trimmed from 5 → `['inspect_post']` (the LLM no longer picks among readability/link/section helpers; the aspect filter is driven by the `aspect` CategorySlot instead)

### RES template owns the user-facing message

- **What changed:** The spoken utterance for inspect is produced by `_format_inspect_message` in `backend/modules/templates/research.py`. The template reads `frame.metadata['metrics']` and walks a known key order (`word_count`, `section_count`, `estimated_read_time`, `image_count`, `link_count`, …) into a human-readable sentence like "Your post has 1,234 words, 5 sections, 6-minute read." A fallback path stringifies unknown metric keys with human labels, and an `empty_sections` list is appended if present.
- **Why:** Matches the "response text in RES templates, not frame.thoughts" feedback rule in `MEMORY.md` (FeedbackThoughtsVsTemplate). Policies push data to frame blocks/metadata; templates produce the spoken line.
- **Theme:** Theme 3 secondary — the metrics dict is now the stable contract between policy and template.
- **Files touched:**
  - `backend/modules/templates/research.py` — `_format_inspect_message` + `_INSPECT_LABELS`

### Scratchpad write under AD-1 convention

- **What changed:** After the tool succeeds, `inspect_policy` writes to scratchpad under key `'inspect'` with the required fields `version: '1'`, `turn_number: context.turn_id`, `used_count: 0`, plus `post_id` and the `metrics` dict.
- **Why:** Theme 5 / AD-1. Step 13 polish (and any future chained flow) can look up the live inspect metrics from the scratchpad without re-calling the tool.
- **Theme:** Theme 5 (cross-turn findings channel).
- **Files touched:**
  - `backend/modules/policies/research.py` — `inspect_policy` lines ~155-162

## Architectural decisions applied

- **AD-1** (scratchpad channel) — producer write under key `'inspect'`, convention-compliant (`version`, `turn_number=context.turn_id`, `used_count=0`).
- **AD-2** (no "informed mode") — metrics are always written regardless of whether a downstream flow consumes them; step 13 polish reads the scratchpad conditionally.
- **AD-5** (terminology) — InspectFlow "calls a tool"; no NLU "firing" language introduced.
- **AD-6** (three failure modes) — tool-call failure path returns `DisplayFrame(origin='inspect', thoughts=<tool _message>)`; no ambiguity declared on tool failure. This path predates AD-6 and is acceptable as-is since inspect is read-only.

> **Part 2 alignment.** This fix aligns with [§ 8 Determinism boundaries](../best_practices.md#8-determinism-boundaries) and [§ 9 Cross-turn state / findings channel](../best_practices.md#9-cross-turn-state--findings-channel). See [Deterministic Core, Agentic Shell — davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html) on deleting the LLM indirection when the task is pure discovery (tool result is already JSON) and [State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026) on structured-scratchpad conventions with `version` / `turn_number` / `used_count` metadata.

## Open follow-ups

- `check_readability` and `check_links` were dropped from `InspectFlow.tools` along with the skill delete. If a user later needs those specifically, they will come back either as new flows or as extra optional tool calls driven by a richer `aspect` taxonomy. Not urgent.
- The inspect RES template currently handles the happy-path metric keys only. If `inspect_post` starts returning new keys (e.g. readability score), `_INSPECT_LABELS` needs to be extended.
- No eval assertion yet that `memory.read_scratchpad()['inspect']['metrics']['word_count']` matches the tool result. Part 4 cross-flow integration test (Theme 5 § Cross-flow integration test) covers this.
