# Fixes — `simplify` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/simplify.md` — § A (Guard clauses, Persistence calls), § B (Skill contract, Few-shot coverage), § Known gaps #1–#4
- Primary SUMMARY.md themes: **Theme 1** (skill/policy ownership — persistence), **Theme 2** (unexemplified slots — `image`, `guidance`), **Theme 7** (`tool_succeeded` helper)
- Theme feedback: `_theme1_feedback.md` § `simplify` (persistence contract), `_theme2_feedback.md` § `simplify`, `_theme7_feedback.md` § Helper 2
- Part 2: > **Alignment.** Fixes land under [§ 8 Determinism boundaries](../best_practices.md#8-determinism-boundaries) and [§ 1 Skill-prompt structure](../best_practices.md#1-skill-prompt-structure) — see [Deterministic Core, Agentic Shell — davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html) on a single owner per side-effect (skill owns `revise_content`; policy's write is a gated backup only) and [Anthropic skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) on concrete exemplars for every declared slot (`image`, `guidance`).

## Changes that landed

### 1. Skill owns persistence, with a policy-level backup (Theme 1)

**What changed.** The skill prompt (`backend/prompts/skills/simplify.md`) now states in its `## Important` block: "The skill owns persistence — you MUST call `revise_content` to save the simplified text. The policy does not save automatically." The earlier line claiming "policy saves automatically" has been deleted. `simplify_policy` in `backend/modules/policies/revise.py` (lines 224–227) keeps a **guarded** backup persistence path:

```python
already_saved, _ = self.engineer.tool_succeeded(tool_log, 'revise_content')
if post_id and sec_id and text and not already_saved:
    self._persist_section(post_id, sec_id, text, tools)
```

**Why.** Known Gap #3 flagged a potential double-write because the skill called `revise_content` AND the policy unconditionally called `_persist_section`. The resolved contract (Theme 1 feedback TL;DR: "the skill owns persistence") picks one owner and makes the policy's `_persist_section` call a recovery path only when the skill skipped the tool — matching the prompt's retry-once-then-error rule.

**Files touched.** `backend/modules/policies/revise.py`, `backend/prompts/skills/simplify.md`.

### 2. `image` and `guidance` slot exemplars (Theme 2)

**What changed.** Three new few-shot blocks in `skills/simplify.md` sit after the original paragraph example:

- **Image — intent clear**: `image` slot filled AND the user said "replace" or "remove". Proceed with `revise_content` / `remove_content`. Explicit prohibition on `insert_media` (that's the `add` flow).
- **Image — intent unclear**: `image` filled but the user did NOT specify replace vs. remove. The skill emits `{"target": ..., "needs_clarification": "simplify image by replacing ... or removing entirely?"}` and skips tool calls. The skill's `## Slots` block codifies this as a `confirmation`-level signal.
- **Guidance — soft preference**: `guidance` carries style hints ("more conversational", "keep it academic"). Treated as a soft preference — honor it while the primary simplification goal wins any conflict; the summary line records the trade-off.

Also: the `## Behavior` block now explicitly **permits paragraph reformatting** (e.g. normalizing blank lines) per `_theme2_feedback.md` § `simplify` (d).

**Why.** Known Gaps #1 and #2 called out `image` and `guidance` as declared-but-unused. Theme 2 feedback answers (d.1, d.2) specified the exact semantics: confirmation-level ambiguity for unclear image intent, soft-preference treatment for `guidance`.

### 3. `self.engineer.tool_succeeded` gate (Theme 7)

**What changed.** The `already_saved` check in (1) is the sole Theme 7 migration site. `(bool, dict)` return — only the bool is consumed.

**Why.** The user accepted only `tool_succeeded` from the Theme 7 proposal; `guard_slot`, `complete_with_card`, and `stack_on` were rejected. See `_theme7_feedback.md` § Overall Feedback.

## Architectural decisions applied

- **AD-6** (failure modes): unclear image intent is an **ambiguity** (`confirmation` level), surfaced via the skill's `needs_clarification` JSON field — NOT an error frame and NOT a tool-call failure. Ambiguous user intent lives in channel 3.
- **AD-5** (terminology): the skill "emits" / "declares"; it does not "fire".

## Open follow-ups

- The `needs_clarification` string is **emitted by the skill**, but `simplify_policy` does not yet parse the JSON to hoist it into an explicit `self.ambiguity.declare('confirmation', ...)` call. Today the field reaches the user via `frame.thoughts`, which works for RES but misses the AmbiguityHandler bookkeeping. Wire-up is noted as a future pass once other flows (rework, polish) adopt the same pattern — centralising the parse in a helper would be the time to lift it.
- Paragraph-5-in-3-paragraph-section edge case from Known Gap #4 is still skill-level heuristic; no policy guard added.
