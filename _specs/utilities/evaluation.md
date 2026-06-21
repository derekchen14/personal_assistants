# Evaluation

Engineering utility for evaluating the agent end-to-end. Lives outside the agent; a universal consumer of
signals from every module and component.

**Trust framing.** Evaluation exists to earn the confidence to deploy the agent to customers. That trust is
correlated with — but distinct from — single-model accuracy. Evals must be intuitive, trustworthy, and easy
to extend to new scenarios. The organizing principle is a **ladder**: cheap, static, deterministic checks at
the bottom; expensive, full-loop, judged checks at the top. Each level gates the next — a change must clear
the lower rungs before the higher ones are worth running.

> **Naming.** The three eval levels are **Model Unit Tests**, **Observability Traces**, and **E2E Agent
> Evaluations** (shorthand **Tests**, **Traces**, **Evals**). We do **not** use `L1/L2/L3` codes — they collide
> with the Memory Tiers. Each level has two stages, named descriptively (never lettered).

## The eval ladder

| Level | Stage | LLM | Proves | Speed |
|---|---|---|---|---|
| **Model Unit Tests** | Contract & property | none | components honor their contracts in isolation | ms |
| | Component isolation | one call | a single module does its job (detect, fill, write) | sec |
| **Observability Traces** | Trace replay | deterministic | the agent reproduces approved tool-call trajectories within tolerance | sec |
| | Adversarial / robustness | varies | the agent recovers from ambiguity, bad input, and injection | varies |
| **E2E Agent Evaluations** | Scenario / parity | full loop | end-to-end behavior matches the oracle on three axes | min |
| | Quality / judge | judge | the spoken output is good (rubric, faithfulness, no overclaim) | min |

> **Out of scope — production feedback.** Online per-session metrics, explicit/implicit user-feedback
> collection, prompt-version attribution, A/B infrastructure, and RFT signal collection are **not built
> here** — we adopt a dedicated library/service for them. The agent still emits structured signals; their
> runtime consumption is the library's concern, not this spec's.

---

## Model Unit Tests

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

### Adversarial / robustness

Targeted probes of the failure surface — each asserts *bounded, graceful* recovery, not a happy path:
- Ambiguity declaration and recovery (`handle_ambiguity`, [NLU `contemplate`](../modules/nlu.md) re-route).
- Corrective-tool-error loops — a malformed belief-tool call, unknown flow, unknown slot, grounding violation — come
  back as `{_success: False, ...}` and the loop retries within the consecutive-failure cap.
- Input guards — reserved-keyword / injection rejection, length and repeat guards.
- The lethal-trifecta approval gate; the round budget and `_final_emit` wrap-up.

## E2E Agent Evaluations

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

Multi-turn JSON. Each case: `convo_id`, `domain`, `available_data`, `turns`. Each agent turn carries
`context` (slots, entities), `actions` (the expected `{flow, tools}` trajectory — Observability Traces / E2E
Agent Evaluations), and `utterance` (the expected response — the judge rubric).

## Regression gates

| Metric | Level | Threshold |
|---|---|---|
| Flow-detection accuracy | Model Unit Tests | > 2% drop |
| Trajectory (full workflow) | Observability Traces | > 3% drop |
| Robustness pass rate | Observability Traces | any drop |
| End-state / grounding parity | E2E Agent Evaluations | any break (hard) |
| Output rubric (mean) | E2E Agent Evaluations | > 0.5 level drop |
| Mean latency | E2E Agent Evaluations | > 20% increase |

Triggers: prompt-template change, ontology/config change, policy code change, or manual run.
