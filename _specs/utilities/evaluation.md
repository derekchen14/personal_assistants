# Evaluation & Feedback

Engineering utility for end-to-end agent evaluation, runtime metrics, and user feedback collection. Lives outside the agent. Universal consumer: collects signals from every module and component in the system.

**Trust framing.** The success of evaluation should give confidence to trust the agent when deployed to customers. This is correlated with, but distinct from, individual model accuracy. Evals should be intuitive, trustworthy, and easy to extend to a variety of scenarios.

**Lifecycle.** Continuous. Unlike [Configuration](./configuration.md) (startup-only, immutable), Evaluation collects data throughout runtime and aggregates offline. Two operational modes:

| Mode | Description |
|---|---|
| **Online** | Per-session metrics, user feedback, self-check gate — runs every session |
| **Offline** | E2E agent evals, regression testing, per-flow evaluation — runs at dev time / deployment |

---

## Evaluation Architecture

### E2E Agent Evals vs. Model Accuracy Testing

Two distinct evaluation systems with different aims, triggers, and formats.

| Aspect | E2E Agent Evals | Model Accuracy Testing |
|---|---|---|
| What it tests | The pipeline as a whole | Individual model components |
| When it runs | Every deployment, periodic regression | When a specific model changes |
| Format | Multi-turn conversations with expected actions and outputs | Standard train/dev/test splits |
| Goal | Trust that the agent works end-to-end | Confidence that a single model is accurate |
| Relation | If E2E evals pass, individual components likely did their job | Independent of E2E evals |

Model accuracy testing (e.g., retraining a slot prediction model) uses standard train/dev/test splits and is scoped to that model. If we retrain a dimension prediction model, we use the training set for training, dev set to tune hyper-parameters, and test set for evaluation. If we are only performing prompting, the training set consists of the chosen exemplars, the dev set covers the different scenarios, and the test set is a smaller held-out set to prevent degradation.

E2E agent evals assess whether the full NLU→PEX→RES pipeline produces correct behavior. This spec covers both, but the three-pillar approach (§ Offline Evaluation) is for E2E.

### Offline Testing Infrastructure

Flow-level integration tests are the primary testing vehicle for v1. Frontend tests, load tests, auth tests, and concurrency tests are deferred.

**Framework**: FastAPI `TestClient` with WebSocket support. Module-scoped fixtures for DB, auth, and test data.

**Test naming**: Flow-oriented, ordered by dax code — `{dax}_flow_name.py` (e.g., `{001}_query_flow.py`). Tests are stateful and accumulate conversation history across a test file.

**Assertion patterns**: Substring matching on response text, token membership checks, SQL/code inspection on tool output, action verification, negative assertions (no error prefix).

Focus on flow-level integration tests first. Too many tests early on add bloat without value.

### Online vs. Offline

| Mode | What happens | Cost | Frequency |
|---|---|---|---|
| Online | Passive signal collection, per-session metrics, user feedback, self-check gate | Low — no extra LLM cost except optional self-check | Every session |
| Offline | E2E agent evals (three pillars), regression testing, per-flow evaluation | Higher — LLM-as-judge for Final Output scoring | Every deployment / on change |

### Signal Flow Diagram

```
Every Module & Component
        │
        ▼
  Signal Envelopes
        │
   ┌────┴────┐
   ▼         ▼
Online     Offline
(Session   (Benchmark
 Record)    Reports)
   │         │
   └────┬────┘
        ▼
   Consumers
   ├─ Configuration (edge flow refinement)
   ├─ Prompt Engineer (A/B decisions)
   └─ Domain Builders (flow tuning)
```

---

## Signal Taxonomy

### Signal Sources Table

Every module and component emits structured signals. Organized by source.

| Source | Signal | When Emitted | Reference |
|---|---|---|---|
| NLU | Intent prediction + confidence | Every `think()` | [nlu.md § Step 1](../modules/nlu.md) |
| NLU | Flow prediction + top-3 scores | Every `think()` | [nlu.md § Step 2](../modules/nlu.md) |
| NLU | Multi-model vote agreement | Every majority vote round | [nlu.md § Step 2](../modules/nlu.md) |
| NLU | Contemplate re-route | Every `contemplate()` | [nlu.md § Contemplate](../modules/nlu.md) |
| NLU | Pre-hook check result (7 checks) | Every `think()` entry | [nlu.md § Pre-Hook](../modules/nlu.md) |
| NLU | Post-hook check result (4 checks) | Every `think()` exit | [nlu.md § Post-Hook](../modules/nlu.md) |
| PEX | Tool execution envelope | Every tool call | [pex.md § Step 2](../modules/pex.md) |
| PEX | Recovery attempt | Each recovery strategy tried | [pex.md § Recover](../modules/pex.md) |
| PEX | Pre-hook check result (7 checks) | Every `execute()` entry | [pex.md § Pre-Hook](../modules/pex.md) |
| PEX | Post-hook check result (5 checks) | Every `execute()` exit | [pex.md § Post-Hook](../modules/pex.md) |
| RES | Template fill coverage | Every `generate()` Step 3 | [res.md § Step 3](../modules/res.md) |
| RES | Streaming decision | Every `generate()` Step 4 | [res.md § Step 4](../modules/res.md) |
| RES | Pre-hook cleanup result (4 checks) | Every `generate()` entry | [res.md § Pre-Hook](../modules/res.md) |
| RES | Post-hook output result (4 checks) | Every `generate()` exit | [res.md § Post-Hook](../modules/res.md) |
| Ambiguity Handler | Ambiguity declaration | Every `declare()` | [ambiguity_handler.md § Lifecycle](../components/ambiguity_handler.md) |
| Dialogue State | Top-3 confidence scores | After every NLU prediction | [dialogue_state.md § Confidence Tracking](../components/dialogue_state.md) |
| Context Coordinator | Checkpoint | End of session | [context_coordinator.md § Checkpoints](../components/context_coordinator.md) |
| Prompt Engineer | Prompt version ID | Every prompt execution | [prompt_engineer.md § Prompt Versioning](../components/prompt_engineer.md) |
| Display Frame | Graceful degradation flag | On render failure | [display_frame.md § Rendering Pipeline](../components/display_frame.md) |
| Memory Manager | Promotion signal | On scratchpad promotion | [memory_manager.md § Promotion Triggers](../components/memory_manager.md) |

Each validation hook check failure is itself a signal (NLU: 7 pre + 4 post, PEX: 7 pre + 5 post, RES: 4 cleanup + 4 output).

### Signal Envelope

Standard wrapper for all evaluation signals.

```python
{
    'signal_id': str,
    'source': str,              # component name
    'signal_type': str,         # from Signal Sources table
    'timestamp': float,
    'session_id': str,
    'turn_id': str | None,
    'flow_id': str | None,
    'prompt_version_id': str | None,  # from Prompt Engineer
    'environment': str,         # dev | prod
    'payload': dict             # signal-specific data
}
```

The `prompt_version_id` field enables prompt version attribution (§ Prompt Version Attribution). The `flow_id` field enables per-flow evaluation and feedback attribution.

---

## Self-Check Gate

Evaluation-owned logic injected into the RES pipeline. Catches obvious mismatches before the user sees them — particularly useful for multi-step flows where the original intent may drift.

### Position in Pipeline

Runs after RES pre-hook cleanup (4 lifecycle checks) but before RES Step 1 (Ambiguity Check).

```
PEX completes → RES Pre-Hook (4 checks) → SELF-CHECK GATE → RES Step 1 → ...
```

### Checks

Two modes, distinguished by cost.

**Rule-based** (always run, zero LLM cost):

| # | Check | What it catches |
|---|---|---|
| 1 | Intent drift | Original predicted intent vs. completed flow intent mismatch |
| 2 | Slot coverage | Required slot values missing from response or display frame |
| 3 | Empty response | Non-empty required for user-facing intents |
| 4 | Length bounds | Outside min/max token range for intent type |

**LLM-based** (dev only, configurable via `self_check_gate_llm` feature flag):

| # | Check | What it catches |
|---|---|---|
| 5 | Semantic alignment | Single Haiku-class call: "Does the response answer the request? YES/NO with one-sentence reason." |

### Failure Handling

- Set `has_issues` on dialogue state (same pattern as PEX pre-hook failure)
- Emit signal envelope with `signal_type: 'self_check_failure'`
- Return to Agent for re-route or clarification
- LLM check is advisory in prod — emits signal but does not gate delivery

---

## Online Evaluation

### Per-Session Metrics

Structured record accumulating per-session metrics. Populated during runtime from signal envelopes.

#### Session Record Schema

| Group | Fields |
|---|---|
| Timing | Turn latencies per component (NLU, PEX, RES), total session duration |
| Routing | Flows attempted, completed, invalid; re-route count and details |
| Tool Execution | Calls, successes, failures, retries — grouped by `tool_id` |
| Ambiguity | Declarations by level, resolution outcomes |
| Prediction Quality | Vote rounds per turn, confidence scores, agreement ratios |
| Self-Check | Rule-based results (4), LLM-based result (if enabled) |
| Prompt Versions | `prompt_versions_used` — map of `{template_id.version: call_count}` |
| User Feedback | Explicit and implicit signals collected during session |

#### Annotated Session Record (Cooking)

Four-turn session: recipe search → nutrition lookup → ambiguity (partial) → resolution.

```yaml
session_id: "sess_20260115_a7f3"
domain: "cooking"
environment: "prod"
started_at: 1737000000.0
ended_at: 1737000047.2

# --- Timing ---
timing:
  total_duration_ms: 47200
  turns:
    - turn_id: "t1"
      nlu_ms: 820          # 3-model vote resolved in round 1
      pex_ms: 1340          # recipe_search tool call
      res_ms: 410
    - turn_id: "t2"
      nlu_ms: 790
      pex_ms: 2100          # nutrition_lookup tool call (external API)
      res_ms: 380
    - turn_id: "t3"
      nlu_ms: 1450          # escalated to round 2 vote (4 models)
      pex_ms: 0             # ambiguity declared — no execution
      res_ms: 520           # clarification question generated
    - turn_id: "t4"
      nlu_ms: 600           # resolution — no new vote needed
      pex_ms: 1580          # recipe_search with calorie filter
      res_ms: 440

# --- Routing ---
routing:
  flows_attempted: ["read_recipe", "nutrition_lookup", "read_recipe"]
  flows_completed: ["read_recipe", "nutrition_lookup", "read_recipe"]
  flows_invalid: []
  re_routes: 0
  re_route_details: []

# --- Tool Execution ---
tool_execution:
  recipe_search: { calls: 2, successes: 2, failures: 0, retries: 0 }
  nutrition_lookup: { calls: 1, successes: 1, failures: 0, retries: 0 }

# --- Ambiguity ---
ambiguity:
  declarations:
    - turn_id: "t3"
      level: "partial"       # "healthy version" is ambiguous
      resolved: true
      resolution_turn: "t4"

# --- Prediction Quality ---
prediction_quality:
  vote_rounds: [1, 1, 2, 1]  # per turn — turn 3 needed 4-model vote
  confidence_scores:
    - turn_id: "t1"
      top_3: [["read_recipe", 0.91], ["nutrition_lookup", 0.06], ["meal_plan", 0.02]]
    - turn_id: "t2"
      top_3: [["nutrition_lookup", 0.88], ["read_recipe", 0.08], ["compare_recipes", 0.03]]
    - turn_id: "t3"
      top_3: [["read_recipe", 0.52], ["meal_plan", 0.31], ["nutrition_lookup", 0.12]]
      # low confidence triggered round 2; ambiguity declared
    - turn_id: "t4"
      top_3: [["read_recipe", 0.94], ["nutrition_lookup", 0.04], ["meal_plan", 0.01]]

# --- Self-Check ---
self_check:
  - turn_id: "t1"
    rule_based: { intent_drift: false, slot_coverage: true, empty_response: false, length_bounds: true }
    # all clear — response delivered
  - turn_id: "t2"
    rule_based: { intent_drift: false, slot_coverage: true, empty_response: false, length_bounds: true }
  - turn_id: "t4"
    rule_based: { intent_drift: false, slot_coverage: true, empty_response: false, length_bounds: true }
  # t3 skipped — ambiguity path, no RES delivery

# --- Prompt Versions ---
prompt_versions_used:
  "nlu_flow_predict.v3": 4
  "res_recipe_template.v2": 2
  "res_nutrition_template.v1": 1
  "res_clarification.v1": 1
  "ambiguity_partial.v2": 1

# --- User Feedback ---
user_feedback:
  explicit: []               # no thumbs up/down this session
  implicit:
    - type: "continued_engagement"   # user kept going after ambiguity
      turn_id: "t4"
```

### User Feedback

#### Explicit Feedback

Captured on a response turn via UI affordances.

| Type | Shape | Example |
|---|---|---|
| Thumbs up/down | `bool` | User clicks thumbs-down on turn 2 |
| Correction | `{expected, actual}` | `{expected: "zucchini", actual: "squash"}` |
| Rating | `int` (1–5) | User rates session 4/5 |

#### Implicit Feedback

Inferred from user behavior patterns. No explicit UI action required.

| Signal | Interpretation | Detection |
|---|---|---|
| Re-ask | Rephrased same request — prior response was insufficient | Semantic similarity between consecutive user turns |
| Abandonment | Active/Pending flow left on stack — user gave up | Session end with non-empty flow stack |
| Correction follow-up | Next utterance contradicts agent — agent was wrong | Negation or correction patterns in next user turn |
| Continued engagement | User continued interacting — positive signal | Session length beyond ambiguity/error |
| Escalation to ambiguity | Agent couldn't handle it — negative signal | Ambiguity handler invoked after agent attempt |

#### Feedback Attribution

Explicit feedback captured on a response turn → `turn_id` → Context Coordinator → `flow_id` → full turn sequence. Implicit feedback inferred at session level during post-session aggregation. Both include `prompt_version_id` from signal envelope.

### Prompt Version Attribution

Closes the loop between [Prompt Engineer](../components/prompt_engineer.md) changes and measured outcomes.

1. Prompt Engineer assigns `{template_id, version}` to every template
2. Every prompt execution emits signal envelope with `prompt_version_id`
3. Session record aggregates `prompt_versions_used` with call counts
4. Feedback attributed to specific prompt versions that produced the output

**A/B testing.** [Configuration](./configuration.md) feature flags define experiment variants → Prompt Engineer selects version → Evaluation tracks results → comparison table generated offline.

---

## Offline Evaluation

### E2E Agent Evals (Three Pillars)

Three pillars spanning NLU, PEX, and RES — covering the full pipeline with limited ongoing costs. When we manually test the agent, we check that it "did the right thing" and "gave the right result." These three pillars cover that intuitive sense.

#### Workflow Prediction (NLU)

Did the agent predict the correct flow (from ~64 options)?

- **Metric**: Accuracy (0–100%)
- **Granularity**: More specific than intent (8 options), less granular than slot-filling — the ideal level for pipeline confidence
- **Requirement**: Diverse test scenarios covering the full flow space

#### Trajectory Optimization (PEX)

Did the agent choose the correct tool calls?

- **Metric**: Four scoring modes (see § Scoring)
- **Value**: Gets at the heart of agent behavior — correct actions lead to correct outcomes
- **Prerequisite**: Tools must be concretely defined to avoid ambiguity about what is "correct"

#### Final Output (RES)

Did the agent produce the correct response?

- **Metric**: 5-level rubric with LLM-as-judge for semantic evaluation (see § Scoring)
- **Value**: Ultimately what we care about most — the user-facing result
- **Cost**: Handles arbitrary complexity but requires LLM judge calls for semantic cases

### Test Case Format

JSON conversation format. Each test case: `convo_id`, `domain`, `available_data`, `turns` array. Each agent turn: `context` (slots, entities), `actions` (flow + tools = expected trajectory), `utterance` (expected response for Final Output scoring).

```json
[{
   "convo_id": 2001,
   "domain": "cooking",
   "available_data": ["recipes", "nutrition", "meal_plans"],
   "turns": [
      {
        "turn_count": 1,
        "role": "user",
        "utterance": "Find me a healthy pasta recipe under 500 calories"
      },
      {
        "turn_count": 2,
        "role": "agent",
        "context": {
          "key_entities": ["recipe", "ingredient"],
          "slots": {"cuisine_type": "italian", "calorie_max": 500}
        },
        "actions": [
          {"flow": "read_recipe", "tools": ["recipe_search", "nutrition_lookup"]}
        ],
        "utterance": "Here's a zucchini pasta primavera at 380 calories. It uses spiralized zucchini with cherry tomatoes, garlic, and fresh basil."
      },
      {
        "turn_count": 3,
        "role": "user",
        "utterance": "What about the protein content?"
      },
      {
        "turn_count": 4,
        "role": "agent",
        "context": {
          "key_entities": ["recipe", "nutrition"],
          "slots": {"recipe_id": "zucchini_primavera", "nutrient": "protein"}
        },
        "actions": [
          {"flow": "nutrition_lookup", "tools": ["nutrition_lookup"]}
        ],
        "utterance": "The zucchini pasta primavera has 12g of protein per serving. Adding grilled chicken would bring it to 38g."
      }
   ]
}]
```

### Scoring

#### Workflow Prediction Scoring

Accuracy — predicted flow matches expected flow per turn. Measured across the full test suite.

#### Trajectory Scoring Modes

Four options for measuring tool call correctness. Suppose the correct path is `[recipe_search, nutrition_lookup, recipe_search, meal_plan_api]` within the `read_recipe` flow, and the agent predicted `[recipe_search, nutrition_lookup, meal_plan_api, recipe_search]` within the `nutrition_lookup` flow.

| Mode | Description | Result |
|---|---|---|
| Partial path | Correct tools in sequence until first error | 2/4 correct before mismatch = 50% |
| Full path | All-or-nothing on exact tool sequence | Must match exactly = 0% or 100% |
| Path nodes | Correct tools regardless of order | All 4 tools present = 100% |
| Full workflow | Full path AND correct workflow prediction | Both must pass = 0% or 100% |

Default: **Full workflow** (strictest). Report all four for diagnostic insight.

#### Final Output Rubric

| Score | Criteria |
|---|---|
| Perfect | Answers the request completely, correct values, appropriate tone |
| Great | Answers the request, minor omissions or style issues |
| Good | Substantively correct, some gaps in completeness |
| Adequate | Partially addresses the request, notable issues |
| Poor | Wrong answer, hallucination, or doesn't address the request |

**Simple cases**: Rule-based value-matching — `target in response` (e.g., checking that "380 calories" appears in a nutrition answer).

**Complex cases**: LLM-as-judge — Haiku-class call with rubric. Used when the correct answer requires semantic evaluation (e.g., explanations, recommendations, multi-part responses).

### Regression Testing

**Triggers**: Prompt template version change, `ontology.py` change, domain YAML config change, policy code change, manual run.

**Thresholds**:

| Metric | Regression Threshold |
|---|---|
| Workflow prediction accuracy | > 2% drop |
| Trajectory (full workflow) | > 3% drop |
| Final output (mean rubric score) | > 0.5 level drop |
| Tool success rate | > 1% drop |
| Mean latency | > 20% increase |
| Self-check failure rate | Any increase |

### Per-Flow Evaluation

Three levels of flow-scoped testing.

| Level | Scope | Tools |
|---|---|---|
| Unit | Single policy with mocked tools | Fast, isolated, no external calls |
| Integration | Full NLU→PEX→RES for one flow | Sandboxed tools, real pipeline |
| Edge flow confusion | Run edge flow test cases, verify flow is NOT predicted | Validates edge flow definitions in Configuration |

Edge flow confusion testing is the refinement referenced in [configuration.md § Edge Flow Selection](./configuration.md): "Based on historical confusion patterns — start with best guesses, refine from evaluation data."

---

## Evaluation Consumers

### Consumer Access Table

| Consumer | What It Reads | Evaluation Data Path |
|---|---|---|
| Configuration (edge flow refinement) | Flow confusion patterns | Per-flow confusion matrices from offline evals |
| Prompt Engineer (A/B decisions) | Version comparison metrics | Session records aggregated by `prompt_versions_used` |
| Domain builders (flow tuning) | Per-flow accuracy, latency, failure rates | Offline per-flow reports + online session aggregates |
| Agent (runtime) | Self-check gate result | Self-check signal envelope |
| NLU (contemplate calibration) | Re-route success rate | Session records `re_route_details` |

### Feedback Loops

Three primary loops connecting evaluation data back to system improvements.

1. **Edge Flow Refinement**: Offline per-flow confusion matrices → update `ontology.py` edge flows → re-run evals to confirm improvement

2. **Prompt Optimization**: A/B test results → Prompt Engineer adopts winning version → Configuration feature flags control rollout

3. **Flow Tuning**: Aggregated session metrics by flow → identify fragile flows (high ambiguity, re-routes, tool failures) → improve policies / slots / recovery

### Agent Reinforcement Fine-Tuning (Future)

The evaluation infrastructure is designed to collect the signals needed for reinforcement fine-tuning (RFT) if and when we pursue it. Specifically:

- **Trajectory data**: Every session records the complete flow sequence, tool calls, and outcomes (Session Record § Tool Execution, § Routing)
- **Reward signals**: Explicit user feedback (thumbs, corrections, ratings) and implicit signals (re-asks, abandonment, continued engagement) provide per-turn reward labels
- **Prompt version attribution**: Links outcomes to specific prompt versions, enabling comparison of policy variants

This is not a current priority — the eval infrastructure exists for online/offline evaluation. But the same signals that power evaluation (trajectories + reward labels + attribution) are exactly what RFT requires. No additional instrumentation would be needed to generate training data for fine-tuning policies.
