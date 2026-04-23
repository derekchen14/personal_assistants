# Shared Functionality — Fixes

**Status:** applied (see themes listed below)

Cross-flow helpers, conventions, and constants touched during the Theme 1-7 execution. Every shared-helper candidate below back-links to the inventory files and theme feedbacks where the repeated pattern was observed.

## Back-references to Part 1

- Inventory summary: `inventory/SUMMARY.md § Theme 7` (repeated guard-clause and tool-log patterns)
- Shared patterns observed in: `inventory/outline.md`, `inventory/refine.md`, `inventory/compose.md`, `inventory/simplify.md`, `inventory/polish.md`, `inventory/rework.md`, `inventory/add.md`, `inventory/audit.md`, `inventory/inspect.md`, `inventory/find.md`, `inventory/release.md`, `inventory/create.md`
- Theme feedbacks: `inventory/_theme5_feedback.md` (scratchpad convention), `inventory/_theme6_feedback.md` (stack-on), `inventory/_theme7_feedback.md` (extracted helpers)

## Extracted helpers that landed

### `PromptEngineer.tool_succeeded(tool_log, tool_name) -> (bool, dict)`

- **Location:** `backend/components/prompt_engineer.py` line ~474.
- **Contract (per `_theme7_feedback.md § Overall Feedback #2`):** returns `(True, cleaned_result)` when at least one call to `tool_name` exists in the log AND all calls succeeded; returns `(False, {})` on miss or any failure. Consistent shape means callers can always unpack, never worry about `None`.
- **Call-sites:** `outline_policy`, `refine_policy`, `polish_policy`, `simplify_policy`, `rework_policy` (via `_mark_suggestions_done`) — 4 migrations across `draft.py` and `revise.py`.
- **Rationale:** Pure extraction of the `[tc for tc in tool_log if tc['tool']==X]` + `_success` check that appeared near-verbatim in 6+ call-sites. Zero semantic change.

### `BasePolicy.llm_execute(..., include_preview=False, extra_resolved=None, exclude_tools=())`

- **Location:** `backend/modules/policies/base.py` line ~18.
- **Change:** three new kwargs **extend** the existing method; no new top-level helper, no new concept. Each kwarg was introduced to serve a specific flow need rather than generically:
  - `include_preview=True` — `compose_policy` preloads per-section previews (title + first 3 lines) so the skill can plan without an extra `read_metadata` round-trip.
  - `extra_resolved=<dict>` — merges ad-hoc, already-fetched data into the resolved-entities block. Used by `refine` (current_outline), `outline` (depth + propose_mode hint), `rework` (target_section + rework_scope), and `polish` (prior findings summary if needed).
  - `exclude_tools=(...)` — hard-strips tools by name from the skill's tool-def list before calling `engineer.tool_call`. Used by `_propose_outline` to exclude `generate_outline` + `merge_outline` in propose mode (AD-6 prompt-tightening + defence-in-depth).
- **Rationale:** Per "don't create new concepts" rule, extend the one existing entry point the policies already share instead of building parallel helpers.

### `ContextCoordinator.turn_id` property

- **Location:** `backend/components/context_coordinator.py` line ~123.
- **Change:** alias for `num_utterances`. Every scratchpad write uses `context.turn_id` for the `turn_number` field per AD-1, giving the scratchpad a single canonical clock source.
- **Rationale:** `state.turn_number` was speculative in the Theme 5 draft; `ContextCoordinator` already carries the count, so we expose it with a clean name and avoid a parallel counter.

### `MemoryManager.write_scratchpad` type widened to `str | dict`

- **Location:** `backend/components/memory_manager.py` line ~22.
- **Change:** the value parameter is now typed `str | dict` to accept the AD-1 convention payload (`{'version', 'turn_number', 'used_count', ...}`). Previously the hint was `str`, which was misleading — the storage is already a flat dict.
- **Rationale:** AD-1 codified the convention; the type hint now matches the convention.

### `OUTLINE_LEVELS` dict in `backend/components/flow_stack/flows.py`

- **Location:** module-level constant, line ~9.
- **Change:** canonical 4-level outline scheme per AD-4 (`{0: '# Title', 1: '## Heading', 2: '### Sub-heading', 3: ' - bullet', 4: '   * sub-bullet'}`). Used as the single source of truth for the `depth` slot on `OutlineFlow`, and referenced by `refine`, `compose`, `add`, and any future producer that writes outline markdown.
- **Rationale:** Previously every flow referenced its own informal N-level scheme; AD-4 consolidates.

### Content tool split: `generate_outline` (overwrite) vs `merge_outline` (append / reorder / preserve)

- **Location:** `backend/utilities/content_service.py` (both), wired into `backend/modules/pex.py :: _tools` lines 67-68, and registered in `schemas/tools.yaml`.
- **Change:** the old single `generate_outline` tool was ambiguous — `refine` needed append behaviour but `outline` (direct mode) needed full overwrite. Splitting into two tools makes the caller's intent explicit at the tool site; Theme 4's refine regression (shrinking outline after "add these bullets") is fixed as a side-effect.
- **Rationale:** Theme 1 (skill/policy contract confusion) eliminated one axis of ambiguity.

### Module-level helpers in `draft.py` for refine's bullet-count backstop

- **Location:** `backend/modules/policies/draft.py` top of file.
- **Change:** `_REMOVAL_TOKENS = ('remove', 'delete', 'drop', 'cut', 'trim')`, `_count_bullets(outline:str)`, `_has_removal_intent(flow)`. Called by `refine_policy` to detect whether a shorter-outline result was user-requested or a silent regression (AD-6 contract-violation surface).
- **Rationale:** Shared by the refine-specific Theme 4 backstop; not broad enough to live in `BasePolicy`.

### `RevisePolicy._mark_suggestions_done`

- **Location:** `backend/modules/policies/revise.py` line ~65.
- **Change:** the rework skill may return either `{'done': [name, ...]}` or `{'suggestions': {name: 'done'}}`; this method normalises both and calls `sug_slot.mark_as_complete(name)` on each. Only runs if `revise_content` reported success (via `tool_succeeded`) and the parse yields a dict.
- **Rationale:** Theme 1 rework — the skill now owns persistence, and this callback closes the loop by ticking ChecklistSlot steps without inventing a new "done" attribute.

## Proposed but rejected

Tracking the proposals explicitly so we don't regrow them next time.

- **`BasePolicy.stack_on(flow_name, state, reason=None)`** — rejected in `_theme7_feedback.md § Overall Feedback #4`. `flow_stack.stackon()` already exists; callers inline the 3-line pattern (`flow_stack.stackon(X); state.keep_going = True; frame.thoughts = <reason>; return frame`) to keep one source of truth.
- **`STACK_ON_REASONS` dict in templates** — rejected in `_theme6_feedback.md § refine (d)`. Reason strings are inlined at the call-site; if duplication becomes a problem, revisit.
- **`BasePolicy.guard_slot(flow, slot_name, level='specific')`** — rejected in `_theme7_feedback.md § Overall Feedback #1`. Slot treatment varies too much across the 12 flows (entity vs elective vs required vs optional), and some flows optimistically fill without guarding. The *pattern* is useful but the *shape* can't be standardised.
- **`BasePolicy.complete_with_card(flow, post_id, tools)`** — rejected in `_theme7_feedback.md § Overall Feedback #3`. Only saves 3 lines, and future `DisplayFrame` / `BuildingBlock` variation will diverge (more blocks, more origins, more conditions).
- **`DialogueState.findings` attribute** — rejected per AD-1. Scratchpad with the key convention is the channel; no new attributes on `DialogueState`.
- **`DisplayFrame.findings` attribute** — rejected per AD-1. Findings live in scratchpad; frame metadata carries ephemeral per-turn payload only.

## Additional helpers proposed (Part 2 feedback, pending user sign-off)

These are concrete helpers / kwargs that land once AD-7 through AD-10 are signed off. Each is small, additive, and traceable to a `policy_spec.md § AD-N` decision.

### AD-7 — `PromptEngineer.load_skill_meta(flow_name)` — read frontmatter

- **Location (proposed):** `backend/components/prompt_engineer.py`, alongside the existing `load_skill_template`.
- **Change:** parse the YAML frontmatter from `backend/prompts/skills/<name>.md`, return the dict. `load_skill_template` strips frontmatter from the body so existing callers keep working.
- **Rationale:** Anthropic's 2026 skill-authoring convention (see `components_as_skills_proposal.md § 5`). `description` becomes a routing key for future skill registries; `tools` field is an allowlist asserted against `flow.tools`.

### AD-8 — `BasePolicy.commit_optional_default(flow, slot_name, default)` — EVPI helper

- **Location (proposed):** `backend/modules/policies/base.py`.
- **Change:** three-line helper; if slot is unfilled, fill it with the default. Codifies the pattern already in `audit_policy` (reference_count default 5). Optional helper — if only 1-2 flows need it, keep it inline.

### AD-9 — `_validate_frame` block-type value checks

- **Location:** `backend/modules/pex.py::_validate_frame`.
- **Change:** small `_BLOCK_VALIDATORS` dict keyed by block type. Validators return `(ok: bool, reason: str)`. `origin='error'` short-circuits passed=True (AD-6 alignment; matches the `error_recovery_proposal.md § 5.3` fix).

### AD-9 — `_llm_quality_check` per-flow opt-in

- **Location:** `backend/components/flow_stack/parents.py::BaseFlow.__init__`, add `self.llm_quality_check = False`. Override `True` in prose-heavy flows (`polish`, `rework`, `brainstorm`).
- **`_validate_frame`:** replace current `_should_llm_validate(flow)` with `flow.llm_quality_check`.
- **Rationale:** eliminates default-on LLM-as-judge; ~50% reduction in per-turn LLM cost across the deterministic or tool-heavy flows.

### AD-10 — Prompt caching markers

- **Location:** `backend/components/prompt_engineer.py::_call_claude`, on the `messages` / `system` / `tools` blocks.
- **Change:** append `{'cache_control': {'type': 'ephemeral'}}` to the system-prompt and tool-def segments. Cache hit automatic on subsequent calls with the same segments. 1-hour TTL.
- **Rationale:** pure cost + latency win; no behavior change.

### AD-10 — `BaseFlow.max_response_tokens`

- **Location:** `backend/components/flow_stack/parents.py::BaseFlow.__init__`, add `self.max_response_tokens = 4096`. Override in short-output flows.
- **`llm_execute`:** reads `flow.max_response_tokens` and forwards to `tool_call`.
- **Rationale:** most flows never need the full 4096; tightens token spend per-flow.

## Best-practice justifications

> **Part 2 alignment.** Shared helpers land under [§ 8 Determinism boundaries](../best_practices.md#8-determinism-boundaries) and [§ 9 Cross-turn state / findings channel](../best_practices.md#9-cross-turn-state--findings-channel). See [Anthropic — Building agents with the Claude Agent SDK](https://claude.com/blog/building-agents-with-the-claude-agent-sdk) on the "gather → act → verify → repeat" loop (`tool_succeeded` is the verify step for tool-log outputs, consistent shape across call-sites) and [State of AI Agent Memory 2026 — mem0.ai](https://mem0.ai/blog/state-of-ai-agent-memory-2026) on structured-scratchpad conventions with a canonical clock source (`context.turn_id`) that make producer/consumer handoff auditable.

## Migration order that was executed

1. Theme 7's `tool_succeeded` landed first (pure refactor, zero behaviour change, 4 call-sites).
2. Theme 1 deletes (create, find, inspect skills) + Theme 1 content-tool split landed next — big surface shrink.
3. Theme 2 exemplar rewrites to match the new contracts.
4. Theme 3 structured-output fixes (audit card, inspect metadata) + scratchpad writes.
5. Theme 4 AD-6 error-channel work (release, refine, outline propose-mode).
6. Theme 5 scratchpad producers/consumers wired end-to-end.
7. Theme 6 stack-on inline reason strings.

No per-flow drift between themes because the shared helpers + conventions were locked before per-flow rewrites.
