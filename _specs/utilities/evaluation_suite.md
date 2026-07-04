# Evaluation Suite

Engineering utility for evaluating the agent at a micro and macro level. Lives outside the agent; a universal consumer of
signals from every module and component.

**Trust framing.** Evaluation exists to earn the confidence to deploy the agent to customers. That trust is
correlated with — but distinct from — single-model accuracy. Evals must be intuitive, trustworthy, and easy
to extend to new scenarios. The organizing principle is a **ladder**: cheap, static, deterministic checks at
the bottom; expensive, full-loop, judged checks at the top. Each level gates the next — a change must clear
the lower rungs before the higher ones are worth running.

> **Naming.** The three levels are **Model Unit Tests**, **Observability Traces**, and **E2E Agent
> Evals** (shorthand **Tests**, **Traces**, **Evals**). We do **not** use `L1/L2/L3` codes — they collide
> with the Memory Tiers. The full word 'evaluations' references the comprehensive suite which includes all
three levels. The shorthand 'evals' is more commonly reserved for the level regarding E2E Agent Evals.

## The Evaluation Ladder

Each level widens the scope. **Tests** check a **single decision** in isolation. **Traces** check a **series
of decisions** where **order matters** — often a tool-call trajectory. **Evals** take the **broad end-to-end view**:
less concerned with the specifics of what happened, and instead focused on the **final result**.

| Level | Stage | LLM | Proves | Speed |
|---|---|---|---|---|
| **Model Unit Tests** | Contract & property | none | components honor their contracts in isolation | ms |
| | Component isolation | one call | a single module does its job (detect, fill, write) | sec |
| **Observability Traces** | Trace replay | deterministic | the agent reproduces approved tool-call trajectories within tolerance | sec |
| | Adversarial / robustness | varies | the agent recovers from ambiguity, bad input, and injection | varies |
| **E2E Agent Evals** | Scenario / parity | full loop | end-to-end behavior matches the oracle on three axes | min |
| | Quality / judge | judge | the spoken output is good (rubric, faithfulness, no overclaim) | min |

**One entry point.** `utils/evaluation_suite/run_suite.py` runs any combination of levels via argparse:
`--tests [MODULES]` (deterministic, free), `--model [MODULES]` (probabilistic, paid), `--traces`, `--evals`,
`--all`. `MODULES` is an optional comma list (`nlu,pex,mem`) or `all` — so a level can be run for one module
(`--tests nlu`, `--model nlu`) or all. **With no flags it runs only the free deterministic Model Unit Tests**
— no model calls, no cost; every probabilistic / live level is opt-in. The deterministic tests are found by
naming the `*_unit_tests.py` files **explicitly** (no `python_files` pattern, no directory scan). Each level
runs as its own subprocess; the suite exits non-zero if any requested level fails.

**Layout — everything lives under `utils/evaluation_suite/`.** Each tier folder holds only its runner; the
shared infrastructure sits alongside them.

| Path | Role |
|---|---|
| `run_suite.py` | the single entry point (drives all three tiers) |
| `_tests/` | Tests tier — `{nlu,pex,mem}_unit_tests.py` (deterministic) + `model_tests.py` (probabilistic) + `conftest.py` |
| `_traces/` | Traces tier — `run_traces.py` + `traces.json` (folded baseline) + `tolerance_rules.md` |
| `_evals/` | Evals tier — `run_evals.py` (the 7 criteria) |
| `datasets/` | the corpus as three JSONL splits: `train.jsonl` (96 labelled conversations, one JSON per line) + `dev.jsonl` / `test.jsonl` (placeholders) — pure data |
| `harness.py` | shared: build/seed agents + load/`sample()` the corpus splits |
| `scoring.py` | shared: the scorers (completion, tools, response) + the red-green gate |
| `_snapshot.py` | shared: structural snapshot assertion |
| `review_app/` | the seed-scenario review UI (`server.py` + `index.html` + `app.js`) + its `feedback/` verdicts |

**Train / dev / test.** `train.jsonl` holds all 96 labelled conversations (one JSON per line); `dev.jsonl`
and `test.jsonl` are placeholders for now. The **dev set is a fresh random ~8 drawn from train per build**
(`harness.sample`) — not a fixed list — so each iteration judges against a new slice; pass feature-relevant
ids with `--ids` to override, or `--all` for the whole train split (a release gate). One shared model,
offline: `scoring.semantic_similarity` and the (designed) business-context vector retrieval both use
`backend/utilities/embeddings.py` (`all-MiniLM-L6-v2`), so nothing extra is downloaded.

```
python utils/evaluation_suite/run_suite.py                      # free deterministic tests, all modules
python utils/evaluation_suite/run_suite.py --tests nlu --model nlu
python utils/evaluation_suite/_traces/run_traces.py --ids B01.C01,B02.C04   # traces on a chosen set
python utils/evaluation_suite/_evals/run_evals.py               # 7 criteria, embedding response, sample of 8
python utils/evaluation_suite/_evals/run_evals.py --judge-response          # response via the LLM judge instead
```

> **Out of scope — production feedback.** Online per-session metrics, explicit/implicit user-feedback
> collection, prompt-version attribution, A/B infrastructure, and RFT signal collection are **not built
> here** — we adopt a dedicated library/service for them. The agent still emits structured signals; their
> runtime consumption is the library's concern, not this spec's.

---

## Model Unit Tests

The Model Unit Tests are **three parts — [NLU](../modules/nlu.md), [PEX](../modules/pex.md),
[MEM](../modules/mem.md)** — and each part splits into **two halves**: **(a) deterministic** code (traditional
unit tests, no model call) and **(b) probabilistic** model predictions (one model call per decision). On disk:

- **Deterministic** — one file per module: `nlu_unit_tests.py`, `pex_unit_tests.py`, `mem_unit_tests.py`. Each
  **stores its checks inline** and also holds that module's owned component/service/infra tests — NLU: Dialogue
  State + Session Scratchpad; PEX: Task Artifact, FlowStack, the domain services, snapshots, the completion
  gate, and the skill/schema lints; MEM: Context Coordinator (L1), sessions, Business Context (L3). Free tier
  (`pytest -m "not llm"`), millisecond-fast.
- **Probabilistic** — one file for all three modules: `model_tests.py`, selected by
  `--module nlu,pex,mem,all`. It **stores no cases inline**: the labels already live in the eval corpus
  (`utils/evaluation_suite/datasets/train.jsonl`), so it loads that data and scores each module's single-decision
  predictions (one model call per decision, no full loop — the trajectory view is the Traces tier's job).
  Paid, so not in the default free run. NLU flow-detection accuracy is scored today; PEX/MEM scoring is declared
  with its scope still to be defined.

`conftest.py` holds the shared fixtures. The prune bar: keep tests that check **actual outputs vs. expected**
(and that catch real drift); drop tests that only exercise a function's **signature / interface**. The two
stages below are those two halves.

### Contract & property (no LLM)

The free-tier suite — must stay green throughout development. `pytest` + Hypothesis, no model calls,
millisecond-fast. Covers component **contracts** and pure logic: the Dialogue State belief tools
(`classify_intent` / `detect_flow` / `fill_slots` / `complete_flow`) and their grounding
validation, Flow Stack reload (in-memory vs. file-backed in lockstep), slot typing, the Task Artifact
`Part` oneof, `state.json` round-trips, scratchpad writer-stamping, and completion-record shape. This is the
gate every other level assumes; if these contract tests are red, nothing above runs.

### Component isolation (one LLM call)

Each module exercised alone with a real model call but **no full loop** — fast enough to tune prompts before
paying for E2E. Covers:
- **[NLU](../modules/nlu.md)** — flow-detection accuracy (the sharpest single signal: detect the right flow
  from the 16-flow catalog — more specific than intent, less brittle than slots), slot-filling, entity
  extraction, and `med`-tier ensemble agreement.
- **[PEX](../modules/pex.md)** skill execution — a single flow's skill composes its reply directly from a
  fixed artifact (no template fill, no naturalization step).
- **[NLU](../modules/nlu.md)** Dialogue State tools — op contracts against a real state file.

Model-accuracy testing lives here too: when a prompt's exemplars change, evaluate with train/dev/test splits
(exemplars = train, scenarios = dev, held-out = test) scoped to that one component.

## Observability Traces

### Trace replay (deterministic + tolerance)

Replay the **human-approved tool-call trajectories** — the trace dev set (the approved trajectories +
`tolerance_rules.md`). The recorder parses a session's `messages.jsonl` + `scratchpad.jsonl` into per-turn
`(tool, key_args, ok)` sequences, activated flows, and completion records; replay compares against the
approved trace, allowing only the documented tolerances. Deterministic and cheap — this is trajectory
correctness made reproducible.

Because flow detection is a multi-voter ensemble, the recorder also captures **each voter's output**; replay
feeds those cached votes back instead of calling the model (record-once / replay-many, temp-0), so detection
is deterministic at replay. Live ensembles run only at the **scenario / parity** stage (E2E Agent Evaluations),
where the judge axis tolerates vote-to-vote drift.

**Trajectory scoring modes** (for the tool sequence within a flow):

| Mode | Measures | Example (4-tool path, one out of order) |
|---|---|---|
| Partial path | correct tools in sequence until first error | 50% |
| Full path | exact sequence, all-or-nothing | 0% |
| Path nodes | correct tools regardless of order | 100% |
| Full workflow | full path **and** correct flow | 0% |

Default to **full workflow** (strictest); report all four for diagnostics.

### Operational tool scoring (implemented)

The live Traces runner (`utils/evaluation_suite/_traces/run_traces.py`) scores each user turn's tool calls against
the following agent turn's `actions` with a **token-level Levenshtein similarity** — `1 − editDistance / max(len)`
between the dispatched domain tools and the expected list (`utils/evaluation_suite/scoring.py`). It is **partial credit against
a threshold** (target ~0.9), not strict pass/fail: a new feature passes once similarity clears the bar, so
tool-name drift shows up as a graded red rather than a hard break. One live pass over the corpus emits **two**
metrics from a single set of model calls — `completion_rate` and `tool_match_rate` (mean similarity). Only
real domain tools count: dispatched names are filtered to the keys of `schemas/tools.yaml`, so orchestration
plumbing is ignored. **Declaring ambiguity is not a tool** — NLU owns the Ambiguity Handler and PEX only
declares it — so `handle_ambiguity` never appears in `actions`; ambiguity is scored separately from the
user turn's `ambiguity` level, not from the tool trace.

### Adversarial / robustness

Targeted probes of the failure surface — each asserts *bounded, graceful* recovery, not a happy path:
- Ambiguity declaration and recovery (`handle_ambiguity`, [NLU `contemplate`](../modules/nlu.md) re-route).
- Corrective-tool-error loops — a malformed belief-tool call, unknown flow, unknown slot, grounding violation — come
  back as `{_success: False, ...}` and the loop retries within the consecutive-failure cap.
- Input guards — reserved-keyword / injection rejection, length and repeat guards.
- The lethal-trifecta approval gate; the round budget and `_final_emit` wrap-up.

## E2E Agent Evals

### Scenario / parity (full loop, three axes)

Multi-turn scenarios run through the **full orchestrator loop** and compared against oracle fixtures on three
axes:

1. **End-state DB** — structural facts exact (title, status progression, section order, outline shape,
   section content); LLM prose presence-only.
2. **Grounding** — the `grounding` block / `active_post` matches the oracle on every turn.
3. **LLM judge** — utterance task-adequacy (the judge rubric below).

The **parity harness** (oracle capture + 3-axis comparator) is the tooling. Hard gates: crashes, end-state
mismatches, grounding breaks. Borderline judge verdicts are tolerated — independently generated prose
legitimately diverges turn to turn.

The two headline metrics are **task completion rate** (ran end-to-end to a final answer, no crash / give-up /
fallback) and **task success rate** (of completed tasks, the fraction that achieved the goal — end-state match
plus a passing judge verdict).

### The 7 Eval criteria

All **seven are wired** in `utils/evaluation_suite/_evals/run_evals.py` — the ground truth already lives in the
96-example corpus, so most are deterministic. **Only criterion 3 needs a model** (and it defaults to a cheap
offline embedding, not an LLM), so scoring adds no meaningful cost on top of running the agent itself:

1. **Task completion** — did the turn reach the end in the right mode? `is_completed` (artifact origin == label flow).
2. **Task correctness (actions)** — did the agent take the right actions? **Deterministic**: per-turn tool-match
   (Levenshtein similarity vs the label's `expected_tools`), aggregated over the conversation.
3. **Task success (response)** — is the reply close to the ground-truth agent turn? **Default: offline embedding
   similarity** (cosine over the shared `all-MiniLM-L6-v2`, no API); `--judge-response` swaps in an LLM-as-judge
   that also sees the conversation lead-up. This is the only criterion that costs a model call, and it is opt-out.
4. **Task success (state)** — did NLU's belief detect the labelled flow? **Deterministic**:
   `pred_flows[0].flow_name == labels.stack[0].flow`.
5. **Latency** — **ideal** targets we **measure** but do **not** gate on: time-to-first-token **≤ 5 s**,
   full turn **≤ 10 s**, whole conversation **≤ 60 s**, the 8-scenario gate **≤ 10 min**. Track distance to
   these goals rather than pass/fail them.
6. **Ambiguity** — did the agent declare ambiguity when the label says the turn is ambiguous (no false positives)?
   **Deterministic** from the per-turn `ambiguity` level.
7. **Planning** — did multi-flow plan turns complete? **Deterministic** from the multi-item plan stacks.

### Quality / judge rubrics

LLM-as-judge on the spoken output, scored against a five-level rubric:

| Score | Criteria |
|---|---|
| Perfect | answers completely, correct values, right tone |
| Great | answers it, minor omissions or style |
| Good | substantively correct, some gaps |
| Adequate | partial, notable issues |
| Poor | wrong, hallucinated, or off-request |

Simple cases use rule-based value-matching (`target in response`). Complex cases use a judge call. Two
faithfulness checks ride alongside the rubric and are **hard** fails: **grounding faithfulness** (does the
reply describe the actual persisted state?) and **no-overclaim** (does it claim work that never persisted?).

---

## Test-case format

Multi-turn JSON. Each case: `convo_id`, `domain`, `available_data`, `turns`. User turns carry the labels:
`labels` (intent + the `{flow, dax}` stack — the dialog acts), `slots`, and the `ambiguity` level. Each agent
turn carries `actions` (the ordered domain tools that complete the preceding user request — Observability
Traces / E2E Agent Evaluations) and `utterance` (the expected response — the judge rubric). A conversation
ends with a closing agent turn holding `actions` only, until a future batch authors its ground-truth reply.

## Regression gates

| Metric | Level | Threshold |
|---|---|---|
| Flow-detection accuracy | Model Unit Tests | > 2% drop |
| Trajectory (full workflow) | Observability Traces | > 3% drop |
| Tool-match rate (Levenshtein) | Observability Traces | below 0.9 threshold |
| Robustness pass rate | Observability Traces | any drop |
| Task completion rate | E2E Agent Evaluations | absolute 0.90, then diff |
| End-state / grounding parity | E2E Agent Evaluations | any break (hard) |
| Output rubric (mean) | E2E Agent Evaluations | > 0.5 level drop |
| Ambiguity accuracy (declare when present, no false positives) | E2E Agent Evaluations | any drop |
| Planning appropriateness (plan multi-flow, no over-stacking) | E2E Agent Evaluations | any drop |
| Latency (TTFT ≤5s · turn ≤10s · convo ≤60s · 8-scenario ≤10min) | E2E Agent Evaluations | measure-only, non-gating |
| Mean latency | E2E Agent Evaluations | > 20% increase |

Triggers: prompt-template change, ontology/config change, policy code change, or manual run.
