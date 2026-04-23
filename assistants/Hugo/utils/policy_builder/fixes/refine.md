# Fixes — `refine` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/refine.md`
- Relevant sections: § Guard clauses, § Persistence calls, § Tool plan, § Frame shape, § Stack-on triggers, § Known gaps (AGENTS.md step 3 regression: append vs. overwrite)
- Primary SUMMARY.md themes: **T1 (skill/policy contract confusion)**, **T4 (error-path gaps — contract violation)**, **T6 (stack-on opacity)**, **T7 (repeated tool-log pattern)**

## Changes that landed

### New `merge_outline` tool replaces `generate_outline` for refine

- **What changed:** A dedicated `merge_outline(post_id, content)` tool was introduced. Unlike `generate_outline` (which fully replaces the post's outline), `merge_outline` replaces matching sections in place and appends new ones, leaving untouched sections in the original order. `RefineFlow.tools` in `backend/components/flow_stack/flows.py` was swapped from `generate_outline` to `merge_outline`. The `refine_policy` now also injects `extra_resolved={'current_outline': content}` into `llm_execute` so the skill does not re-fetch via `read_metadata`. `skills/refine.md` was rewritten: it now points at `current_outline` in Resolved entities, documents the reorder/rename case (Example 2), and includes an explicit malformed-outline error instruction ("return a short error message in plain text and do NOT call `merge_outline`").
- **Why:** AGENTS.md flagged step 3 `refine_bullets` regression ("`generate_outline` overwrites instead of appending"). Inventory § Known gaps #1 confirmed the root cause: one tool being used for two opposite semantics. `_theme1_feedback.md` and SUMMARY.md § Theme 1 resolved it as tool-split + skill-owns-persistence.
- **Theme:** Theme 1 (skill/policy contract confusion); step 3 regression is the primary eval signal.
- **Files touched:**
  - `backend/utilities/content_service.py` (`merge_outline` implementation)
  - `backend/modules/pex.py` (tool registration)
  - `schemas/tools.yaml` (tool schema entry)
  - `backend/components/flow_stack/flows.py` — `RefineFlow.tools` swap
  - `backend/modules/policies/draft.py` — `refine_policy` `extra_resolved={'current_outline': content}`
  - `backend/prompts/skills/refine.md` (rewrite)

### Contract-violation backstop — return error frame when outline shrinks unexpectedly

- **What changed:** After `merge_outline` reports success, `refine_policy` re-reads the post's outline metadata and compares `_count_bullets(new_outline)` to `_count_bullets(content)` (prior). If the new outline has strictly fewer bullets AND the user did NOT express removal intent (via `_has_removal_intent`, which scans `flow.slots['steps']` step names/descriptions and `flow.slots['feedback']` values for any of `_REMOVAL_TOKENS = ('remove', 'delete', 'drop', 'cut', 'trim')`), the policy returns a `DisplayFrame(origin='error', metadata={'contract_violation': 'outline_shrunk_after_merge', 'prior_bullets': N, 'new_bullets': M}, code='merge_outline returned a shorter outline than the prior state without an explicit removal directive')`. A sibling error branch covers the case where the skill failed to persist at all (`not text or not saved`): `metadata={'contract_violation': 'refine_did_not_persist'}`.
- **Why:** AD-6 — contract violations surface as error-origin frames with a `code` payload, not through `AmbiguityHandler`. The bullet-count check is intentionally lenient (only a *net* loss triggers) per the user's feedback that strict equality is overkill for minor issues.
- **Theme:** Theme 4 (error-path gaps) under the AD-6 contract-violation channel.
- **Files touched:**
  - `backend/modules/policies/draft.py` — module-level `_REMOVAL_TOKENS`, `_count_bullets`, `_has_removal_intent`; `refine_policy` lines ~175-191 (shrink backstop) and ~168-173 (did-not-persist branch)

### Stack-on to `OutlineFlow` surfaces the reason inline

- **What changed:** The "outline has no bullets" branch now stacks `OutlineFlow` using the inline Theme 6 form: `self.flow_stack.stackon('outline'); state.keep_going = True; frame = DisplayFrame(thoughts='No bullets in the outline yet — generating one first.')`. No helper, no new attributes — just the existing `flow_stack.stackon()` plus a reason attached to `thoughts` so the RES layer can surface the transition.
- **Why:** SUMMARY.md § Theme 6 flagged the silent stack-on. User feedback on Theme 6/7 explicitly rejected a `BasePolicy.stack_on` helper, a `STACK_ON_REASONS` dict, and new DisplayFrame fields; the reason lives in `thoughts` and the pattern is inline.
- **Theme:** Theme 6 (stack-on & recursion risk).
- **Files touched:**
  - `backend/modules/policies/draft.py` — `refine_policy` lines ~196-200

### `saved` check migrated to `PromptEngineer.tool_succeeded`

- **What changed:** `outline_calls = [...]; saved = outline_calls and all(...)` was replaced with `saved, _ = self.engineer.tool_succeeded(tool_log, 'merge_outline')`. Consistent API across the two call sites (outline + refine); the returned result dict is unused here.
- **Why:** SUMMARY.md § Theme 7. Only `tool_succeeded` survived user review; `guard_slot`, `complete_with_card`, `stack_on` helpers were rejected.
- **Theme:** Theme 7 (scoped down).
- **Files touched:**
  - `backend/modules/policies/draft.py` — `refine_policy` line 166

## Architectural decisions applied

- **AD-6** — contract violations (`outline_shrunk_after_merge`, `refine_did_not_persist`) return `DisplayFrame(origin='error', metadata=..., code=...)`, never `ambiguity.declare(...)`.
- **AD-5** — OutlineFlow stack-on uses "stacks on", reason text goes to `thoughts`, no new fields/flags.

> **Part 2 alignment.** This fix aligns with [§ 3 Error recovery](../best_practices.md#3-error-recovery) and [§ 6 Stage machines inside policies](../best_practices.md#6-stage-machines-inside-policies). See [Your ReAct Agent Is Wasting 90% of Its Retries — TDS](https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/) on classifying errors before retry — `outline_shrunk_after_merge` is a semantic contract violation (not a transient), so it surfaces as an error frame rather than a silent retry. Tool-split (`merge_outline` vs. `generate_outline`) echoes [SitePoint — Agentic Design Patterns 2026](https://www.sitepoint.com/the-definitive-guide-to-agentic-design-patterns-in-2026/) on making stage transitions reflect real control-flow divergence.

## Open follow-ups

- The removal-intent detector is a keyword scan over `steps` + `feedback`. A user requesting removal via `changes`-style free text that doesn't contain any `_REMOVAL_TOKENS` word could trip the backstop. Eval coverage should include a "remove X" utterance that uses synonyms like "drop" (already covered) and "scrap" / "delete" (covered via "delete").
- `merge_outline` currently treats omitted sections as implicitly preserved. If the skill intentionally drops a section to delete it, the policy should ideally surface that as a separate `remove_section` intent — deferred.
- The malformed-outline skill path (return plain-text error) is not yet wired to a specific policy handling branch; today it falls through to the `not text or not saved` → `refine_did_not_persist` error frame, which is accurate but could be split for clearer UI messaging.
