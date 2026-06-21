# Fixes — `outline` Flow

**Status:** applied (see themes listed below)

## Back-references to Part 1

- Inventory: `inventory/outline.md`
- Relevant sections: § Usage contexts (propose / direct), § Staging, § Stack-on triggers, § Frame shape, § Known gaps (depth unused, propose-mode enforcement, recursion)
- Primary SUMMARY.md themes: **T2 (unexemplified slots — `depth`)**, **T4 (error-path gaps — propose-mode enforcement)**, **T6 (stack-on & recursion risk)**, **T7 (repeated tool-log pattern)**

## Changes that landed

### `depth` slot wired through the canonical 4-level scheme

- **What changed:** Introduced `OUTLINE_LEVELS` as a module-level constant at the top of `backend/components/flow_stack/flows.py` (Level 0 = title through Level 4 = sub-bullet). `outline_policy` now reads `flow.slots['depth'].level` (defaulting to 2 when unfilled) and injects `extra_resolved={'depth': depth}` into `llm_execute`. `skills/outline.md` gained a `## Outline levels` section with the canonical table plus a depth-semantics ladder (`depth=1` → Level 1 headings only; `depth=2` → headings + bullets; etc.) and a `depth=1` few-shot example.
- **Why:** Inventory § Known gaps #2 (depth unused) and SUMMARY.md § Theme 2 both called this out — NLU was filling a slot neither the policy nor the skill honored. AD-4 locks the 4-level scheme as the repo-wide reference.
- **Theme:** Theme 2 (unexemplified slots).
- **Files touched:**
  - `backend/components/flow_stack/flows.py` (`OUTLINE_LEVELS` constant)
  - `backend/modules/policies/draft.py` — `outline_policy` (depth extraction + `extra_resolved` kwarg)
  - `backend/prompts/skills/outline.md` (new `## Outline levels` section, updated `## Slots`, new Example 2)

### Propose-mode defensive tool stripping via `exclude_tools`

- **What changed:** `BasePolicy.llm_execute` gained an `exclude_tools:tuple=()` kwarg that filters the skill's tool registry by name before the `engineer.tool_call` invocation. `_propose_outline` now passes `exclude_tools=('generate_outline', 'merge_outline')` and adds `propose_mode: True` into the resolved-context hint. The runtime fallback (detecting `generate_outline` in the tool log and reframing to direct-mode) is retained as a safety net and now emits `log.warning` if it ever trips.
- **Why:** SUMMARY.md § Theme 4 and inventory § Known gaps #1 flagged propose-mode as "LLM-trust-only." Tool stripping makes the constraint deterministic; the `propose_mode` context hint gives the skill a human-readable reason; the runtime fallback covers the impossible-but-safe case.
- **Theme:** Theme 4 (error-path gaps) — two-layer defense + logged safety net.
- **Files touched:**
  - `backend/modules/policies/base.py` — new `exclude_tools` kwarg on `llm_execute` (line 19, applied at line 36-37)
  - `backend/modules/policies/draft.py` — `_propose_outline` call (line 128)
  - `backend/prompts/skills/outline.md` — Rule 6 in "Rules for propose mode" now references `propose_mode: True`

### Recursion documented as safe (no code change)

- **What changed:** An inline comment above the recursive `outline_policy(...)` call explicitly states the invariant: after `proposals → sections` is drained, the recursive call takes the sections-filled branch (which does not self-recurse), so max recursion depth = 1. `OutlineFlow` may not `stackon('outline')` itself.
- **Why:** AD-3 — existing recursion is safe; the fix is documentation, not control flow. Theme 6 explicitly rejected the band-aid rewrites.
- **Theme:** Theme 6 (stack-on & recursion risk).
- **Files touched:**
  - `backend/modules/policies/draft.py` — `outline_policy` lines ~94-97 (comment only)

### `saved` check migrated to `PromptEngineer.tool_succeeded`

- **What changed:** The prior `outline_calls = [tc for tc in tool_log if tc.get('tool') == 'generate_outline']; saved = outline_calls and all(...)` pattern was replaced with `saved, _ = self.engineer.tool_succeeded(tool_log, 'generate_outline')`. The helper returns `(bool, dict)` with a consistent API; the second item (result dict) is discarded here.
- **Why:** SUMMARY.md § Theme 7 — repeated tool-log pattern. Only this one helper from the Theme 7 proposal landed; `guard_slot`, `complete_with_card`, and `stack_on` were rejected by the user.
- **Theme:** Theme 7 (repeated guard-clause & tool-log patterns — scoped down).
- **Files touched:**
  - `backend/modules/policies/draft.py` — `outline_policy` line 80

## Architectural decisions applied

- **AD-3** — outline recursion is safe by construction; documentation-only change.
- **AD-4** — 4-level outline system; `OUTLINE_LEVELS` is the central reference.
- **AD-6** — propose-mode violation would be a **contract violation**, not ambiguity. The tool-stripping + `propose_mode` hint prevent the skill from violating the contract in the first place; the fallback logs a warning rather than declaring ambiguity.
- **AD-5** — consistent terminology: `flow.stage = 'propose' | 'direct' | 'error'` are **stages**, not modes.

> **Part 2 alignment.** This fix aligns with [§ 1 Skill-prompt structure](../best_practices.md#1-skill-prompt-structure) and [§ 2 Tool-call loop shape](../best_practices.md#2-tool-call-loop-shape). See [Anthropic skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) on consistent terminology and concrete input/output examples (`OUTLINE_LEVELS` + `depth=1` exemplar) and [Anthropic — Building agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk) on using allowed-tool filtering (`exclude_tools`) to make stage constraints deterministic.

## Open follow-ups

- `refine`, `compose`, and `add` do not currently read `depth` from a stored outline. Whether they should infer level from prior outline state is deferred (see `_theme2_feedback.md § Feedback prompts` under outline).
- The `apply_guardrails(raw, format='markdown', shape='candidates')` parser in `_propose_outline` has no documented failure path if the LLM emits two options instead of three. Currently `candidates` may be empty, in which case no `selection` block is added — Part 4 should cover this edge case.
