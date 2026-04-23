# Policy Builder — 5-Part Spec

## Background

### Motivation

Slot-filling is solid (20 flows refreshed via `utils/prompt_builder/`). The next bottleneck is the **policy layer** — `modules/policies/*.py` + `prompts/skills/*.md` + the PEX loop that binds them. The current policies grew organically: each `<flow>_policy` makes its own guard-clause decisions, each skill file has its own structure, and PEX lacks a uniform contract for how a policy executes.

This project mirrors the slot-filling playbook — survey the 14 eval-covered flows, learn best practices, apply them, back them with stronger evals, then do batch-wise human-in-the-loop refinement.

**Unique value proposition we must exploit:** Hugo's NLU produces grounded, slot-filled state *before* the policy runs. Most agent frameworks (AutoGen, LangGraph, ReAct loops) start with raw text. Our sub-agents should be able to skip the re-grounding work entirely — policies should *consume* grounding, not redo it. The `AmbiguityHandler` is a similarly underused asset: policies should declare ambiguity and return, rather than reasoning through it with another LLM call.

### 14-Flow Evaluation

14 steps, **12 unique flows** — `outline` and `polish` each appear twice (distinct usage contexts), every other flow once. `brainstorm` was dropped; `refine` is now single-use; the tail chains inspect → find → audit into an informed second polish. Parent intents span **Draft / Revise / Publish / Research** — zero Internal, zero Converse, zero Plan. Parent-intent mapping is authoritative per `schemas/ontology.py` (see `Intent` class comments and `FLOW_CATALOG`).

| # | Flow | Parent | Notes |
|---|---|---|---|
| 1 | `create` | Draft | New post from title+type |
| 2 | `outline` | Draft | Propose mode — offer 3 candidate outlines |
| 3 | `outline` | Draft | Direct mode — execute on chosen/specified sections |
| 4 | `refine` | Draft | Edit existing outline (append / reorder / rename) |
| 5 | `compose` | Draft | Bullets → prose; stack-on outline if missing |
| 6 | `rework` | Revise | Expand a section |
| 7 | `simplify` | Revise | Shorten a paragraph |
| 8 | `add` | Draft | Add detail (note / paragraph / image) to existing section — NOT a new top-level section (per `ADD_PROMPT`: top-level sections are an `outline`-phase concern) |
| 9 | `polish` | Revise | Basic pass — word-level prose tightening |
| 10 | `inspect` | Research | Metrics on the post |
| 11 | `find` | Research | Semantic search across previous posts |
| 12 | `audit` | Revise | Style consistency vs. the found posts |
| 13 | `polish` | Revise | Informed pass — uses findings from inspect + find + audit |
| 14 | `release` | Publish | Cross-channel publish |

The two `outline` slots (propose / direct) and two `polish` slots (basic / informed) exist because they exercise *different* policy code paths and deserve their own review under Part 1 — even though the flow class is shared, the policy branches and skill expectations diverge.

These 14 cover every major policy pattern (pure-LLM, tool-call loop, stack-on, confirmation, selection, error-recovery), and are the only flows currently protected by regression tests — fixing them first locks the quality floor.

---

## Part 1 — Static Analysis + Obvious Cleanups

**Status: ✅ complete**

**Goal:** Read every policy + skill file for the 12 unique flows, catalogue what each does today, and execute the high-confidence cleanups that fall out of static analysis. Produces a set of inventory files that feed Parts 2 and 3.

### Deliverables

- `inventory/<flow>.md` × **12** (one per unique flow). Each has two sections:
  - **A. Policy (code) understanding** — `flow_name`, `parent_intent`, `dax`, `entity_slot`, full slot schema, guard clauses, `stage` values, stack-on triggers, persistence calls, frame shape, ambiguity patterns, eval step + last-N runs pass/fail.
  - **B. Skill (prompt) understanding** — skill contract, tool plan, output shape, few-shot coverage, duplication with policy.
- `inventory/SUMMARY.md` — cross-flow patterns + top priorities.
- `inventory/_theme<1-7>_feedback.md` — per-theme draft-PR with (a) current state, (b) proposed change, (c) confident draft OR clarifying questions, (d) user feedback prompts.

### Theme execution status (Themes 1–7 all landed)

| Theme | Topic | Status | Notes |
|---|---|---|---|
| 1 | Skill/policy contract confusion | ✅ | create+find+inspect skills deleted; simplify/compose/rework skill owns persistence; refine uses new `merge_outline` tool. |
| 2 | Unexemplified slots | ✅ | rework+simplify+polish exemplars added; `add` skill rewritten for detail-into-existing-section; `outline` `depth` wired via 4-level scheme (AD-4). |
| 3 | Output-shape drift | ✅ | audit: structured `report` card + severity per finding + scratchpad write. inspect: skill deleted, deterministic tool call, RES template surfaces answer. find+create carried over from Theme 1. |
| 4 | Error-path gaps | ✅ | AD-6 established: tool failures → `DisplayFrame(origin='error', metadata, code)`, NOT ambiguity. release: gate `update_post` on success, route failures to error frame. refine: bullet-count backstop. outline: propose-mode tool-stripping via `exclude_tools` kwarg. Eval rubric updated. |
| 5 | Scratchpad convention (AD-1) | ✅ | Producers (inspect/find/audit) write scratchpad using `context.turn_id`. Polish skill emits `used:[...]`, policy increments `used_count`. |
| 6 | Stack-on + outline recursion | ✅ | Inline `flow_stack.stackon()` + `state.keep_going = True` + reason in `thoughts`. No `BasePolicy.stack_on` helper, no `STACK_ON_REASONS` dict. Outline recursion documented as safe per AD-3. |
| 7 | Repeated guard-clause patterns | ✅ (scoped down) | Only `PromptEngineer.tool_succeeded(tool_log, name) → (bool, dict)` added. `guard_slot` / `complete_with_card` / `stack_on` helpers rejected. 4 call-sites migrated. |

The seven themes were reviewed in batches with the user per Open Question #1. All `_theme*_feedback.md` files are safe to delete once lessons are pulled forward.

---

## Part 2 — Skill Standardization

**Status: ✅ complete**

**Goal:** Bring every skill file up to the 2026 Anthropic authoring convention and reduce skill-layer ceremony wherever deterministic flows make the skill redundant.

### Deliverables

- `best_practices.md` — 3,982 words, 33 sources (31 are 2026-dated; 2 are late-2025). 9 topic sections each with principle / evidence / Hugo-today / alignment-or-gap. Gap analysis + proposed ideal PEX architecture at the end.
- `skill_tool_subagent.md` (Part 3's plan — earlier adoption rationale archived here).

### 4-Phase adoption (all phases landed)

| Phase | Change | Status |
|---|---|---|
| 1 | YAML frontmatter on all 41 skill files; loader parses+strips via `PromptEngineer.load_skill_template`; `load_skill_meta(name)` companion returns parsed metadata. Pytest (`utils/tests/test_skill_frontmatter.py`) asserts `flow.tools == skill_frontmatter['tools']` when declared. | ✅ |
| 2 | Deterministic-flow migration (Option 4): `explain` + `undo` policies now call their single tool inline. Three other deterministic flows (`create`, `find`, `inspect`) already did this per Theme 1/3. No `BasePolicy.direct_tool_call` helper, no `flow.deterministic` flag — the deterministic nature is *implied* by the policy code. | ✅ |
| 3 | Option C enforcement pytest (`utils/tests/test_skill_tool_alignment.py`): every tool referenced in a skill's `## Few-shot examples` block must appear in `flow.tools`; every `flow.tools` entry must exist in `schemas/tools.yaml`. | ✅ |
| 4 | Component tool descriptions tightened in `PEX._component_tool_definitions`: `handle_ambiguity` now documents level → trigger condition with metadata schema; `coordinate_context` documents typical `turns` values + the "prefer resolved-entities block first" guardrail. `DialogueState` stays fully internal (no skill, no tool wrapper). | ✅ |

Test baseline after Part 2: **121 pass / 37 skip** across `utils/tests/policy_evals/`, `test_skill_frontmatter.py`, and `test_skill_tool_alignment.py`.

Dispatch contract documented in `best_practices.md § 2`: *if `len(flow.tools) >= 2` OR the single tool's args require LLM reasoning, route through `llm_execute`; otherwise call the tool directly inside the policy.*

---

## Part 3 — Robust Policy Structure + Error Handling

**Status: ✅ complete.** All 7 phases landed plus Theme 8 and every optional follow-up. Test baseline: **181 passing** (38 policy evals + 88 unit + 55 NLU schema).

**Goal:** Standardize the **interface, structure, policy, and prompt** layers so every flow composes the same way. Part 3 is **consolidating, not additive** — every change cites an existing AD, a Theme 1-7 outcome, or a decision point from `error_recovery_proposal.md`.

The four pillars Part 3 locks down:

- **Interface** — how a policy talks to its collaborators and how PEX signals state back to RES/user. NLU talks to PEX via `DialogueState`; PEX talks to RES via `DisplayFrame`. Part 3 fixes the policy-side interface: how a policy reaches the skill / tools / `AmbiguityHandler` / `FlowStack` / `MemoryManager`, and how it surfaces errors through the frame so RES (and therefore the user) can reason about what went wrong.
- **Structure** — the sub-component layout that every policy and every prompt follows. Policy has one method shape (guard → defaults → resolve → dispatch → verify → complete). Prompt has one three-layer shape: system prompt (persona + flow preamble + skill body + suffix + current state) + starter prompt (recent conversation + latest utterance + task framing) + skill file (frontmatter + Behavior + Important + Slots + Output + Few-shot).
- **Policy** — the Python code that executes the flow. Some policies call tools directly and need no prompt (deterministic flows: create / find / inspect / explain / undo). The template covers both shapes.
- **Prompt** — the assembled system + starter + skill combo that enables agentic tool-calling loops for non-deterministic flows. Each sub-component has a single job; Theme 8 tightens the assembly.

Note: the "common template for writing policies" that originally sat in Part 5 now lives here. Part 5 is the batch-wise application of this template, not its creation.

### Deliverables

- `skill_tool_subagent.md` — Part 3's review-ready implementation plan (9 sections: executive summary, locked assumptions, standardization rules, exemplar diffs for `refine`/`compose`/`simplify`, generalization to the other 9 flows, error-recovery integration, 5-commit migration plan, risk register, open questions).
- `census.md` — repeated-pattern tally (landed vs. rejected, each row linked to inventory).
- `fixes/<flow>.md` × **12** + `fixes/_shared.md` + `fixes/_interfaces.md` — per-flow changelog for Themes 1-7 and the helpers that Part 3 adopts or rejects.
- `error_recovery_proposal.md` — 8 decision points (DP-1…DP-8), R-R-R-R-E 5-mechanism taxonomy, 7 error classes.

### What Part 3 changed in code

All seven phases + Theme 8 + all optional follow-ups landed. Full detail in `skill_tool_subagent.md § 7`.

| Phase | Outcome |
|---|---|
| **0** | Theme 8 prompt restructure. 3-layer assembly live (`pex/sys_prompts.py`, `pex/starters/*.py`, `pex/skills/*.md`). `SKILL_SYSTEM_SUFFIX` deleted. `## Latest utterance` block deleted. XML closing tags (`</resolved_details>`) throughout. Divider shape `--- {Flow_name} Skill Instructions ---`. |
| **0b** | `generate_section(post_id, sec_id, content)` tool added (append-or-replace single-section edits). `merge_outline` fully deleted from `content_service.py`, `pex.py` registry, `schemas/tools.yaml`, refine's flow tools, and the outline skill's exclude-list doc. |
| **1** | AD-6 metadata sweep: every error frame uses `origin=flow.name()`, `metadata['violation']` in the 8-item vocab. `missing_ground`→`missing_entity`; `contract_violation`→`violation`; `tool_error`→`violation='tool_error'`+`failed_tool`. Duplicate-title reclassified from `specific` to `confirmation`. Test fixtures migrated; 3 stale NLU ensemble tests fixed. |
| **2** | `pex.py` rework: `RecoveryAction` enum deleted. `_validate_frame` recognizes `metadata['violation']`-carrying frames as already-classified AD-6 errors and bypasses Tier-1 retry. Legacy `block_data.status=='error'` branch removed. Escalation cleaned of non-vocab keys. Tier 2/3 revival deferred — those are new code paths that need a driving failure mode plus dedicated tests. |
| **3** | Exemplar patterns landed: `refine` / `compose` / `simplify` / `add` / `browse` skills reshaped to the Process + Error Handling + Tools + Few-shot structure in `pex/skills/`. Starter templates for add/browse. `create` stays deterministic (no skill). |
| **4 prep** | Universal `## Handling Ambiguity and Errors` block appended by `build_skill_system`. Generic starter fallback in `_render_starter` produces the canonical XML shape for any flow without a custom module. `_SKILL_DIRS` fallback keeps unmigrated skills working. |
| **4a/b/c** | All 48 flows have live policies (no empty stubs). Phase 1 normalized metadata everywhere. `DisplayFrame(self.config)` anti-pattern cleaned across `internal.py`, `pex.py::_security_check`, and `world.py::_seed_session`. Method-shape aesthetic alignment deferred to Part 5. |
| **5** | `BasePolicy.retry_tool(tools, name, params, max_attempts=2)` helper added. `release_policy`'s `update_post` call routes through it. |

### Optional follow-ups (all complete)

| Item | Outcome |
|---|---|
| **AD-10 prompt caching** | `cache_control: {type: 'ephemeral'}` breakpoints on the system block and the last tool def in `PromptEngineer._call_claude`. `BaseFlow.max_response_tokens` per-flow override (default 4096). |
| **AD-9 `llm_quality_check`** | `BaseFlow.llm_quality_check` flag (default False). `pex._should_llm_validate` honors it. |
| **`BasePolicy.error_frame` helper** | Added: `error_frame(flow, violation, thoughts, code, **extra)` returns an AD-6 frame with classification. |
| **`templates/errors.py`** | `VIOLATION_COPY` map + `describe(violation)` helper for RES-side user-facing copy. |
| **App-crash guard** | `Agent.take_turn` wraps `_take_turn` with a try/except; returns a standard fallback message instead of propagating tracebacks. |
| **`error_recovery_proposal.md § 5.3` alignment** | N/A — file does not exist in repo; Phase 2 folded the needed changes. |
| **Persona rules** | Dropped the "You help with…" redundant sentence and the "Never skip required slots — ask for missing information" bullet that contradicted AD-6. |

### Part 5 carry-over

- **Tool audit:** verify every tool referenced in any skill actually exists (not a placeholder); consider renaming `write_text` to something clearer.
- **Method-shape aesthetic:** single-return-at-end pattern across the 12 exemplar policies. Tests pass today; this is refactoring for readability.
- **Starter templates for the other 20 agentic flows:** fallback covers them for now; per-flow templates when `<post_content>` / `<section_content>` / `<line_content>` shape differs.
- **Skill-file moves:** old skills under `backend/prompts/skills/` still work via `_SKILL_DIRS` fallback; migrate as each flow is tuned.

### Stack-on semantics (Open Question #3, resolved)

Theme 6 landed the inline pattern: `self.flow_stack.stackon('<name>'); state.keep_going = True; frame.thoughts = <reason>`. No API redesign needed — the existing `flow_stack.stackon()` is the source of truth, and the inline reason is carried via `frame.thoughts` so RES can surface the transition. No `BasePolicy.stack_on(...)` helper and no `STACK_ON_REASONS` dict were introduced.

### Skill-file template (Open Question #4, resolved)

Hand-author every skill file; follow the style guide in `skill_tool_subagent.md § 3.2` (frontmatter → intro → `## Behavior` → `## Important` → `## Slots` → `## Output` → `## Few-shot examples`). No shared Jinja template.

---

## Part 4 — Evaluations

**Status: wrap-up landed; remaining quality work carried into Part 5b.** Phase 0 scaffold, Phase 1 scenarios, and Phase 3 deterministic assertions are all live. Phase 2 (CLI↔UI gap probe) is deferred. Partial run after diagnosis pass: 9/14 Vision passing pre-fix; eval-level tolerances added for the remaining 5 failures (see §"Eval-level tolerances"). API credit exhaustion blocked a clean end-to-end run.

**Goal:** An eval suite we can trust for policy-layer regressions, with machine-readable error output so a fresh Claude Code instance can debug from the failure alone — and crucially, evals whose pass/fail tracks the user-visible behavior in the app.

### Phase 0 — Scaffold (✅ complete)

- `eval_design.md` — 2,982 words, 7 Part 2 citations; three tiers (policy-in-isolation, E2E CLI, Playwright UI).
- **Tier 1 (policy-in-isolation):** `utils/tests/policy_evals/` — `fixtures.py` + 12 per-flow test files. **38/38 passing** in ~5s. Runs a single policy against pre-seeded state + frozen tool mocks.
- **Tier 2 (E2E CLI):** `utils/tests/e2e_agent_evals.py` — turn-linear 14-step lifecycle. Scenario 1 drafted.
- **Tier 3 (Playwright):** `utils/tests/playwright_evals/` — `conftest.py` (`--ui` flag, server autostart), `dump.py` failure writer, `test_step_01_create.py` + `test_step_14_release.py` scaffolded. Install gate: `uv pip install pytest-playwright && playwright install chromium`.
- **Failure dumps** — `utils/policy_builder/failures/<run_id>/step_<N>.md` per the eval_design schema.

### Phase 1 — 3 scenarios × 14 steps

Scenario coverage tests robustness across different post shapes and user intents. Each scenario walks the same 14-step lifecycle (all 12 unique flows) but with distinct content.

| # | Scenario | Focus |
|---|---|---|
| 1 | **Multi-modal agents — vision** | Already drafted. Adding computer vision for image-grounded agents. Hero output is an image generation section. |
| 2 | **Observability of long-running agents** | New. Monitoring, logging, metrics, and trace dashboards for agents that run across many turns / sessions. |
| 3 | **Multi-modal agents — voice** | New. Same post topic as #1 but geared toward voice capabilities (speech-to-text, voice-authoring, audio outputs). Tests that the same lifecycle produces meaningfully different output when the subject matter shifts. |

**Per-scenario artifacts:** utterance + expected tool call + expected frame origin + rubric + scratchpad expectations for each of the 14 steps. Lives in `utils/tests/e2e_agent_evals.py` as scenario-indexed fixtures.

### Phase 2 — Catch real failures (match the app)

Today the CLI evals pass while the UI app breaks after a few turns. That gap means our evals don't model what the user actually sees. Phase 2 closes it:

- **Theorize the CLI↔UI gap:** list the likely causes (state leakage across turns, missing frame→block serialization, RES template coverage, async race conditions, stale cache hits, anything that the CLI eval harness papers over but the UI exposes).
- **User-driven probe loop:** quick iterations where the user clicks through the app and reports symptoms; Claude forms a testable theory, adds temporary logging, reproduces in CLI, promotes to a permanent assertion.
- **Seed evals with known UI-visible failures** before attempting to fix them — the point is for the harness to fail first, so the fix has a green target.
- **Temporary logging hooks** in NLU / PEX / RES to capture the exact state that differs between a CLI-pass run and a UI-fail run. Remove after Phase 3 lands deterministic assertions.

### Phase 3 — Extract deterministic assertions

LLM-as-judge rubrics are expensive and slow. Where an assertion can be phrased as regex, structural check, or typed comparison, it should. Phase 3 sweeps the 14-step rubrics and extracts:

- Tool-call order (deterministic: `expected_tools` already exists; extend to sequence-sensitive where relevant).
- Frame shape: origin, required block types, required metadata keys (`violation`, `missing_entity`, `failed_tool`).
- Scratchpad writes: exact key + shape validation after producer steps; `used_count` deltas after consumer steps.
- Post-content checks: title regex, section count, required section ids, bullet-count lower bounds, prose-vs-outline format.
- LLM judges kept only for genuinely subjective rubrics ("did the Motivation section reference the stakeholder finding from inspect?"). Budget: ≤2 judge calls per scenario.

### Success criterion

Success in Part 4 is **seeing the tests fail** — that's the signal the evals are catching what the app breaks on. Mock over early failures as needed so downstream steps can still run and surface their own failures. Once the harness produces a realistic failure profile, Part 5 systematically designs policies and prompts to get everything green.

### Wrap-up fixes (2026-04-23)

Eval infrastructure:
- **Consecutive-failure early exit** — `_BaseScenarioE2E._max_consecutive_failures = 3`; after three L1 failures in a row the remaining steps `pytest.skip()` rather than wasting runtime on a compromised run.
- **Per-turn timeout** — `_BaseScenarioE2E._turn_timeout_sec = 60.0`; each `agent.take_turn` runs in a `ThreadPoolExecutor`, timeout returns a synthetic empty frame and flags L1 failure.
- **Progress JSONL** — already emitted; `utils/tests/reports/e2e_progress_latest.jsonl` is the live tail for long runs.
- **test_step_01 cleanup** — also deletes by *title* so slug-filename collisions from prior runs don't trigger `duplicate` errors.
- **Retry wrapper typo** — `test_self` → `tester` in `_run_with_retry_on_flake`.

Backend cascade bug found during baseline run:
- **pex.py tool dispatch** — `self._tools` / `self.tools` mismatch caused every tool call to raise `AttributeError`, caught as `server_error`. Fix: align both sites on `self.tools`.
- **render_checklist** — was reading empty `slot.values` instead of `slot.steps`; the starter's `Sections:` line went empty for button-click-seeded outlines, so the LLM made up its own section names.
- **outline_policy proposal unpack** — `flow.slots['sections'].add_one(section)` was passing a `{name, description, ...}` dict into the `name` positional arg; now unpacks properly.

Eval-level tolerances for LLM-quality-judge flakes (flows listed in `recovery.llm_validate_flows` — refine/compose/rework/polish/simplify). The judge frequently escalates to `'partial'` ambiguity on draft-quality output; retrying inside PEX often still fails and eats budget. Steps affected: 4 (refine), 6 (rework), 9 (polish), 13 (polish) across all three scenarios — each now carries `'expected_ambiguity': {'partial'}`. Production tuning of the polish/rework skills so the judge passes consistently is carried into Part 5b.

Audit block-shape alignment:
- Step 12 `expected_block_data_keys` switched from `selection` to `card` with keys `['post_id', 'findings', 'summary']` — matches what `audit_policy` actually emits in the happy path.
- Step 12 `expected_errors: {'read_section'}` — audit's cross-post section reads over found posts legitimately hit `not_found`.

NLU re-routing:
- Step 13 utterances mentioned "audit" by name to cue the scratchpad-consumer angle. NLU re-classified on the keyword and landed on AuditFlow instead of polish. Rephrased as "lean on the findings from the earlier checks".

Button-click path (Vision only):
- Step 3 uses `utterance='select proposal 1'` + static payload + `pre_hook=_seed_proposal_options` to exercise the UI selection-block path.
- Obs and Voice step 3 keep the typed-utterance path with `pre_hook=_reset_outline_flow` (pops the stale OutlineFlow so `_fill_slots` doesn't early-exit on `is_filled()`).

---

## Part 5

**Status: ✅ complete.** Part 5a app built; Part 5b ran all 9 unscoped flows through Round 1 + Round 2 and landed edits to `backend/modules/policies/*.py`, `backend/prompts/pex/skills/*.md`, and `backend/prompts/pex/starters/*.py`. All eval gates pass (251 unit + policy-eval tests; 23 basic-flows; 0 skipped). Consolidated lessons live in [`LESSONS.md`](LESSONS.md) (760 lines, 14 chapters, 110+ lessons traced to source).

Part 5 takes the policy + prompt template locked in Part 3 and applies it to every flow in the 14-step target. Part 3 establishes *what* a good policy looks like; Part 5 *writes the 12 of them*, with user input filling in the per-flow specifics, and gates each batch on the Part 4 evaluations.

### Part 5a — Feedback App

**Goal:** Build an HITL tool that lets the user feed domain knowledge, decision rules, and exemplars into per-flow policy construction. Mirrors `utils/prompt_builder/` but for policies. The template the app serializes **comes from Part 3** (`skill_tool_subagent.md § 3`) — Part 5a is the app, not the template.

**What varies per flow:** the authoritative catalog lives in [`decision_points.md`](decision_points.md) — Part A lists 23 universal conventions (displayed as context, not questions) and Part B lists 19 per-flow decisions (DP-1…DP-19) grouped into six sections: Prompt content, Starter, Few-shot, Error handling, Policy logic, Performance. Each DP has a *Decision*, *Why it matters*, and concrete Refine/Compose/Simplify *Precedents*. The app renders one form field per DP per flow.

**Deliverables:** `utils/policy_builder/` app — `server.py`, `index.html`, `app.js`, `data/` subtree, `README.md`. Built fresh on port **8022** (prompt_builder is gone; no scaffolding to copy from). Vanilla JS + stdlib `http.server`, dropdown flow switcher across a 3-flow batch, tabs per DP-section (Prompt content / Starter / Few-shot / Error handling / Policy logic / Performance) inside each flow.

**Per-flow round structure (mirrors slot-filling):**
- **Round 1 — scaffold + clarifying Q&A.** Claude writes `proposals/<flow>.json` with its best-guess answer for each of the 19 DPs (string, or mode-keyed object for multi-mode flows) plus reasoning. App renders with per-DP accept/override plus a `rationale` textarea for transferable cross-flow reasoning. User exports `answers/<flow>.json`.
- **Round 2 — best draft + final feedback.** Claude reads answers, writes `drafts/<flow>.json` with the final proposed change. App renders side-by-side with a feedback textbox per section. User exports `feedback/<flow>.json`.
- **Landing.** Claude applies feedback directly to `backend/modules/policies/<intent>.py`, `backend/prompts/pex/skills/<flow>.md`, `backend/prompts/pex/starters/<flow>.py`, and `backend/modules/templates/<intent>.py`.

### Part 5b — Execute Batches

**Goal:** Walk the 12 unique flows through the round-1/round-2 loop, landing improvements into the codebase, and verify each batch against the Part 4 evaluations before moving on.

**Batches:** 9 unscoped flows in 3 batches of 3. (Refine, Compose, and Simplify are NOT routed through the app — they are the three hand-written exemplar flows at `backend/prompts/pex/skills/{refine,compose,simplify}.md` whose current content defines the DP precedents. Running them through proposals would be tautological.)

- **Batch 1 (Draft foundations):** `create`, `outline`, `rework` — the entry flows for a new post plus the substantive-revise sibling to the exemplars. Establishes the "good baseline" across one deterministic (create), one bimodal (outline propose/direct), and one agentic-single-mode (rework).
- **Batch 2 (Revise loop):** `add`, `polish`, `audit` — per-section adders plus the basic polish and style audit. Exercises the producer side (audit) and consumer side (polish) of the scratchpad channel (AD-1).
- **Batch 3 (Research + Publish):** `inspect`, `find`, `release` — the post-draft tail. Note that `polish` (informed) is a second pass on the same flow class, so it's covered under Batch 2.

**Workflow per batch:**
1. Claude generates `proposals/*.json` for the 3 flows in the batch, informed by Part 1 inventories, Part 3 fixes, Part 2 best practices, and any lessons from earlier batches.
2. User goes through the app, exports answers.
3. Claude writes `drafts/*.json`; landing is conditional on round-2 feedback.
4. User exports feedback; Claude applies to real files.
5. **After each batch:** run the Part 4 eval suite on the touched flows. Gate the next batch on green.
6. Mid-project: extract lessons after batch 2 and inject them into batch-3 proposals.

**Deliverable:** 9 updated policies + skills + templates (plus the 3 exemplar flows carried over unchanged), all eval-passing, plus `utils/policy_builder/LESSONS.md` summarizing the top 5 policy-layer insights.

---

## Overall Plan

### Parallelism Waterfall

```
Time →
Part 1 ████████ (blocker)
Part 2         ████████████████
Part 3         ████ (census)    ████ (fixes)
Part 4         ████ (draft)        ████ (impl)
Part 5a                            ████
Part 5b                                 ████████ (batches)
```

- **Day 1 (Part 1 blocker):** sub-agent sweep builds 12 inventory templates. Human reviews.
- **Day 2+ (parallel phase):** Part 2 research agent + Part 3 census agent + Part 4 draft agent all running at once. None of them block each other.
- **Day 3 (convergence):** Part 2 deliverable unblocks Part 3 fixes doc + Part 4 impl + Part 5a app build.
- **Day 4+:** Part 5b batches, with evals + lessons propagating between batches.

### Out-of-Scope

- Internal flows (recap / recall / retrieve / search / reference / study / store — all untouched; `inspect` and `find` are Research, not Internal).
- Plan flows (separate playbook, touch later).
- Converse flows (policy-lite; no structural fixes needed from this pass). Exceptions: `explain` and `undo` were migrated in Part 2 Phase 2 because they're deterministic.
- The 33 non-eval-covered flows — stretch goal only if Part 5b finishes early.
- Schema changes to `DisplayFrame`, `DialogueState`, or flow-class contracts.
- NLU slot-filling changes (just finished that project).

---

## Architectural Decisions

These are the decisions that resolved the biggest open questions from Part 1 — bake them into every subsequent part and theme. Numbering gaps (no AD-2, AD-4, AD-5) are deliberate: those three were conventions/references, not code-shaping decisions, and have been moved to `AGENTS.md` (terminology, `OUTLINE_LEVELS`). The remaining seven (AD-1, AD-3, AD-6, AD-7, AD-8, AD-9, AD-10) are the code-shaping set.

### AD-1 — Cross-turn findings channel = **scratchpad with key convention**

No new attribute on `DialogueState`, no new attribute on `DisplayFrame`. The scratchpad (`MemoryManager`, L1, turn-surviving) is the standard cross-policy channel. We adopt a stricter key convention so downstream flows can rely on its shape:

- **Key** = the `flow_name` (e.g. `'inspect'`, `'find'`, `'audit'`).
- **Value** = `dict` with required fields: `version`, `turn_number`, `used_count`, plus flow-specific payload.
- **Type** of the whole scratchpad: `dict[str, dict]` (serializable).
- Each dialogue state is turn-scoped; it already houses the flow stack, so it naturally exposes flow + slot state to any policy that needs it.
- Consumers (e.g. `polish` on turn 13) look up by `flow_name` — or, since max 64 snippets, walk the whole scratchpad and filter.

If a flow needs something the convention can't carry, raise it before adding a new attribute. The bar for new `DialogueState` / `DisplayFrame` attributes is explicit user approval (per AGENTS.md § Boundaries ⚠️).

### AD-3 — Outline recursion is already safe (document, don't refactor)

The existing `outline_policy` only self-recurses AFTER draining `proposals` into `sections`. Since the recursive call is guaranteed to hit the `sections`-filled branch (which does NOT self-recurse), there is no infinite-loop risk. The fix is documentation, not control flow. Do NOT rewrite to an iterative form, do NOT extract `_execute_direct_outline`, do NOT add a depth guard — all of those would be band-aids on a non-existent bug. `OutlineFlow` may not `stackon('outline')` itself.

### AD-6 — Three failure modes, three distinct channels

Every policy handles three classes of "things didn't go smoothly", each with its own channel — **do NOT conflate them under `AmbiguityHandler`**.

**1. Tool-call failure** (platform unavailable, API down, permission denied, network error):
- Use `DisplayFrame(origin='error', metadata={'tool_error': <tool_name>, 'reason': <code|msg>, ...}, code=<raw error text>)`.
- `code` is the existing `DisplayFrame` attribute — it holds error messages (analogous to how it holds successful code). Do NOT invent a new field.
- Do NOT declare ambiguity. A platform being down is not a question for the user; it's a failure the UI surfaces.

**2. Contract violation** (skill output shape mismatch, missing required fields, truncated result):
- First-line fixes: (a) tighten the skill prompt, (b) require JSON output, (c) run `engineer.apply_guardrails(text, format='json')` to parse-and-fail-closed.
- If the validated output still violates the contract at runtime, fall through to an error frame: `DisplayFrame(origin='error', metadata={'contract_violation': <field>}, code=<offending raw output>)`.
- Do NOT declare ambiguity.

**3. Ambiguous user intent** (the prototypical AmbiguityHandler case):
- Use `self.ambiguity.declare(level, metadata=...)` with one of the four levels from `_specs/components/ambiguity_handler.md`:
  - `general` — intent unclear / dialog act unknown
  - `partial` — intent known, key entity unresolved (post / section / channel / …)
  - `specific` — intent + entity known, a slot value is missing or invalid
  - `confirmation` — a candidate value exists and needs user sign-off
- This is the only channel that should produce a clarification question back to the user.

### AD-7 — YAML frontmatter on skill files

Every file in `backend/prompts/skills/` gains a YAML frontmatter header. Minimum schema:

```yaml
---
name: <flow_name>               # matches flow.name()
description: <1-sentence purpose, reusable as routing key>
version: 1
stages:                          # optional, only for flows with staged control flow
  - propose
  - direct
tools:                           # optional, explicit allowlist assertion
  - find_posts
  - generate_outline
---
```

Loader update in `PromptEngineer.load_skill_template` parses the frontmatter and exposes a companion `load_skill_meta(name)` for registries. Frontmatter is additive — legacy loaders that strip it still work. This is Anthropic's 2026 convention and the natural home for the per-flow purpose statement.

**Scope:** currently-present skills get frontmatter. No changes to flows whose skill was deleted (`create`, `find`, `inspect`).

### AD-8 — EVPI default-with-commit for optional slots

Optional slots **with a sensible default** commit with the default and let downstream decide whether to clarify. Do NOT declare ambiguity upfront on optional-slot absence.

Concrete callers today:
- `audit_policy` already does this for `reference_count` (defaults to 5); preserve and document.
- Slots with no obvious default stay as `ambiguity.declare('specific', metadata={'missing_slot': …})`.

### AD-9 — `_validate_frame` tightens; `_llm_quality_check` is off by default

`_validate_frame` in `pex.py` should check that expected *values* are present on the returned frame (e.g., card blocks have the required `post_id` / `title` / `content` keys), not just that `.blocks` is non-empty. Every non-trivial policy already knows its contract — validation enforces it deterministically.

`_llm_quality_check` (the LLM-as-judge secondary check invoked from `_validate_frame` when enabled) should **not run on most turns**. It adds a second LLM call to every response; the deterministic value-checks above are cheaper and more reliable. Reserve LLM quality checking for a small allowlist of flows where prose quality is the whole point (e.g. `polish`, `rework`) — and even there, gate behind a per-flow opt-in flag.

### AD-10 — Token-budgeting easy wins

Two additive, no-conflict changes flagged by Part 2 research:

1. **Prompt caching** on the skill system prompt and tool definitions passed to `PromptEngineer.tool_call`. Anthropic supports `cache_control={'type': 'ephemeral'}` markers on system-prompt + tool-def segments; 1-hour TTL on cache hits. Wire this in `_call_claude` as a one-line additive change per marker. No AD conflict, no behavior change; pure cost + latency win.

2. **Per-flow `max_tokens` tightening**. `tool_call` defaults to `max_tokens=4096`; most flows (inspect, find after dedup, release) never need more than 1024. Propose `flow.max_response_tokens` attribute on `BaseFlow`, default 4096, override per flow. Keeps cost down without capping prose-heavy flows like `rework`.

Both land in `fixes/_shared.md § Token budgeting` once agreed.

---

## Policy-writing conventions

Distilled while writing the six exemplar policies (`utils/policy_builder/skill_tool_subagent.md § 4`). Every Part 3/5 policy change must respect these — deviations need an inline comment citing the convention number. Several of these apply beyond the policy layer; cross-component rules also live in `utils/flow_recipe.md § Coding conventions`.

1. **Don't defend deterministic code.** Service tools (`read_metadata`, `create_post`, etc.) have known contracts. Access keys directly — `flow_metadata['outline']`, not `flow_metadata.get('outline', '')`. If a key is missing or `_success=False`, that's a bug to surface.
2. **No defaults that hide errors.** `text or ''`, `parsed or {}`, `isinstance(parsed, dict)` — mask upstream mistakes. Let the code crash so tests catch it.
3. **Slot priorities are definitional, not advisory** (canonical defs in `utils/flow_recipe.md § 1` / `_specs/components/flow_stack.md § Elective Rule`). Required = must be filled. Elective = exactly one of ≥2 options. Optional = nice-to-have. `flow.is_filled()` encodes both the required check and the at-least-one-elective check; the policy doesn't re-derive them.
4. **Build `frame_meta` and `thoughts` first, then the frame.** Avoid multi-line `DisplayFrame(...)` constructions. One-line instantiation. `DisplayFrame(flow.name())` is the empty-guard shorthand.
5. **`code` holds actual code; `thoughts` holds descriptive text.** `code` is for copy-paste payloads (raw tool response, failing JSON). Descriptive prose goes in `thoughts`.
6. **Keep metadata sparse.** Metadata is for classification (violation category, missing-slot name, duplicate-title sentinel). Flow identity lives in `origin`, not metadata. Specifics go in `thoughts`, not nested-underscore tokens.
7. **`ambiguity.declare` uses `observation`, not metadata keys.** `declare(level, observation=..., metadata=...)` — the human-readable text is `observation`; metadata is classification only. Don't stuff `question`/`reason`/`prompt` into metadata.
8. **Never invent new keys without approval.** Hard rule. Whether in `metadata`, `extra_resolved`, `frame.blocks` data, or anywhere else — don't introduce a new key without explicit approval. If it doesn't fit an existing key, surface the design question.
9. **Standard variable names.** `flow_metadata` for `tools('read_metadata', ...)`, `text, tool_log` for `llm_execute`, `parsed` for `apply_guardrails`, `saved, _` (or `saved_any`, `content_saved`) for `tool_succeeded`.
10. **No em-dashes in `frame.thoughts`.** Thoughts are user-facing. Write like a person: commas, periods, short sentences.
11. **Single return at end; early returns only for major errors.** `partial` and `general` ambiguity use early returns. Everything else — `specific`, `confirmation`, stack-on, fallback, success, AD-6 error frames — assigns to `frame` and falls through to one `return frame` at the bottom.
12. **`origin` is always `flow.name()`.** Every policy-built `DisplayFrame` sets `origin` to `flow.name()`, regardless of success/error. Error-ness lives in metadata (`'violation' in frame.metadata`). The old `origin='error'` sentinel is gone. `flow` is never a metadata key — it lives in `origin` only.

### Violation vocabulary

`metadata['violation']` names what kind of failure occurred. Keep the set small — 8 categories:

| violation | fires when |
|---|---|
| `failed_to_save` | A persistence tool didn't run or produced no effect |
| `scope_mismatch` | The flow ran at the wrong granularity |
| `missing_reference` | An entity referenced in a slot doesn't exist on the post |
| `parse_failure` | Skill output couldn't be parsed into the expected shape |
| `empty_output` | Skill returned nothing when prose was expected |
| `invalid_input` | A tool rejected the arguments given |
| `conflict` | Two slot values contradict |
| `tool_error` | A deterministic tool returned `_success=False` |

An earlier draft carried a parallel `error_class` taxonomy for PEX recovery routing. It was dropped — everything PEX needs is derivable from `violation` + `tool_log`. See `skill_tool_subagent.md § 3.3` for the dispatch rules.

---

## Key Findings

Patterns that surfaced across all 12 flows during Part 1 inventory, and the theme that resolved each.

- **T1 — Skill/policy contract confusion** (create, find, simplify, compose, refine, rework). Grounding + persistence were done twice or skipped entirely. Resolved in Theme 1 (skill deletions + skill-owns-persistence pattern + `merge_outline` tool split for refine).
- **T2 — Unexemplified slots** (rework, simplify, polish, add, outline-`depth`). Slots declared on the flow class but no skill few-shot exercised them. Resolved in Theme 2.
- **T3 — Output-shape drift** (audit, inspect, find, create). Skill-declared shapes didn't match what downstream consumed. Resolved in Theme 3 (structured audit card + inspect-as-deterministic + scratchpad writes).
- **T4 — Error-path gaps** (release, audit, refine, outline). Happy path covered, ambiguity/failure paths skipped. Resolved in Theme 4, which codified AD-6 (three-channel failure model).
- **T5 — Cross-turn findings channel.** Polish at step 13 needs findings from inspect/find/audit (steps 10-12); there was no structured channel. Resolved via AD-1 (scratchpad convention) — not an "informed mode" per AD-2.
- **T6 — Stack-on recursion risk.** Outline is safe by construction (AD-3); compose/refine stack-ons now surface reason via `thoughts`. Resolved in Theme 6.
- **T7 — Repeated guard-clause patterns.** Only `PromptEngineer.tool_succeeded` proved extractable. `guard_slot`/`complete_with_card`/`stack_on` helpers were rejected — slot treatments and frame variations differ too much across flows. Resolved in Theme 7 (scoped down).

Three Part 2 follow-ups surfaced by the research are now ADs (no longer open):
- **Prompt caching** → AD-10.
- **`RecoveryAction` disposition** → DP-1 B in `error_recovery_proposal.md` (landed): remove entirely in Part 3 Phase 2.
- **EVPI default-with-commit** → AD-8.
