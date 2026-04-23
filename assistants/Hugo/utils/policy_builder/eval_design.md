# Evaluation Suite Design

**Status:** design — Part 4 deliverable. Implementation lives in `utils/tests/policy_evals.py` (CLI harness) and `utils/tests/playwright_evals.py` (UI tier).

## Goals

Three tiers with increasing fidelity and decreasing speed:

1. **Unit / policy-in-isolation** — one policy method, mocked tools, seeded state. Sub-second per test. Deterministic (no LLM). Lives in `utils/tests/unit_tests.py` (existing framework) plus new `utils/tests/policy_evals/test_policy_<flow>.py` files per policy.
2. **E2E CLI harness** — full turn pipeline (NLU → PEX → RES), LLM-driven, tool calls to real services where possible. ~5 min for the 14-step sequence. Uses existing `utils/tests/e2e_agent_evals.py`, extended with the new rubric fields below.
3. **Playwright UI tier** — drives `http://localhost:5174` in a real browser. Catches "backend says fine, UI doesn't render / button doesn't work" bugs. Slowest tier (~10 min expected). Lives in `utils/tests/playwright_evals.py`.

Each tier uses the **same rubric keys** but asserts at different scope: Tier 1 on the returned `DisplayFrame`; Tier 2 on `result['frame']` after the full pipeline; Tier 3 on the rendered DOM. Consistency across tiers makes a failure at one tier diagnostic for the tier above.

The three-tier split is the "deterministic core, agentic shell" principle applied to testing ([davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html), cited in `best_practices.md § 8`). Tier 1 is the deterministic core; Tiers 2/3 are the agentic shell. The "discovery deterministic, interpretation LLM" rule ([DEV — Deterministic vs. LLM Evaluators](https://dev.to/anshd_12/deterministic-vs-llm-evaluators-a-2026-technical-trade-off-study-11h)) is why Tier 1 has no LLM-as-judge rubric and Tier 2 does.

## CLI harness (Tier 1 + Tier 2)

### Tier 1 — policy-in-isolation

- **Location:** `utils/tests/policy_evals/test_<flow>_policy.py` (one file per policy method).
- **Pattern:**
  1. Seed a `DialogueState` with pre-filled slots.
  2. Build a stub `FlowStack` with the target flow already active at the top.
  3. Stub `tools` so tool calls return canned results (no network, no LLM).
  4. Call `<Intent>Policy.<flow>_policy(flow, state, context, tools)` directly.
  5. Assert on the returned `DisplayFrame` (origin, blocks, metadata, code) plus `flow.status` plus the tool log.

- **Required fixtures (module-level signatures):**
  - `make_state(active_post=None, keep_going=False, has_issues=False, has_plan=False, pred_intent=None)` — returns a `DialogueState` with the given top-level fields set.
  - `make_flow(flow_name, **slot_values)` — instantiates the flow class from `backend/components/flow_stack/flows.py` and sets each named slot's value via `slot.fill(...)`. Checks `flow.slots[name]` exists (Module Contract guarantee) before filling.
  - `make_tool_stub(responses: dict[str, list[dict]])` — scripted per-tool responses. Each tool name maps to a FIFO list of result dicts (`{'_success': bool, '_error': str|None, ...payload}`); calling the tool pops the next result.
  - `make_context(turn_id=1, convo_history='')` — a `ContextCoordinator` stub exposing `turn_id` (per `fixes/_shared.md § ContextCoordinator.turn_id`) and `compile_history() -> convo_history`.
  - `build_policy(flow_name, memory=None, ambiguity=None, engineer=None)` — instantiates the right `<Intent>Policy` (e.g. `DraftPolicy`, `RevisePolicy`, `PublishPolicy` from `backend/modules/policies/`) with components wired. Memory defaults to a `dict`-backed stub; ambiguity defaults to the real `AmbiguityHandler`; engineer to a minimal stub whose `apply_guardrails` passes through.

- **Assertions cite Part 1 inventory.** Every assertion in a unit test must map to a section of `inventory/<flow>.md` (Tool Plan, Frame shape, Ambiguity patterns, Persistence calls, Guard clauses). Example test function comment:
  ```python
  # Asserts inventory/release.md § Persistence calls:
  # "update_post is NOT called and flow.status is NOT marked Completed"
  # when channel_status fails (fixes/release.md § Changes that landed).
  ```

- **What Tier 1 catches cheaply:** AD-6 tool-failure + contract-violation branches (real services usually succeed in Tier 2, so e.g. the `audit_findings_missing` branch has no Tier-2 trigger); required-slot guard clauses; stack-on paths (`compose`/`refine` → `outline`, `polish` → `rework` fallback per `inventory/SUMMARY.md § Theme 6`); scratchpad writes after `inspect` / `find` / `audit` (AD-1).

### Tier 2 — E2E (existing sequence extended)

- **Location:** `utils/tests/e2e_agent_evals.py` — keep the existing 14 turn-linear steps in `STEPS` and the two outline substeps in `OUTLINE_SUBSTEPS`. No renaming, no re-ordering.

- **Step → policy mapping** (used to choose Tier-1 test-file assignment for each step):

| Step | Utterance intent | Flow | Policy file | Policy method |
|---|---|---|---|---|
| 1 | Create new post | `create` | `draft.py` | `create_policy` |
| 2 / 02a / 02b | Outline (direct / propose / select) | `outline` | `draft.py` | `outline_policy` |
| 3, 4 | Refine outline (bullets / reorder) | `refine` | `draft.py` | `refine_policy` |
| 5 | Convert outline to prose | `compose` | `draft.py` | `compose_policy` |
| 6 | Expand a section | `rework` | `revise.py` | `rework_policy` |
| 7 | Tighten a paragraph | `simplify` | `revise.py` | `simplify_policy` |
| 8 | Add a new section | `add` | `revise.py` | `add_policy` |
| 9 | Polish opening paragraph | `polish` | `revise.py` | `polish_policy` |
| 10 | Inspect metrics | `inspect` | `research.py` | `inspect_policy` |
| 11 | Audit style | `audit` | `research.py` | `audit_policy` |
| 12 | Brainstorm angles | `brainstorm` | `research.py` | `brainstorm_policy` |
| 13 | Find past posts | `find` | `research.py` | `find_policy` |
| 14 | Release to Substack | `release` | `publish.py` | `release_policy` |

- **Existing rubric fields** in each `STEPS` entry (keep): `expected_tools`, `expected_block_type`, `max_message_chars`, `rubric: {did_action, did_follow_instructions}`, `expected_errors`, `expected_ambiguity`.

- **New rubric fields** (from Theme 4 and Theme 5, add per step as applicable):
  - `expected_frame_origin: str` — the flow name on the happy path, `'error'` on the AD-6 tool-failure / contract-violation path. Step 14 already sets this to `'error'` (per `fixes/release.md § Eval rubric aligned with AD-6`). Step 11 should set this to `'audit'` on the happy path and `'error'` with `expected_contract_violation='audit_findings_missing'` on the contract-violation path (cited in `fixes/_interfaces.md § AD-6` and `fixes/audit.md § Changes that landed`).
  - `expected_tool_error: set[str]` — only set when `expected_frame_origin='error'`. The union of tool names whose failure the step explicitly anticipates. Step 14 uses `{'channel_status', 'release_post'}` (per `fixes/release.md`).
  - `expected_contract_violation: str | None` — the expected value of `frame.metadata['contract_violation']` when the skill output fails JSON-shape validation (AD-6 Section 2; cited in `fixes/_interfaces.md § AD-6`). Applies to audit step 11 and refine steps 3/4 as an error-path-only assertion.
  - `expected_scratchpad_keys: list[str]` — scratchpad keys that MUST exist after this step per AD-1 (producers: `inspect`, `find`, `audit`; cited in `fixes/_interfaces.md § AD-1`). Step 10 expects `['inspect']`, step 11 expects `['inspect', 'audit']`, step 13 expects `['inspect', 'audit', 'find']`, step 9 (the polish consumer — but step 9 is before the producers in the linear sequence so it won't trigger consumption; defer to Phase 2 of migration when the informed-polish scenario lands).

- **Assertion back-references.** For every new rubric field, the inline comment cites the inventory file and the `fixes/<flow>.md` section. Example:
  ```python
  # expected_scratchpad_keys: inventory/find.md § Frame shape + Known gaps;
  # AD-1 producer per fixes/_interfaces.md § AD-1; write landed in
  # fixes/find.md § Changes that landed.
  'expected_scratchpad_keys': ['find'],
  ```

## Playwright UI tier

### What Playwright catches that the CLI doesn't

CLI validates `result['frame']` — the serialized payload. It can't see what the UI renders. Playwright-only coverage:

- **Card blocks actually render.** A `CardBlock.svelte` field-name mismatch silently drops the block; CLI sees a correct payload, user sees a blank pane.
- **Selection blocks are clickable.** The outline propose → select path (02a → 02b) depends on clicking option 2 and emitting the right payload; CLI simulates the utterance, Playwright exercises the real click.
- **Confirmation buttons emit the right payload.** For confirmation-ambiguity flows (`audit` threshold-exceeded per `fixes/_interfaces.md § PEX ↔ AmbiguityHandler`), the UI test verifies the button emits `{keep_going:True, payload:{...}}` correctly.
- **Toast messages surface.** The `release` happy path writes `level='success'` (per `fixes/release.md § Success path`); a template regression could hide it.
- **Error-origin frames render a user-visible notice.** AD-6 error frames have `origin='error'` and empty `blocks` — a front-end defaulting to `blocks || []` would white-screen instead of surfacing the tool-error message.

### Driver structure

- **File:** `utils/tests/playwright_evals.py`.
- **Startup:** backend + frontend via `./init_backend.sh` + `./init_frontend.sh` (see `AGENTS.md`) in fixture-scope subprocesses; SIGTERM teardown.
- **Test pattern:** navigate to `http://localhost:5174`, type the utterance into the chat input, submit, poll for a new agent message with `data-turn-id == prev+1` (60s timeout), assert on rendered DOM.
- **Minimum coverage:** 14 steps × one block-type assertion each, plus one click-to-emit assertion on the 02a → 02b selection.
- **Front-end `data-test` attributes** (design only; frontend implementation out of Part 4 scope): every `BuildingBlock.svelte` variant should expose `data-test="<type>-block"` and `data-test-field="<field>"`. Additive, no AD conflict.

### Browser + install

`uv pip install playwright && playwright install chromium`. Gated on the `--ui` pytest flag so CI default-skips it; module-level fixture checks `pytestconfig.getoption('--ui')`. Headless in CI, `--headed` locally.

## Failure-dump format

Every failed assertion in any tier writes a dump to `utils/policy_builder/failures/<run_id>/step_<N>.md`, where `<run_id>` = `YYYYMMDD_HHMMSS`. Rationale (per `best_practices.md § Sources surveyed` citing [QubitTool](https://qubittool.com/blog/agent-harness-evaluation-guide), "log every prompt/response/tool/result"): the dump must be **sufficient for a fresh Claude Code instance to debug from cold** — no conversation context required.

### Schema (stable)

```markdown
# Step <N> failure — <flow_name>

## Expected
- origin: <x>
- tool_log: [<tools>]
- blocks: [<types>]
- metadata: {<keys>}
- scratchpad_keys: [<keys>]
- flow_status: <Running|Completed>

## Actual
- origin: <y>
- tool_log: [<tools>]
- blocks: [<types>]
- metadata: {<keys>}
- scratchpad_keys: [<keys>]
- flow_status: <Running|Completed>

## Diff
(unified diff or bullet-by-bullet; one line per differing field)

## State snapshot
- active_post: <id>
- keep_going: <bool>
- has_issues: <bool>
- scratchpad keys: [<keys>]
- flow stack: [<flows>, top-last]
- turn_id: <n>

## Rubric
(the full rubric text from the step definition, verbatim)

## (Playwright only) Screenshot
<relative path to PNG, e.g. ./step_09.png>

## (Playwright only) Network log (last 20 requests)
| timestamp | method | url | status |
| --- | --- | --- | --- |
| … | … | … | … |

## Reproducer
pytest utils/tests/e2e_agent_evals.py::TestSyntheticDataPostE2E::test_step_<NN>_<name> -v -s --tb=short
```

The reproducer line is a single pytest command — a fresh agent can copy-paste it without reconstructing the sequence.

## Coverage matrix

### Steps × Tiers

`✓` = covered in this tier, `—` = N/A (explained), `◯` = skipped for now (add in Phase N).

| Step | Flow | Tier 1 (unit) | Tier 2 (E2E CLI) | Tier 3 (Playwright) |
|---|---|---|---|---|
| 1 | create | ✓ | ✓ | ✓ (card render) |
| 02a | outline (propose) | ✓ | ✓ | ✓ (selection render + click) |
| 02b | outline (select) | ✓ | ✓ | ✓ (emits payload) |
| 2 | outline (direct) | ✓ | ✓ | ◯ (Phase 3 follow-up) |
| 3 | refine (bullets) | ✓ | ✓ | ◯ |
| 4 | refine (reorder) | ✓ | ✓ | ◯ |
| 5 | compose | ✓ | ✓ | ◯ |
| 6 | rework | ✓ | ✓ | ◯ |
| 7 | simplify | ✓ | ✓ | ◯ |
| 8 | add | ✓ | ✓ | ◯ |
| 9 | polish | ✓ | ✓ (retry-loosen; see § Stability work) | ◯ |
| 10 | inspect | ✓ | ✓ | ◯ |
| 11 | audit | ✓ | ✓ | ◯ |
| 12 | brainstorm | ✓ | ✓ | ◯ |
| 13 | find | ✓ | ✓ | ◯ |
| 14 | release | ✓ | ✓ | ✓ (error-origin render) |

### Flows × Inventory findings

For each flow, the unit test file verifies at least the following inventory-cited invariants. "Gap" rows are deliberately left as `◯` when the inventory says so (e.g. unexemplified image slot on polish).

| Flow | Invariants verified in Tier 1 | Inventory cite |
|---|---|---|
| create | `create_post` called exactly once; duplicate-title → `ambiguity.declare('specific', {'missing_slot':'topic'})`; skill is not invoked | `inventory/create.md § Persistence calls, § Ambiguity patterns`; `fixes/_interfaces.md § PEX ↔ AmbiguityHandler` |
| outline | Propose mode excludes `generate_outline` + `merge_outline`; direct mode calls `generate_outline`; self-recurses at most once (AD-3) | `inventory/outline.md § Propose mode, § Staging`; `fixes/_interfaces.md § AD-3` |
| refine | Append-intent uses `merge_outline`; removal-intent uses `generate_outline`; shrink-without-removal → contract-violation error frame | `inventory/refine.md § Known gaps`; `fixes/refine.md § Changes that landed` |
| compose | Per-section preview included in resolved context; stack-on `outline` when sections missing | `inventory/compose.md § Tool plan, § Stack-on` |
| rework | `_mark_suggestions_done` ticks each completed suggestion; suggestion / remove slots pass through to skill | `inventory/rework.md § Known gaps`; `fixes/_shared.md § RevisePolicy._mark_suggestions_done` |
| simplify | No double-persist — only policy's `_persist_section` writes | `inventory/simplify.md § Persistence calls` |
| add | `insert_section` called with resolved `target_section` for position | `inventory/add.md § Tool plan` |
| polish | Structural-issue fallback → `flow_stack.fallback('rework')` + `state.keep_going=True`; consumer reads scratchpad and bumps `used_count` | `inventory/polish.md § Stack-on triggers`; `fixes/_interfaces.md § AD-1` |
| inspect | Scratchpad write: `{version, turn_number, used_count:0, metrics:...}` keyed on `'inspect'` | `inventory/inspect.md § Frame shape`; `fixes/_interfaces.md § AD-1` |
| find | List block carries post status + outline preview (unblocks audit/polish); scratchpad write under `'find'` | `inventory/find.md § Known gaps`; `fixes/find.md § Changes that landed` |
| audit | Structured findings in card block (not thoughts); `audit_findings_missing` contract-violation error frame on bad shape; threshold-exceeded → `ambiguity.declare('confirmation', {'reason':'audit_threshold_exceeded'})` | `inventory/audit.md § Output shape, § Ambiguity patterns`; `fixes/audit.md § Changes that landed` |
| release | `update_post(status='published')` gated on tool success; tool failure → `DisplayFrame(origin='error', metadata={'tool_error':...}, code=...)` not ambiguity | `inventory/release.md § Known gaps`; `fixes/release.md § Changes that landed` |

## Stability work

### Step 9 polish flake

Polish has historically been flaky on LLM nondeterminism (per `inventory/polish.md § Known gaps`) — the skill occasionally takes a clarification branch ("which paragraph?") even when the utterance is unambiguous. Three options:

1. **Retry-with-diagnostic** — re-run the same turn up to 2x, fail only if both runs fail, log the divergence regardless.
2. **Tighten the skill prompt** — add a negative exemplar discouraging unnecessary clarification.
3. **Accept both outcomes** — loosen the rubric to `expected_block_type in ('card', 'selection')`.

**Recommendation: (1) retry-with-diagnostic.** (2) is a skill-prompt edit belonging to a per-flow fix cycle, not the eval harness. (3) loses the signal we most want to catch — the skill asking when it should be committing violates EVPI guidance in `best_practices.md § 5` (citing [arXiv 2603.26233 — Ask or Assume?](https://arxiv.org/html/2603.26233)). Retry-with-diagnostic gives resilience to the 15% LLM-accuracy swing in `best_practices.md § 8` (citing [Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)) while still catching genuine regressions (two consecutive flaky runs). (2) and (3) become **open follow-ups**.

### LLM nondeterminism in general

Per `best_practices.md § 8` (citing [Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)): even at `temperature=0`, accuracy swings up to 15% across runs. Recommendations:

- In Tier 2 / Tier 3, set `temperature=0` in the agent's eval-mode config (confirm in `schemas/config.py` during implementation).
- Require 2-of-3 successive passes for "green" in CI on Tier 2 / Tier 3.
- Tier 1 is single-run-gatable (no LLM).

### Step 11 audit — now resolved

`inventory/SUMMARY.md § Theme 3` and `AGENTS.md § Known e2e quality gaps` flagged step 11 surfacing post content instead of a structured style report. Theme 3's `fixes/audit.md` put structured findings in the card block and routed AD-6 contract-violation to the error-origin frame. The new `expected_contract_violation='audit_findings_missing'` rubric guards against regression.

### Pre-existing `TestEnsembleVoting` failures

Three `TestEnsembleVoting` tests in `utils/tests/unit_tests.py` fail — NOT caused by Theme 1-7 policy work, an orthogonal NLU refactor issue. Listed so the harness implementation agent does not treat them as new regressions. Track as open follow-up.

## Migration plan

- **Phase 1** — scaffold `utils/tests/policy_evals/` and write 2 unit tests. Start with `release` (exercises AD-6 tool-failure error frame + gated persistence + success toast — step 14 was the Theme 4 anchor) and `audit` (exercises contract-violation error frame, AD-1 scratchpad write, confirmation-ambiguity threshold escalation — three AD-6-linked surfaces in one flow). Together they cover every new rubric field and every AD-6 branch, proving the template for the other 10 flows.

- **Phase 2** — extend `utils/tests/e2e_agent_evals.py` with the new rubric fields (`expected_frame_origin`, `expected_tool_error`, `expected_contract_violation`, `expected_scratchpad_keys`) on steps 10-14. Wire `_check_level1` to read `frame.metadata.get('contract_violation')` and cross-check `agent.memory.read_scratchpad()` for expected keys.

- **Phase 3** — Playwright. Start with step 1 create (simplest card render, no prior state) and step 14 release (highest-value error-origin render — the UI shouldn't white-screen on AD-6 error frames). Add the 02a → 02b selection-click test once the driver is stable.

## Back-references to Part 1

Every rubric field and assertion cites its inventory source. Spot-checks:

- Release step 14 asserts `frame.metadata['tool_error'] ∈ {channel_status, release_post}` — `inventory/release.md § Eval step`, `fixes/release.md § Eval rubric aligned with AD-6`.
- Audit step 11 asserts structured card block (not `thoughts`) — `inventory/audit.md § Output shape`, `fixes/audit.md`.
- Polish step 9 retry-on-flake — `inventory/polish.md § Known gaps`.
- Scratchpad keys per step — `fixes/_interfaces.md § AD-1`; producer rows in `inventory/inspect.md`, `find.md`, `audit.md`.
- Outline propose-mode tool exclusion — `inventory/outline.md § Propose mode`, `fixes/_shared.md § exclude_tools`.
- Refine append-vs-overwrite — `inventory/refine.md § Known gaps`, `fixes/_shared.md § Content tool split`.

## Part 2 alignment

- **Three-tier recovery taxonomy** — `best_practices.md § 3` (citing [notes.muthu.co](https://notes.muthu.co/2026/02/error-recovery-and-graceful-degradation-in-ai-agents/) and [TDS](https://towardsdatascience.com/your-react-agent-is-wasting-90-of-its-retries-heres-how-to-stop-it/)) — informs the AD-6 three-channel assertions and step 9's retry-with-diagnostic.
- **Determinism boundaries** — `best_practices.md § 8` (citing [davemo.com](https://blog.davemo.com/posts/2026-02-14-deterministic-core-agentic-shell.html) and [DEV — Deterministic vs. LLM Evaluators](https://dev.to/anshd_12/deterministic-vs-llm-evaluators-a-2026-technical-trade-off-study-11h)) — Tier-1 no-LLM vs Tier-2 LLM-judge split, 2-of-3 passes rule.
- **Agent harness engineering** — `best_practices.md § Sources surveyed` (citing [QubitTool](https://qubittool.com/blog/agent-harness-evaluation-guide)) — "log every prompt/response/tool/result" underpins the cold-debug failure-dump requirement.
- **Defeating nondeterminism** — `best_practices.md § 8` (citing [Thinking Machines Lab](https://thinkingmachines.ai/blog/defeating-nondeterminism-in-llm-inference/)) — `temperature=0` + retry-with-diagnostic.
- **Ambiguity as cost/value** — `best_practices.md § 5` (citing [arXiv 2603.26233 — Ask or Assume?](https://arxiv.org/html/2603.26233)) — rejects step 9 option (3): loosening the rubric would train us to accept EVPI-violating behaviour.

## Open follow-ups

- Skill-prompt tightening on polish to reduce the clarification branch (step 9 option 2 above).
- 2-of-3 CI gating on Tier 2 / Tier 3 needs CI-side support (not pytest-local); design-only here.
- Retry-with-exponential-backoff on release's transient failures (noted in `fixes/release.md § Open follow-ups`).
- Multi-channel release loop (also in `fixes/release.md § Open follow-ups`) — expands step 14's `expected_tool_error` assertion shape.
- Consume `AmbiguityHandler.should_escalate()` in PEX recover tier 4 (`best_practices.md § 5`) — would add a new rubric field `expected_escalation_level` to Tier 2.
- Front-end `data-test` attribute pass — strictly additive, no AD conflict, but must land before Playwright tier is useful.
- Pre-existing `TestEnsembleVoting` failures (orthogonal NLU refactor).
