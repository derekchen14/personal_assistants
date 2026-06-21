# Step 1 — Evaluation System (the full plan)

Maps to **Master Plan · Step 1**, but **rescoped**: Step 1 was originally just the trace-replay runner. It is
now the plan for the **whole evaluation system** — the three eval levels, the harness, the data pipeline, the
metrics, and the phased roadmap. It absorbs the eval items that were parked in Step 6 (parity oracle
re-baseline, E8). It remains the **early enabler** that gates the risky behavioral steps — the **Traces** phase
must be green before Step 3's NLU intent rework.

This is a **living document**: the roadmap section carries status checkboxes that we update as phases land.

> **Naming.** We do **not** use `L1/L2/L3` (those collide with the Memory Tiers). The three levels are
> **Model Unit Tests**, **Observability Traces**, and **E2E Agent Evaluations** — shorthand **Tests**,
> **Traces**, **Evals**. Sub-parts are named descriptively, never lettered.

Spec: `_specs/utilities/evaluation.md` (the eval ladder + regression-gate table — note the spec still uses the
old letter codes; updating it to these names is a follow-up).
Operational guide (currently **stale** — documents the dead NLU→PEX→RES pipeline):
`assistants/Hugo/utils/tests/evaluation_guidelines.md` — rewrite is part of the Tests phase.

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

## Decision log (locked with Derek, 2026-06-21)

1. **Harness = pytest + custom CLI + Langfuse (Langfuse deferred).** Pytest owns the deterministic contracts +
   lints. A purpose-built CLI harness owns the accuracy tests, the traces, and the agent evals (scoring,
   baseline-diff gates, reports). **Langfuse** is the future observability/dashboard/run-history layer — a
   **seam is designed now, integration is deferred**; we do simpler internal verification first.
2. **Data = LLM-synthesized seed now; recorded traces as ground truth later.** The current
   traces/snapshots/oracle are **outdated** (dead 48-flow taxonomy + retired `detect_and_fill`) and are
   **discarded**, not migrated. Bootstrap on LLM-synthesized seed data (hand-curated **anchor** set + synthesized
   **bulk**). Once the agent behaves correctly, **re-record gold traces from the working agent** and use them as
   the regression net (the Traces phase).
3. **Success = hybrid metric.** Completion = ran to a final answer without crash / give-up / fallback. Success =
   deterministic end-state facts match the oracle (**HARD gate**) **and** an LLM-judge rubric passes (**soft**).
4. **Run cadence = tiered.** Contract tests + lints gate every commit; accuracy + trace evals run nightly and on
   relevant prompt/ontology/policy changes; full E2E is manual / pre-release.
5. **Trace determinism = cached-vote replay.** Record each ensemble voter once at temp-0; replay feeds cached
   votes back so flow detection is deterministic and the gate never re-rolls the model.
6. **Adversarial robustness = part of Observability Traces, designed now** (built in the final phase), not
   deferred to a separate plan.
7. **Synthesis trust = anchor manual, bulk synthesized.** Hand-curate a small held-out anchor/test set (no
   exemplar leakage); LLM-synthesize the larger dev set with human approval on labels + recorded gold.
8. **Phasing** (the order we build): **P1** task *completion* (coarse Eval, on seed data) → **P2** Model Unit
   Tests → **P3** Observability Traces (regression net) → **P4** task *success* (rigorous Eval) + adversarial
   robustness.

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
| `unit_tests.py` (~380 service/contract tests) | Tests | ✅ solid, mostly architecture-agnostic | Keep; add slot/entity assertions |
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

## Target architecture

### Harness layout

```
assistants/Hugo/utils/tests/        # pytest home — deterministic contracts + lints (unchanged location)
  unit_tests.py                      # service/contract                    (keep)
  test_artifacts.py                  # static lints                        (keep)
  test_nlu_module.py                 # NLU belief contracts                (keep)
  conftest.py                        # markers + fixtures                  (extend)
  eval/                              # NEW — the custom CLI harness (accuracy / traces / agent evals)
    run_evals.py                     #   single entrypoint: --level {tests,traces,evals,adversarial} --tier ...
    synthesize.py                    #   LLM dataset generator (seed scenarios + labels)
    datasets/
      model_cases.json               #   classification gold (anchor + synthesized)
      scenarios/                     #   multi-turn agent scenarios (anchor + synthesized)
      traces/                        #   recorded gold trajectories + cached votes (P3)
      oracles/                       #   end-state oracles (recorded, P4)
    scorers/                         #   exact / tolerance / endstate / judge
    report/                          #   per-run artifacts (json + md) + run history
    baselines/                       #   committed baseline metrics for regression-diff
    gates.py                         #   thresholds → process exit code
    langfuse_sink.py                 #   # designed-not-built — Langfuse trace/score export seam
  parity/                            # reuse the existing recorder + 3-axis comparator
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
2. human approve labels     anchor set hand-written; bulk synthesized labels reviewed before use
3. run through live Hugo     execute the approved scenario end-to-end on current code
4. human approve gold        approve the recorded tool-trajectory (Traces) and end-state oracle (Evals)
5. freeze                    recorded gold becomes the regression ground truth (cached votes for traces)
```

- **Why record gold instead of synthesizing it:** a synthesized *label* is fine, but a synthesized *trajectory*
  or *end-state* won't reliably match live tool APIs. Gold trajectories/oracles must be **recorded from real
  behavior and approved** — this is exactly Derek's "use the traces as ground truth once things work."
- **Leakage guard:** prompt exemplars are the *training* set. The **anchor/test** set is held out and must not
  reuse exemplar topics (e.g. the Kitty Hawk anchor must never appear in a prompt exemplar). Synthesized *dev*
  cases may rotate freely.

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

Use train/dev/test splits scoped to the component (exemplars = train, synthesized scenarios = dev, anchor =
held-out test). **Volumes (locked):** 16 dev cases/flow (256 total, Opus-synthesized) + 4 anchor cases/flow
(64 total, hand-written, no exemplar leakage). Reported as percentages with a baseline; **not** binary pytest
asserts.

---

## Observability Traces

### Trace replay (deterministic + tolerance)

Replay human-approved tool-call trajectories. The recorder parses a session into per-turn `(tool, key_args,
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
  correctness — it surfaces gross breakage cheaply on seed data.
- **Task success rate** (rigorous, final phase): of completed tasks, the fraction that achieved the goal — the
  **hybrid** judgement below.

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
| Task completion rate | Evals | baseline-diff | nightly |
| End-state / grounding parity | Evals | any break (hard) | pre-release |
| Task success rate / rubric mean | Evals | > 0.5 level drop | pre-release |
| Mean latency | Evals | > 20% increase | pre-release |

Triggers (per spec): prompt-template change, ontology/config change, policy code change, or manual run.

---

## Phased roadmap

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done. (We are at the **plan** stage — nothing built yet.)

### Phase 1 — task **completion** (coarse Eval on seed data)  · `[ ]`
- **Goal:** a fast, cheap "does the whole agent run end-to-end and do something" signal on the new 16-flow
  architecture — before investing in granular accuracy or traces.
- **Deliverable:** `synthesize.py` (seed scenarios + labels across 7 intents / 16 flows; anchor + bulk);
  `run_evals.py --level evals --metric completion`; a completion-rate report + baseline. No oracle/judge yet.
- **Depends on:** nothing structural (live agent + seed data).
- **Verify:** completion-rate baseline recorded; gross breakages (dead flows, crashes, fallbacks) surfaced.

### Phase 2 — Model Unit Tests (classification accuracy)  · `[ ]`
- **Goal:** restore meaningful per-decision accuracy on the 16-flow catalog (today's number is meaningless).
- **Deliverable:** `model_cases.json` (synthesized + anchor, leakage-guarded); `run_evals.py --level tests`
  with intent/flow/slot/entity accuracy + confidence calibration + ensemble agreement; thresholds wired. Add
  the missing contract-test slot/entity assertions. Rewrite `evaluation_guidelines.md` to the NLU→PEX (no RES)
  pipeline.
- **Depends on:** Phase 1's synthesizer.
- **Verify:** flow-detection accuracy ≥ threshold; baselines recorded; contract tests stay green.

### Phase 3 — Observability Traces (the regression net)  · `[ ]`
- **Goal:** lock correct behavior into a deterministic regression net — "use the traces as ground truth once
  things work."
- **Deliverable:** re-record gold trajectories from the now-working agent (synthesized scenario → live run →
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

## Open decisions / needs-Derek

- **Synthesis model + volume — DECIDED.** Generator model = **Opus**. Per the powers-of-2 heuristic
  (`style_guide.md § Choosing Quantities`): **16 dev cases/flow (256 total)** synthesized + **4 anchor
  cases/flow (64 total)** hand-written and held out (no exemplar leakage). 16 flows.
- **Two `tolerance_rules.md` rules — DECIDED** (both encode the normative design; the rule activates when its
  step lands, executed at Phase 3 re-recording):
  - **06 ambiguity ask:** a clarification **must** go through `handle_ambiguity(declare)` — bare-text asks fail
    the gate. (Lands with Step 3's ambiguity work.)
  - **07 plan chain:** chained sub-flows **must** be stacked with a shared `plan_id` linkage. (Lands with Step
    5's `plan_id` work.)
- **E8 — parity oracle re-baseline** (folded here from Step 6): re-capture the parity oracle from an approved
  orchestrator run, converged with the recorded-trace model. *Execute in Phase 4.*
- **Langfuse — DECIDED (defer).** Build the no-op `langfuse_sink.py` seam now; do internal verification with
  pytest + the CLI harness first. Integrate Langfuse later (hosted vs self-hosted + data-egress review) once the
  internal harness is trusted. Easy to walk back, so not gating anything.
- **CI provider** for the tiered cadence (no CI today). *Skeleton in Phase 1; the runner is CI-agnostic.*

## New surface / approvals

- All eval tooling lives under `assistants/Hugo/utils/tests/` (new `eval/` package; reuse `parity/`). This is
  **spec-defined eval tooling** (`evaluation.md`), **not a new agent concept** — no new-concept approval needed.
- The synthesizer and the judge are LLM-callers; they **reuse the existing `PromptEngineer` + model-resolution**
  — no new agent component, no new dialogue/belief concept.
- **Charlie/Hugo cwd gotcha:** run pytest and the CLI harness with cwd + `sys.path[0]` set to the Hugo dir, or
  `import backend` silently resolves to the wrong assistant.

## Relationship to the master plan

This rewrites Step 1 to cover the whole eval system and consolidates the eval items from Step 6 (E8 parity
oracle). It is still the early enabler that gates **Step 3** (the NLU intent rework): **the Observability
Traces phase must be green before that behavioral change lands.** The completion Eval and Model Unit Tests
phases can proceed in parallel with Step 2 (MEM) and Step 4 (PEX).
