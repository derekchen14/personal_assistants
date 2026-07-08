# Round 1 — Evaluation System (the full plan)

Maps to **Master Plan · Round 1**, but **rescoped**: Round 1 was originally just the trace-replay runner. It is
now the plan for the **whole evaluation system** — the three eval levels, the harness, the data pipeline, the
metrics, and the phased roadmap. It absorbs the eval items that were parked in Round 6 (parity oracle
re-baseline, E8). It remains the **early enabler** that gates the risky behavioral steps — the **Traces** phase
must be green before Round 3's NLU intent rework.

This is a **living document**: the roadmap section carries status checkboxes that we update as phases land.

> **Naming.** We do **not** use `L1/L2/L3` (those collide with the Memory Tiers). The three levels are
> **Model Unit Tests**, **Observability Traces**, and **E2E Agent Evaluations** — shorthand **Tests**,
> **Traces**, **Evals**. Sub-parts are named descriptively, never lettered.

Spec: `_specs/utilities/evaluation.md` (the eval ladder + regression-gate table — note the spec still uses the
old letter codes; updating it to these names is a follow-up).
Operational guide (currently **stale** — documents the dead NLU→PEX→RES pipeline):
`assistants/Hugo/utils/evals/evaluation_guidelines.md` — rewrite is part of the Tests phase.

---

## North star

Evaluation exists to **earn the confidence to deploy to customers**. Trust correlates with — but is distinct
from — single-model accuracy. The organizing principle is a **ladder**: cheap, deterministic checks at the
bottom; expensive, full-loop, judged checks at the top. Each rung gates the next.

The three levels:

| Level | Question it answers | Made of |
|---|---|---|
| **Model Unit Tests** | Did a single model decision get classified right? | contract tests (no LLM) + accuracy tests (one LLM call) |
| **Observability Traces** | Did we call the right tools / sub-agents, in the right order? | trace replay + adversarial/robustness |
| **E2E Agent Evaluations** | Did the agent do the right thing overall? | parity (3-axis) + judge rubric |

The two headline Eval metrics are **task completion rate** and **task success rate** (defined under E2E Agent
Evaluations).

---

## Decision log

All decisions, open or closed, live here (items 1–8 locked 2026-06-21; 9–13 added 2026-06-22).

1. **Harness = pytest + custom CLI + Langfuse (Langfuse deferred).** Pytest owns the deterministic contracts +
   lints. A purpose-built CLI harness owns the accuracy tests, the traces, and the agent evals (scoring,
   baseline-diff gates, reports). **Langfuse** is the future observability/dashboard/run-history layer — a
   **seam is designed now, integration is deferred** (hosted-vs-self-hosted + data-egress reviewed before
   turn-on); we do simpler internal verification first.
2. **Data = LLM-synthesized seed now; recorded traces as ground truth later.** The current
   traces/snapshots/oracle are **outdated** (dead 48-flow taxonomy + retired `detect_and_fill`) and are
   **discarded**, not migrated. Bootstrap on a hand-generated **64-conversation seed** + **192 synthesized** (augmentation + denoising). Once the agent behaves correctly, **re-record gold traces from the working agent** and use them as
   the regression net (the Traces phase).
3. **Success = hybrid metric.** Completion = ran to a final answer without crash / give-up / fallback. Success =
   deterministic end-state facts match the oracle (**HARD gate**) **and** an LLM-judge rubric passes (**soft**).
4. **Run cadence = tiered.** Contract tests + lints gate every commit; accuracy + trace evals run nightly and on
   relevant prompt/ontology/policy changes; full E2E is manual / pre-release.
   - **Default to a fresh dev sample of 8.** Every paid tier (model / traces / evals) defaults to a **random
     ~8 conversations drawn from `train.jsonl` per build** (`harness.sample`) — not a fixed set, never the
     full corpus (we almost never run all 96). Pass `--ids` for a chosen set, or `--all` for the whole train
     split (a pre-release gate). All runners share `harness.sample`/`load_cases`, so a "model" run and a
     "traces" run draw from the same split the same way. (Supersedes the earlier fixed `DEFAULT_SCENARIOS`
     idea — see [[round_2.10_orchestrator_activation.md]] "Shared prerequisite".)
5. **Trace determinism = cached-vote replay.** Record each ensemble voter once at temp-0; replay feeds cached
   votes back so flow detection is deterministic and the gate never re-rolls the model.
6. **Adversarial robustness = part of Observability Traces, designed now** (built in the final phase), not
   deferred to a separate plan.
7. **Synthesis trust = manual seed, synthesized bulk.** Hand-generate the **64-conversation seed** together (no
   exemplar leakage); synthesize the bulk via augmentation + denoising with human approval on labels +
   recorded gold. On disk the corpus is three JSONL splits under `utils/evaluation_suite/datasets/`:
   **`train.jsonl`** (the 96 labelled conversations, one JSON per line), **`dev.jsonl`** and **`test.jsonl`**
   (placeholders for now). **Dev** is a fresh random ~8 drawn from train per build (dynamic, not a stored
   slice); the held-out **Test** set is real usage (empty for now). See the Train/Dev/Test split below.
8. **Phasing** (the order we build): **P1** task *completion* (coarse Eval, on seed data) → **P2** Model Unit
   Tests → **P3** Observability Traces (regression net) → **P4** task *success* (rigorous Eval) + adversarial
   robustness.

9. **Dataset volume — the coverage funnel — DECIDED.** **256 conversations** = **64 manual seed + 192
   synthesized** (augmentation + denoising; generator = Opus); 7 turns each (4 user + 3 agent) → **1024**
   flow-detection + **512** slot-filling examples (~64/flow over 16 flows); **256** trajectory traces from **64**
   conversations; **32** E2E conversations (8 scenarios × 4 topics), of which **16** are the ambiguity-recovery
   core. See the Dataset coverage funnel.
10. **Tolerance rules — DECIDED.** Two `tolerance_rules.md` rules, executed at Phase 3 re-recording: **(06)** a
    clarification must go through `handle_ambiguity(declare)` — bare-text asks fail the gate (lands with Round 3);
    **(07)** a multi-step request must stack sub-flows in dependency order — match on ordering, not a shared id
    (`plan_id` removed; lands with Round 5).
11. **E8 — parity oracle re-baseline — DECIDED (Phase 4).** Re-capture the parity oracle from an approved
    orchestrator run, converged with the recorded-trace model (folded here from Round 6).
12. **CI provider — OPEN.** No CI today; the runner is CI-agnostic and the skeleton lands in Phase 1. *(The one
    still-open item.)*

13. **Dev = 25% sample; the feature-build loop — DECIDED.** Dev is a random 25% slice of Train (≈64), handed to
    the SWEs to start; the full **256 (4× Dev)**, expanded with QA + PM, is the **correctness threshold** and the
    regression set; each checkpoint runs a **random 25% sample** of the suite to bound cost. See the
    Feature-build loop.

### The three automation approaches considered

For the record (we chose **A+B now, C later**):

- **A — pytest-native, extended.** Familiar, IDE-integrated, cheapest; but pass/fail fights accuracy scoring,
  aggregation, and trend tracking.
- **B — standalone CLI harness (build).** Purpose-built for scoring/aggregation/baseline-diff/reporting; maps
  cleanly onto the ladder; most code to own.
- **C — third-party framework (buy):** dashboards, dataset versioning, judge, run history out of the box; but
  integration friction with the bespoke ensemble-NLU / flow-stack / cached-vote-replay agent.

**Chosen:** pytest (A) for deterministic contracts + custom CLI (B) for everything that scores; **Langfuse (C)**
added later for observability only — a seam now, no runtime dependency yet.

---

## Current-state audit

| Asset | Level | Status | Action |
|---|---|---|---|
| `unit_tests.py` (206 service/contract tests) | Tests | ✅ solid, mostly architecture-agnostic | Keep; add slot/entity assertions |
| `test_artifacts.py` (skill/tool/schema lints) | Tests | ✅ solid | Keep |
| `test_nlu_module.py` (belief contracts) | Tests | ✅ current | Keep |
| `model_tests.py` (NLU accuracy) | Tests | ⚠️ runs, but on dead labels | Re-target to new `model_cases.json` |
| `test_cases.json` (100 cases / 205 turns) | Tests/Evals | ❌ dead 48-flow labels (21/35 flows gone) | **Discard**; synthesize fresh |
| `traces/*.json` (10) + `tolerance_rules.md` | Traces | ❌ encode retired `detect_and_fill`; nothing reads the rules | **Discard traces**; keep rules vocab; re-record in P3 |
| `parity/` recorder + comparator (3-axis) | Traces/Evals | ⚠️ harness OK; oracle from deleted pipeline (E8) | Reuse harness; re-baseline oracle in P4 |
| `e2e_agent_evals.py` (14-step, 3-tier) | Evals | ⚠️ dead-flow scenario | Replace scenario; reuse the 3-tier scaffolding |
| `e2e_multiturn_evals.py` (ambiguity) | Traces/Evals | ⚠️ partial | Fold into adversarial robustness (P4) |
| `snapshots/` (Vision/Observability, 14 steps) | Evals | ❌ dead-flow filenames | Regenerate from re-recorded scenarios |
| `evaluation_guidelines.md` | doc | ❌ documents dead NLU→PEX→RES | Rewrite in P2 |

The 16-flow catalog the new data must target: Research `find/browse/summarize/compare`, Draft
`outline/compose/refine/brainstorm`, Revise `rework/write/audit/propose`, Publish `release/schedule/cite`,
Converse `chat` (+ NLU-only `Clarify`, no flows).

---

## Inventory & targets (proposal)

Counts as of the `utils/{tests,traces,evals}` restructure. **Have** is what exists today; most of the
LLM-bearing assets are on the **dead taxonomy** (48-flow labels / retired `detect_and_fill` / 14-step
lifecycle) and are rebuilt against the 16-flow catalog, not migrated.

| Tier | Have today | Dead taxonomy? | Target |
|---|---|---|---|
| **Tests — contract** (no LLM) | **337** — `unit_tests` 206, `test_artifacts` 123, `test_nlu_module` 8 | architecture-agnostic — keep | ~337 + slot/entity assertions |
| **Tests — accuracy** (1 LLM call) | `model_tests` 13 + `test_cases.json` (100 cases / 205 turns) | ❌ dead flows (suggest/check/survey/calendar) | **1024** flow-detection + **512** slot-fill examples (256 convos × 4 turns, ~64/flow) |
| **Traces** (Observability) | 10 recorded trajectories + parity 3-axis harness | ❌ retired `detect_and_fill` | **256** traces from **64** conversations |
| **Evals** (E2E) | 3 lifecycle scenarios (Vision/Obs/Voice ×14) + 3 ambiguity + 1 completion anchor; 28 snapshots | ❌ 14-step dead taxonomy | **32** conversations (8 scenarios × 4 topics; 16 happy + 16 ambiguity) |

The contract tests are the only assets that survive as-is; everything LLM-bearing is re-synthesized.

## Train / Dev / Test split (by data source)

The split is by **where the data comes from**, not which tier consumes it:

On disk the split is three JSONL files under `utils/evaluation_suite/datasets/` (`train.jsonl`, `dev.jsonl`,
`test.jsonl`). The split is by **where the data comes from**, not which tier consumes it:

| Split | File | Source | Role |
|---|---|---|---|
| **Train** | `train.jsonl` | **64 manual seed + synthetic bulk** (augment + denoise) | the working set — **96 today**, growing toward the 256 target |
| **Dev** | `dev.jsonl` (placeholder) | **a fresh random ~8 drawn from Train per build** (`harness.sample`) | what a build iterates on + judges against — **dynamic, not stored** |
| **Test** | `test.jsonl` (placeholder) | **real Hugo usage** (logged failures, user-reported misses) | the true held-out generalization measure — **empty for now** |

**Train is built, not collected:** the seed conversations we hand-generate together (including the
hand-brainstormed E2E ambiguity scenarios) **+** synthesized ones via data-augmentation and -denoising cycles;
the **256** figure is the target, **96** exist today. **Dev is drawn fresh, not stored:** each build samples
~8 random conversations from `train.jsonl` — representative and dynamic, so no single slice gets overfit
(`dev.jsonl` is a placeholder for a frozen slice if we ever want one). The held-out **Test** set is real
usage (empty for now). Leakage rule still holds — synthesized Train must not reuse a prompt exemplar's topic
(e.g. Kitty Hawk).

### Feature-build loop (how the data drives the team)

1. **Hand a fresh Dev sample (~8) to the SWEs** to start building the feature.
2. **You + QA + PM 4× it to the full 256** — that full set is the feature's **correctness threshold**.
3. Once it lands, the **same 256** guards against **regressions**.
4. **Each checkpoint runs a random 25% sample of the suite** (≈Dev-sized) to keep cost down; the full set runs
   only at the correctness gate and pre-release.

(The SWE / QA / PM roles are the engineering team in `_specs/agents/`.)

## Dataset coverage funnel

One nested set of **256 synthesized conversations** — 7 dialogue turns each (**4 user turns** to predict + 3
agent responses) — feeds every tier. Each tier adds richer labels to a **halving subset** of the one above, so
one conversation can serve several tiers at once:

| Tier (label depth) | Unit | Target | Derivation |
|---|---|---|---|
| Flow detection — Model Unit Tests | user-turn | **1024** | 256 conversations × 4 user turns → **~64 / flow** |
| Slot-filling — Model Unit Tests | user-turn | **512** | half of 1024 (128 conversations) |
| Tool-call trajectories — Observability Traces | trace / user-turn | **256** | half of 512 → **64 conversations** |
| Task completion — E2E Agent Evals | conversation | **32** | half of 64 → **8 scenarios × 4 topics** (extended) |
| └ ambiguity-recovery core | conversation | **16** | **4 ambiguity scenarios × 4 topics** |

**Source.** The **64-conversation seed** is hand-generated together — including the hand-brainstormed E2E
ambiguity scenarios, where most of the design effort goes; the other **192** are **synthesized** (augmentation
+ denoising) then human-approved. Trajectory gold (256 traces) is **recorded** from live runs and approved.
**Dev** is a random 25% slice of the 256; **Test** is real usage (empty for now).

### E2E scenario design (the 32)

The E2E tier is judged **only by task completion** — not by turn count or tool calls (the Traces tier owns
those). These are **extended** conversations: **8 use cases × 4 blog-post topics = 32**.

- **4 happy-path scenarios** — the user collaborates smoothly, but each walks **different flows** so coverage
  spans the catalog rather than one lifecycle.
- **4 ambiguity / recovery scenarios** — the agent must **recognize and recover** from ambiguity (or other
  issues) inside a complex task.

The **4 ambiguity × 4 topics = 16 conversations** are the heart of the effort: most of the work is
**brainstorming exactly how each plays out — what the agent should do at every turn** — so these double as the
hand-designed Dev set. (The 4 happy-path × 4 topics are the other 16.) Adversarial/robustness probes stay
separate, in the Observability Traces tier (P4).

## Layout rationale

The directory split mirrors the eval ladder **1:1**, so a file's location states which tier it belongs to and
how it runs:

- **`utils/tests/`** — Model Unit Tests: pytest, deterministic, gates every commit (`unit_tests`,
  `test_artifacts`, `test_nlu_module`; accuracy via `model_tests`).
- **`utils/traces/`** — Observability Traces: the parity recorder/comparator plus recorded gold trajectories;
  cached-vote replay, nightly cadence.
- **`utils/evals/`** — E2E Agent Evaluations: the scoring CLI harness (`run_evals`, `gates`, `scorers`,
  `datasets`, `baselines`) plus the full-loop scenarios; nightly + pre-release.
- **`utils/`** (shared) — `harness.py` (build the orchestrator Agent, seed/clean posts), `conftest.py`,
  `_snapshot.py`, `helper.py`. Each tier has a different cadence, data source, and determinism strategy;
  separating the dirs keeps the ladder legible and lets each tier evolve without entangling the others, while
  the shared agent harness lives in exactly one place.

---

## Target architecture

### Harness layout

```
assistants/Hugo/utils/                 # three tiers map 1:1 to the eval ladder + shared infra
  harness.py                           # shared: build orchestrator Agent, seed/clean posts
  conftest.py  _snapshot.py            # shared: pytest fixtures/markers, snapshot helper
  helper.py                            # shared: DAX / flow lookups
  tests/                               # Model Unit Tests — pytest, deterministic, gate every commit
    unit_tests.py  test_artifacts.py  test_nlu_module.py   # contract + lints (no LLM)
    model_tests.py  test_cases.json                        # accuracy (1 LLM call) → retarget to model_cases.json
  traces/                              # Observability Traces — parity harness + recorded gold
    parity/                            #   recorder + 3-axis comparator + fixtures (reuse)
    <NN>_<name>.json/.md               #   recorded gold trajectories  ·  tolerance_rules.md
  evals/                               # E2E Agent Evaluations — scoring CLI harness + scenarios
    run_evals.py  gates.py  scorers/   #   entrypoint, folded-baseline gate, scorers
    datasets/ (scenarios/  model_cases.json  oracles/)   baselines/   report/
    e2e_agent_evals.py  e2e_multiturn_evals.py  snapshots/
    synthesize.py  langfuse_sink.py    #   planned: dataset generator; Langfuse export seam
```

- **Split rationale:** deterministic, millisecond checks stay in pytest (fast, gate every commit). Everything
  that *scores* (accuracy %, trajectory %, completion/success rate, judge rubric) lives in the CLI harness,
  where aggregation, baseline-diff, and reporting are first-class — pytest's binary assert model is the wrong
  shape for those.
- **One entrypoint, four levels.** `run_evals.py --level tests|traces|evals|adversarial` with a `--tier`
  (`commit|nightly|prerelease`) selecting the dataset slice. Always writes a report + a machine-readable
  metrics blob; `gates.py` diffs that against `baselines/` and sets the exit code.
- **Langfuse seam (deferred).** `langfuse_sink.py` is a no-op shim now: the harness already produces per-run
  traces + scores; the sink will later forward them to Langfuse for dashboards and trend history without
  touching the runners. No runtime dependency until we turn it on.

### Data pipeline (synthesize → approve → record gold)

```
1. synthesize.py            LLM generates scenarios + intent/flow/slot/entity labels (per the
                            confidence-experiment guidelines: short, implicit, context-dependent utterances)
2. human approve labels     64-conv seed hand-written; 192 synthesized labels reviewed before use
3. run through live Hugo     execute the approved scenario end-to-end on current code
4. human approve gold        approve the recorded tool-trajectory (Traces) and end-state oracle (Evals)
5. freeze                    recorded gold becomes the regression ground truth (cached votes for traces)
```

- **Why record gold instead of synthesizing it:** a synthesized *label* is fine, but a synthesized *trajectory*
  or *end-state* won't reliably match live tool APIs. Gold trajectories/oracles must be **recorded from real
  behavior and approved** — this is exactly the user's "use the traces as ground truth once things work."
- **Leakage guard:** synthesized **Train** cases must not reuse a prompt exemplar's topic (e.g. the Kitty Hawk
  anchor must never appear in a prompt exemplar) — see the Train/Dev/Test split above. **Dev** is a random 25% slice the SWEs iterate on; the held-out **Test**
  set comes from real usage.

### Case schema (what `synthesize.py` emits)

One shape for all phases — each conversation is one JSON object, stored one-per-line in
`datasets/train.jsonl` and consumed by every tier (accuracy and multi-turn alike). Each phase reads a
documented subset:

```jsonc
{
  "convo_id": 17, "domain": "hugo",
  "available_data": { "posts": [{ "post_id": "Seed01", "title": "Prompt Caching for LLM Apps" }] },
  "turns": [
    { "turn_count": 1, "role": "user",
      "utterance": "Trim the Approach section of the prompt caching post.",
      "labels": { "intent": "Revise", "flow": "rework", "dax": "{5A1}" },
      "slots": { "source": { "post": "Prompt Caching for LLM Apps", "sec": "Approach" } },
      "expected_tools": ["read_content", "revise_content"],
      "rubric": { "did_action": "...", "did_follow_instructions": "..." } }
  ]
}
```

| Field | P1 completion | P2 accuracy | P3 traces |
|---|---|---|---|
| `utterance` (user) | drives the turn | drives the turn | drives the turn |
| `labels.{intent,flow,dax}` | `flow` only (expected-flow check) | **all** (accuracy scoring) | — |
| `slots` | — | slot-fill / entity F1 | — |
| `expected_tools` | — | — | seed for the recorded gold trajectory |
| `rubric` | — | — | — (P4 judge) |
| `available_data` | seeds posts | seeds posts | seeds posts |

`expected_tools` is advisory — the real gold trajectory is **recorded** from a live run and approved (P3),
not synthesized. Fields unused until P3/P4 are the frozen targets the later red→green loops aim at.

### Determinism

- **Traces:** cached-vote record-once / replay-many at temp-0; the gate is fully deterministic.
- **Evals:** temp-0 in eval-mode config; require **2-of-3** successive passes for "green" on the LLM-bearing
  levels to absorb residual nondeterminism. Contract tests are single-run-gatable (no LLM).

---

## Model Unit Tests

**Contract tests (no LLM):** component contracts and pure logic — Dialogue State belief tools, Flow Stack
reload, slot typing, Task Artifact `Part` oneof, `state.json` round-trips, scratchpad stamping,
completion-record shape, service round-trips, the static lints. **This is the gate every other level assumes.**
Mostly already green; add the missing slot-fill and entity-extraction assertions.

**Accuracy tests (one LLM call, no full loop):** per-decision classification accuracy against `model_cases.json`.

| Metric | What it measures | Gate |
|---|---|---|
| Flow-detection accuracy (top-1) | the sharpest single signal — right flow from 16 | **> 2% drop** |
| Intent accuracy | correct of the 7 intents | baseline-diff |
| Slot-fill exact-match / F1 | declared slots filled with right values | baseline-diff |
| Entity-extraction F1 | post/section/snippet/channel spans | baseline-diff |
| Confidence calibration | floor respected + endorsed/guessed separation | baseline-diff |
| Ensemble agreement (med-tier) | voter consensus rate; flags cross-intent splits | report-only |

See the **Dataset coverage funnel** above. **Volumes:** **1024** flow-detection examples (256 conversations ×
4 user turns, ~64/flow); **512** of those also carry slot-fill labels. Train = 64 manual seed + 192 synthesized; Dev = a random 25%
slice; Test = real usage, empty for now. Reported as percentages with a baseline; **not** binary pytest asserts.

---

## Observability Traces

### Trace replay (deterministic + tolerance)

Replay human-approved tool-call trajectories — **target 256 traces from 64 conversations** (the funnel). The
recorder parses a session into per-turn `(tool, key_args,
ok)` sequences, activated flows, and completion records; replay compares against the approved gold, allowing
only the documented tolerances, feeding cached votes so detection is deterministic.

**Trajectory scoring modes** (report all four; default to **full workflow**, the strictest):

| Mode | Measures |
|---|---|
| Partial path | correct tools in sequence until first error |
| Full path | exact sequence, all-or-nothing |
| Path nodes | correct tools regardless of order |
| Full workflow | full path **and** correct flow |

Gate: **trajectory (full workflow) > 3% drop**.

**Tolerance engine:** loads `tolerance_rules.md` (global rules + per-trajectory rules) and decides, per (gold,
actual) call pair, whether a diff is within tolerance — order-insensitive where allowed, arg-fuzzy where
allowed, required-call presence, forbidden-call absence. Keep the existing call-class vocab (belief-write /
read-only / mutation / ambiguity-ask); re-record the trajectories themselves.

### Adversarial / robustness (designed now, built P4)

Each probe asserts *bounded, graceful recovery*, not a happy path:
- Ambiguity declaration + recovery (`handle_ambiguity`; NLU `contemplate` re-route).
- Corrective tool-error loops — malformed belief-tool call, unknown flow, unknown slot, grounding violation →
  `{_success: False}` and retry within the consecutive-failure cap.
- Input guards — reserved-keyword / injection rejection, length + repeat guards.
- The lethal-trifecta approval gate; the round budget and `_final_emit` wrap-up.

Gate: **robustness pass rate — any drop**.

---

## E2E Agent Evaluations

Full orchestrator loop, real LLM + real tools, multi-turn scenarios. The two headline metrics:

- **Task completion rate** (coarse, first phase): fraction of tasks that run end-to-end to a final answer with
  **no crash, no give-up, no fallback message**, and the expected flow activated. Deliberately ignores
  correctness — it surfaces gross breakage cheaply on seed data. Scored by
  `utils/evals/scorers/completion.py` — primary-flow only; the full trajectory is the Traces tier's job:
- **Task success rate** (rigorous, final phase): of completed tasks, the fraction that achieved the goal — the
  **hybrid** judgement below.

```python
# utils/evals/scorers/completion.py — _FALLBACK_MESSAGE imported from backend.modules.pex (canonical)
FALLBACKS = (_CRASH_FALLBACK, _FALLBACK_MESSAGE, '(turn timed out)')

def is_completed(result:dict, expected_flow:str) -> tuple[bool, str]:
    msg = result['message']
    if msg in FALLBACKS:                              return False, f'fallback: {msg[:40]!r}'
    if not msg.strip():                               return False, 'empty reply'
    if result['artifact']['origin'] != expected_flow: return False, 'wrong flow'   # origin = flow.name()
    return True, 'ok'
```

**Parity (3-axis):**
1. **End-state DB** — structural facts exact (title, status progression, section order, outline shape, section
   content). LLM prose presence-only. **HARD gate.**
2. **Grounding** — the `grounding` block / active post matches the oracle every turn. **HARD gate.**
3. **LLM judge** — utterance task-adequacy (the rubric below). Borderline verdicts tolerated.

**Judge rubric:** five-level (Perfect/Great/Good/Adequate/Poor). Two faithfulness checks ride alongside and are
**hard fails**: **grounding faithfulness** (reply describes the actual persisted state) and **no-overclaim**
(no claiming work that never persisted). Simple cases use rule-based value matching; complex cases use a judge
call (stronger model than the agent, to avoid self-grading).

Gates: end-state / grounding parity — **any break (hard)**; rubric mean — **> 0.5 level drop**; mean latency —
**> 20% increase**.

---

## Metrics & regression gates (summary)

| Metric | Level | Threshold | Run tier |
|---|---|---|---|
| Contract tests + lints | Tests | any failure | commit |
| Flow-detection accuracy | Tests | > 2% drop | nightly + on NLU change |
| Intent / slot / entity accuracy | Tests | baseline-diff | nightly |
| Trajectory (full workflow) | Traces | > 3% drop | nightly + on policy change |
| Robustness pass rate | Traces | any drop | nightly |
| Task completion rate | Evals | absolute target 0.90, then diff | nightly |
| End-state / grounding parity | Evals | any break (hard) | pre-release |
| Task success rate / rubric mean | Evals | > 0.5 level drop | pre-release |
| Mean latency | Evals | > 20% increase | pre-release |

Triggers (per spec): prompt-template change, ontology/config change, policy code change, or manual run.

**Gate model (folded baseline, red-green).** Each metric is one self-describing record in a single
`baselines/<level>.json` per level — no separate `metrics.json`. A record folds the hand-set intent
(`target`, `direction`, `max_drop`, `expected_fail`) with the machine-written measurement (`value`,
`commit`, `date`):

```jsonc
// utils/evals/baselines/evals.json
{ "completion_rate": {
    "target": 0.90, "direction": "higher", "expected_fail": true,   // hand-set intent
    "value": null,  "commit": null,        "date": null } }          // written only by `run_evals --record`
```

`gates.py` grades each metric in order **expected_fail → absolute target → regression diff**: `expected_fail:
true` is xfail (known-red, never breaks the gate); else a set-but-unmet `target` → red; else `value` null but
a target exists → green (the first red→green); else diff `value` by `max_drop`. `run_evals.py --record` is the
only writer of `value/commit/date` and never touches the intent keys (the care-point of the folded model — a
read-modify-write). *(Alternatives rejected: a separate hand-edited `metrics.json` intent file — needs a
cross-file key-sync lint; a bare `xfail.txt` — no absolute target, so the first red→green can't be expressed.)*

---

## Phased roadmap

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done. (We are at the **plan** stage — nothing built yet.)

### Phase 1 — task **completion** (coarse Eval on seed data)  · `[~]`
- **Goal:** a fast, cheap "does the whole agent run end-to-end and do something" signal on the new 16-flow
  architecture — before investing in granular accuracy or traces.
- **Spine — BUILT:** `utils/evaluation_suite/scoring.py` (`is_completed` + the folded-baseline gate `grade`),
  the per-tier baseline (`_traces/traces.json`, `_evals/evals.json`), the corpus at `datasets/train.jsonl`,
  the runners `_traces/run_traces.py` and `_evals/run_evals.py`, and the gate tests in `_tests/pex_unit_tests.py`.
  Was red (import error) → green; xfail keeps the commit gate green until the feature clears `target`.
- **Remaining:** `synthesize.py` (seed scenarios + labels across 7 intents / 16 flows; Train bulk + Dev anchor);
  expand from 1 anchor to per-flow coverage; record the completion baseline and flip `expected_fail` off once
  the rate clears `target`. No oracle/judge yet.
- **Depends on:** nothing structural (live agent + seed data).
- **Verify:** completion-rate baseline recorded; gross breakages (dead flows, crashes, fallbacks) surfaced.

### Phase 2 — Model Unit Tests (classification accuracy)  · `[ ]`
- **Goal:** restore meaningful per-decision accuracy on the 16-flow catalog (today's number is meaningless).
- **Deliverable:** `model_cases.json` (**1024** flow + **512** slot examples; synthesized Train + Dev anchor, leakage-guarded); `run_evals.py --level tests`
  with intent/flow/slot/entity accuracy + confidence calibration + ensemble agreement; thresholds wired. Add
  the missing contract-test slot/entity assertions. Rewrite `evaluation_guidelines.md` to the NLU→PEX (no RES)
  pipeline.
- **Depends on:** Phase 1's synthesizer.
- **Verify:** flow-detection accuracy ≥ threshold; baselines recorded; contract tests stay green.

### Phase 3 — Observability Traces (the regression net)  · `[ ]`
- **Goal:** lock correct behavior into a deterministic regression net — "use the traces as ground truth once
  things work."
- **Deliverable:** re-record **256 gold trajectories from 64 conversations** (synthesized scenario → live run →
  approve); cached-vote record/replay; the tolerance engine reading `tolerance_rules.md`; `run_evals.py
  --level traces` with the 4 scoring modes; resolve the two approval TODOs (below). Discards the outdated traces.
- **Depends on:** Phases 1–2 (agent behaving correctly); the cached-vote mechanism.
- **Verify:** every recorded trajectory replays green at current behavior (establishes the baseline the
  behavioral steps must hold).

### Phase 4 — task **success** (rigorous Eval) + adversarial robustness  · `[ ]`
- **Goal:** the north-star success metric + robustness.
- **Deliverable:** record end-state oracles; re-baseline the 3-axis parity oracle (resolves **E8**); LLM judge
  (5-level rubric + faithfulness/no-overclaim hard checks); task-success-rate metric; temp-0 + 2-of-3 stability;
  the adversarial probe suite; wire all gates into the tiered cadence.
- **Depends on:** Phases 1–3.
- **Verify:** success-rate + robustness-pass-rate baselines; the full gate table is enforced at its tiers.

**Cross-cutting (built incrementally):** the report/baseline/`gates.py` plumbing (skeleton in P1, filled per
level), the tiered run cadence, and the Langfuse seam (no-op shim throughout; turned on in a later, separate
step once the internal harness is trusted).

---

## New surface / approvals

- All eval tooling lives under `assistants/Hugo/utils/{tests,traces,evals}/` (restructured; see the Harness
  layout + Layout rationale above). This is **spec-defined eval tooling** (`evaluation.md`), **not a new agent
  concept** — no new-concept approval needed.
- The synthesizer and the judge are LLM-callers; they **reuse the existing `PromptEngineer` + model-resolution**
  — no new agent component, no new dialogue/belief concept.
- **Charlie/Hugo cwd gotcha:** run pytest and the CLI harness with cwd + `sys.path[0]` set to the Hugo dir, or
  `import backend` silently resolves to the wrong assistant.

## Relationship to the master plan

This rewrites Round 1 to cover the whole eval system and consolidates the eval items from Round 6 (E8 parity
oracle). It is still the early enabler that gates **Round 3** (the NLU intent rework): **the Observability
Traces phase must be green before that behavioral change lands.** The completion Eval and Model Unit Tests
phases can proceed in parallel with Round 4 (MEM) and Round 2 (PEX).


# Round 1 — The 64-conversation seed

The hand-generated core of the Train set (`round_1_evals.md` → Dataset coverage funnel). **64 = 4 personas ×
8 use cases × 2 topic clusters.** Uniqueness comes from three orthogonal axes: the **persona** sets tone +
ambiguity, the **use case** sets the 4-turn flow sequence, the **topic** sets the subject. Each conversation
is **7 turns** (4 user + 3 agent) in the `test_cases.json` shape (`convo_id`, `available_data`, `turns[]` with
`labels{intent,flow,dax}`, `slots`, `expected_tools`, `rubric`).

Scenario ID = **`P{1-4}.U{1-8}.T{1-2}`** (persona · use case · topic).

---

## Axis 1 — Personas (tone + focus)

| # | Persona | Tone | Ambiguity |
|---|---|---|---|
| **P1** | Clear sense of what they want | warm, **conversational**, full sentences | low |
| **P2** | Clear sense of what they want | **terse, business** imperative; few words | low |
| **P3** | *Some* sense — **needs hand-holding** | hesitant, vague, asks the agent to decide | **high** — the ambiguity persona |
| **P4** | Good sense but **absent-minded** | fluent but **changes direction** mid-conversation | medium (mid-task switches) |

**P3 across all 8 use cases × 2 topics = 16** — exactly the funnel's *ambiguity-recovery core*. P4 adds a
direction-change on one turn; P1/P2 are the clean happy paths in two tones.

## Axis 2 — Use cases (the 4-turn flow sequence)

The use case names the intents; the **proposed flow per turn** is below (to confirm — flows are from the
16-flow catalog). `[Clarify]` = an intentionally ambiguous user turn the agent must recognize and recover from
(NLU-only, no flow).

| # | Use case | Turn 1 | Turn 2 | Turn 3 | Turn 4 |
|---|---|---|---|---|---|
| **U1** | Draft → Draft → Revise → Revise (standard blogging) | `outline` `{002}` | `compose` `{3AD}` | `write` `{003}` | `audit` `{13A}` |
| **U2** | Draft → Revise×3 (editing-heavy) | `compose` | `rework` | `audit` | `propose` |
| **U3** | Research → Draft → Revise → Publish (basic E2E) | `find` `{001}` | `outline` `{002}` | `write` `{003}` | `release` `{004}` |
| **U4** | Draft + Converse | `chat` | `brainstorm` | `outline` | `chat` |
| **U5** | Research + Draft + **Clarify** | `browse` | `[Clarify]` | `outline` | `compose` |
| **U6** | **Plan** → Draft phase | `Plan` | `outline` | `compose` | `refine` |
| **U7** | **Plan** → Research phase | `Plan` | `find` | `summarize` | `compare` |
| **U8** | Draft + Revise + **Clarify** | `compose` | `[Clarify]` | `rework` | `audit` |

Clarify appears explicitly in **U5 + U8** (all personas) and pervasively under **P3**.

**Parked (not in the seed):** the alternate **Research → Research → Draft → Draft** opener
(`browse → summarize → outline → compose`) — kept for a later expansion, not one of the 8 seed use cases.

## Axis 3 — Topics (2 clusters, sub-topic per cell)

- **T1 — Tech / AI-infra:** Observability, OpenTelemetry, Traces, LLM Evals, Red-teaming, Security
- **T2 — History of electricity:** Edison, Lightbulb, Bringing Electricity to Homes, Electric vs Diesel Cars,
  Street Lamps

One sub-topic is assigned per **(use case × cluster)** so all 4 personas of a cell share a subject (tone
varies, topic doesn't). Proposed assignment:

| Use case | T1 sub-topic | T2 sub-topic |
|---|---|---|
| U1 | Observability | Edison |
| U2 | OpenTelemetry | The Lightbulb |
| U3 | LLM Evals | Bringing Electricity to Homes |
| U4 | Traces | Street Lamps |
| U5 | Red-teaming | Electric vs Diesel Cars |
| U6 | Security | Edison's workshop |
| U7 | LLM Evals (compare frameworks) | The Lightbulb (rival inventors) |
| U8 | Observability dashboards | Electric vs Diesel Cars |

---

## Per-scenario format

Each scenario is one block; user turns carry the full label set, agent turns carry a response gist. This maps
1:1 to `test_cases.json` (a user turn → `{utterance, labels, slots, expected_tools, rubric}`; an agent turn →
`{role: agent, utterance}`). `completion` notes the per-turn expected primary flow and any ambiguity recovery.

---

## Exemplars (format anchors)

### P1.U1.T1 — clear+conversational × standard blogging × Observability  *(happy path)*

A fresh post built end-to-end: outline → compose → revise → audit. No seeded data.

1. **User → `outline` ({002}):** "Hey! I want to write a post on observability for LLM apps. Let's start with
   an outline — intro, traces vs logs, instrumenting with OpenTelemetry, and takeaways."  · slots
   `{source: {post: "Observability for LLM Apps"}, sections: [...]}` · tools `[generate_outline]`
2. **Agent:** "Outline ready: 1) Why observability matters 2) Traces vs logs 3) Instrumenting with
   OpenTelemetry 4) Takeaways."
3. **User → `compose` ({3AD}):** "Love it — turn that into a full first draft."  · slots
   `{source: {post: "Observability for LLM Apps"}}` · tools `[convert_to_prose]`
4. **Agent:** "Drafted all four sections — the instrumenting one came out a bit thin."
5. **User → `write` ({003}, Revise):** "Yeah, flesh out the instrumenting section with a concrete
   OpenTelemetry tracing example."  · slots `{source: {post: "…", sec: "Instrumenting with OpenTelemetry"}}` ·
   tools `[write_text]`
6. **Agent:** "Expanded it with a span-instrumentation example."
7. **User → `audit` ({13A}, Revise):** "Nice. Do a quick quality pass on the whole post — readability and any
   gaps?"  · slots `{source: {post: "Observability for LLM Apps"}}` · tools `[editor_review]`

*completion:* primary flows `outline → compose → write → audit`; no ambiguity; all four activate.

### P3.U5.T1 — hand-holding × Research+Draft+Clarify × Red-teaming  *(ambiguity-recovery core)*

`available_data`: notes `{Prompt injection basics, Red-team playbook}`.

1. **User → `browse`:** "I think I want to write about… security stuff for AI? Maybe red-teaming? Can you see
   what I have?"  · slots `{query: "AI security"}` · tools `[search_notes]`
2. **Agent:** "I found 2 related notes: *Prompt injection basics* and *Red-team playbook*. Are you leaning
   toward red-teaming specifically, or AI security broadly?"
3. **User → `[Clarify]`** (ambiguous draft request): "Let's just draft it."  → **agent must recognize the
   ambiguity** (which topic? what post?) and ask, not guess.  · expected: `handle_ambiguity(declare)`
4. **Agent (clarify):** "Happy to start — should the post focus on **red-teaming** specifically, titled
   *A Red-Team Playbook for LLM Apps*?"
5. **User → `outline`** (resolves): "Yes, red-teaming, that title's good. Outline it."  · slots
   `{source: {post: "A Red-Team Playbook for LLM Apps"}}` · tools `[generate_outline]`
6. **Agent:** "Outline: 1) Threat model 2) Attack catalog 3) Running a red-team 4) Fixing what you find."
7. **User → `compose`** (still leans on the agent): "Okay um… write the first part? Whatever you think is
   best."  · slots `{source: {post: "A Red-Team Playbook for LLM Apps", sec: "Threat model"}}` · tools
   `[convert_to_prose]`

*completion:* primary flows `browse → (clarify) → outline → compose`; **the agent recovers from the turn-2
ambiguity by asking a concrete question; recovery completes at turn 5.** This is what the ambiguity core tests.

---

## How we fill the rest (iteration plan)

1. **Confirm the framework** — the U1–U8 flow sequences, the sub-topic grid, and the format above.
2. **Fill by use case, both topics, all 4 personas** (8 conversations per use case) — so each batch reuses one
   flow sequence and we just re-voice it across personas/topics. U1 and U5 are seeded above (P1/P3); we add the
   other personas + T2.
3. **Convert to `test_cases.json`** under `utils/evals/datasets/scenarios/` once a batch is locked.
4. **Reconcile the funnel labels** in `round_1_evals.md`: the ambiguity core = P3 × 8 × 2 = 16 ✓; the E2E-32 =
   the two most-collaborative personas × 8 × 2 (the funnel currently says "× 4 topics" — should read "× 2").

Progress: **2 / 64** drafted (P1.U1.T1, P3.U5.T1).
