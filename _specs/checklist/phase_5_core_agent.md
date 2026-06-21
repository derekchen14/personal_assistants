# Phase 5 — Core Agent

Implement all 9 components, the 3 module-loops (NLU / PEX / MEM), and the deterministic main Agent. Replace the
Phase 4 stubs with working implementations.

## Context

This is the largest phase. It implements the three-level system: 9 components that provide the infrastructure,
3 continuous LLM-loops that run in parallel (NLU understands, PEX acts, MEM remembers), and the **main Agent**
— deterministic code that governs the turn. There is **no RES**: the dispatched sub-agent builds the
TaskArtifact and the main Agent delivers it. Most components are reusable across domains, so much is copy-paste
from the scaffolding. By the end, the agent handles simple interactions end-to-end with hard-coded test flows.

**Prerequisites**: Phase 4 complete — server running, config loaded, database created, all shells exist.

**Outputs**: Fully implemented components, module-loops, and main Agent handling simple interactions.

**Spec references**: [components/*.md](../components/), [modules/*.md](../modules/),
[architecture.md](../architecture.md)

---

## Steps

### Step 1 — Dialogue State  (NLU)

The structured, ontology-filled belief. **File**: `backend/components/dialogue_state.py`

**Implement**:
- **Four-block document**: `session`, `user_beliefs`, `grounding`, `flow_stack`. There is **no `flags` block**
  — `keep_going` is PEX loop control, `has_plan` is computed from the agenda, `natural_birth` is a per-flow
  property.
- **Predicted state**: `pred_intent` (one of **7** intents) and `flow_name`; `pred_flows: list[dict]` for
  candidates. No `dax`/`slots` on the state — slots live on the flow instance.
- **Belief tools** (no generic `write_state`): one read tool `understand` (returns serialized state — flow,
  intent, confidence, slots, grounding), and three writes — `classify_intent`, `detect_flow`, `fill_slots`
  (entity extraction, its sub-task, writes `grounding`).
- **Serialization**: `serialize()` → JSON dict; `from_dict(data, config)`. The main Agent calls `serialize()`
  in its post-hook — persistence is deterministic code, not a tool.
- **State history**: a per-turn snapshot (hybrid full-JSON doc + promoted/indexed columns); rollback is the
  existing `undo` flow replaying snapshots — no separate diff/rollback machinery.

**Reference**: [dialogue_state.md](../components/dialogue_state.md)

### Step 2 — Workflow Planner / FlowStack  (PEX)

The FlowStack stores the flows; Workflow Planning / Sub-agent Routing is the activity PEX performs over it.
**File**: `backend/components/flow_stack/` (stack.py, slots.py, parents.py, flows.py, __init__.py)

**Implement**:
- **Stack operations**: `stackon` / `fallback` / `pop_completed`. Hard depth limit **16**; overflow writes a
  note to the scratchpad to revisit (no unbounded branching).
- **Multiple active flows**: the Active block must be **contiguous** at the top, Pending strictly beneath.
- **Flow lifecycle**: Pending → Active → Completed/Invalid. `complete_flow` sets `Completed` (grounding-gated).
- **No FlowEntry**: BaseFlow IS the entry (flow_id, status, plan_id, turn_ids, result). `flow_classes` dict
  maps names → classes; `push(flow_name)` instantiates and sets runtime fields. **PEX's Workflow Planner
  stacks flows** — NLU only records the detection.
- **Flow class hierarchy**: BaseFlow + intent parents; methods `fill_slots_by_label()`, `fill_slot_values()`,
  `slot_values_dict()`, `is_filled()`, `to_dict()`, `name(full=False)`, `get(key, default)`, `serialize()`.
- **Deduplication / carryover**; **fallback protocol** (new flow, best-effort slot mapping, old → Invalid).
- **Concurrency**: the contiguous Active block runs as **asyncio tasks**; no "Internal" flows.
- **Plan decomposition**: the Workflow Planner decomposes a Plan request into sub-flows — there is no Plan
  policy file.

**Reference**: [workflow_planner.md](../components/workflow_planner.md)

### Step 3 — Context Coordinator  (MEM · L1)

The append-only event stream. **File**: `backend/components/context_coordinator.py`

**Implement**:
- **Turn structure**: `turn_id`, role (agent/user/system), form (text/speech/image/action), content.
- **`compile_history(look_back, keep_system)`**, **`recent_turns(n)`**, **`last_user_turn`**, completed-flows
  index, checkpoints (turn history + dialogue-state snapshots), turn→flow mapping.
- Holds MEM-computed rolling summaries as special turn entries (it stores, it does not summarize).

**Reference**: [context_coordinator.md](../components/context_coordinator.md)

### Step 4 — Prompt Engineer  (PEX)

Model-agnostic LLM interface. **File**: `backend/components/prompt_engineer.py`

**Implement**:
- Provider-agnostic dispatch (tier abstraction `low`/`med`/`high` via `ACTIVE_FAMILY`); prompt composition;
  output parsing + guardrails; exponential backoff/retry; token-budget logging; prompt caching markers.

**Reference**: [prompt_engineer.md](../components/prompt_engineer.md)

### Step 5 — Task Artifact  (PEX)

The A2A-aligned per-flow output. **File**: `backend/components/task_artifact.py`

**Implement**:
- **3 stored attributes** (`origin`, `parts: list[Part]`, `blocks: list[BuildingBlock]`) + **3 helper
  properties** (`data`, `thoughts`, `code`). Part oneof contract (exactly one of text/raw/url/data).
- **Lifecycle**: built by the dispatched sub-agent; **PEX curates the concurrent sub-agents' N artifacts → one
  per turn** (stack order, dedup, single-flow-type origin is trivial, a failed sibling is dropped and logged);
  the main Agent delivers it. Pagination (first page 512 rows + reference id).

**Reference**: [task_artifact.md](../components/task_artifact.md)

### Step 6 — Ambiguity Handler  (NLU, on the World)

Four-level uncertainty. **File**: `backend/components/ambiguity_handler.py`

**Implement**:
- **4 levels**: general, partial, specific, confirmation.
- **Gate → level mapping** (the 3 NLU gates): gate 1 intent/flow failure → `general`; gate 2 grounding-entity
  failure → `partial`; gate 3 slot-filling failure → `specific`.
- **4 methods** (the `handle_ambiguity` tool dispatches to these): `declare(level, observation, metadata)`,
  `present()` (predicate), `ask()` (clarification text), `resolve()`.
- Lives on the **World** (shared), beside the Session Scratchpad.

**Reference**: [ambiguity_handler.md](../components/ambiguity_handler.md)

### Step 7 — Session Scratchpad  (NLU, on the World)

The append-only swarm ledger. **File**: lives on the World, beside the Ambiguity Handler.

**Implement**:
- Entries are dicts: key = bare flow name; minimal required fields (`version`, `turn_number`, `used_count`) + payload.
  Hard cap 64; LRU eviction.
- **API**: `append_to_scratchpad(writer, entry)` (stamps `writer` in code; triggers NLU review),
  `read_from_scratchpad(...)` (read-only), `update_scratchpad(key, entry)` (**NLU only**).
- Promotion → L2/L3: a frequency counter (`used_count` ≥ N) plus a low-tier LLM-judge (salience / surprisal),
  run as a background MEM task; explicit promotion is the `store_preference` path.

**Reference**: [session_scratchpad.md](../components/session_scratchpad.md)

### Step 8 — Memory tiers L2 / L3  (MEM)

**Files**: `backend/components/user_preferences.py`, `backend/components/business_context.py`

**Implement**:
- **User Preferences (L2)**: per-account key-value rules (graph search / ID lookup); trajectory playbooks;
  reached via the `recall` skill.
- **Business Context (L3)**: per-tenant docs in vector space, retrieve → re-rank top 10; reached via the
  `retrieve` skill.
- Conversation summarization: MEM computes a rolling summary; CC stores it.

**Reference**: [user_preferences.md](../components/user_preferences.md) ·
[business_context.md](../components/business_context.md)

### Step 9 — NLU module-loop

**File**: `backend/modules/nlu.py`

**Implement**:
- **`prepare()` pre-hook** — input guards (empty, min/max length, exact repeat, Tier-0 shortcuts, reserved
  keywords, unsupported language).
- **Three modes**: `react` (click path — fills required slots from payload, **no LLM call**), `think`
  (detection + ambiguity), `contemplate` (narrowed re-routing).
- **`think()`**: intent (one of 7), flow detection (3 escalating ensemble rounds → `general` ambiguity on no
  majority), slot-filling (domain intents only).
- **Detect, don't push**: NLU **records** the detected flow (`detect_flow`); **PEX's Workflow Planner** decides
  whether to `stackon`. NLU commits belief via the three write tools, or declares ambiguity instead of guessing.
- **Continuous loop**: always-running asyncio task. The await-critical set is the **3 NLU gates** — gate 1
  intent+flow (via `understand()`), gate 2 grounding-entity (via `read_from_scratchpad()`), gate 3 slot-filling.
  A **click awaits gates 1+2**; slot-filling stays **async**, alongside scratchpad review, triggered by
  changes to the scratchpad / ambiguity handler / dialogue state.
- **`validate()` post-hook** — flow exists, slots match schema, no stack dupes, confidence well-formed, entity
  repair.

**Reference**: [nlu.md](../modules/nlu.md)

### Step 10 — PEX module-loop

**File**: `backend/modules/pex.py`

**Implement**:
- **The acting loop** (`_run_loop`, bounded): tool-call hygiene (catalog validation, consecutive de-dup,
  corrective cap, thinking nudge, no-tool-text-ends-turn, `_final_emit`). Consults NLU (`understand` + the
  belief writes) and MEM (`recap`/`recall`/`retrieve`) in parallel.
- **`activate_flow`**: stage + run a flow's policy as a **sub-agent** (level 2 — cannot nest). Every flow is
  **agentic**; deterministic operations are plain tools.
- **Sub-agent toolset**: `append_to_scratchpad` / `read_from_scratchpad` / `understand` / `handle_ambiguity`
  (NLU); `recap` / `recall` / `retrieve` (MEM); plus `flow.tools`.
- **`check()` pre-hook** (required slots, manifest, Lethal Trifecta gate) and **`verify()` post-hook**.
- **Reply composition**: PEX composes the spoken reply **directly** via a voice Skill — there is no
  naturalization / `respond` step and no template registry.
- **Self-check / verify failure fan-out**: a failure writes a `TaskArtifact(violation)`, appends a violation
  entry to the Scratchpad (notifies NLU), and records a Context Coordinator system action (notifies MEM). This
  replaces the removed `has_issues`.
- **Artifact aggregation**: curate active flows' artifacts into one per turn.
- **Policies**: net **5 policy files** — a single `converse` sub-agent + 4 domain intents. Plan and Clarify
  have no policy file (Workflow Planner decomposes Plan; the Ambiguity Handler drives Clarify). Method-shape
  contract; closed 8-code violation vocabulary; `complete_flow` (grounding-gated).

**Reference**: [pex.md](../modules/pex.md)

### Step 11 — MEM module-loop

**File**: `backend/modules/mem.py`

**Implement**:
- **Three skills, one per tier**: `recap` (L1 Context Coordinator), `recall` (L2 User Preferences),
  `retrieve` (L3 Business Context, KB + vector DB).
- **Read-mostly**: MEM does not write the belief file; its durable write path is the append-only event stream
  plus L2/L3 promotion. Pro-active prefetch runs async.
- Compaction in the post-hook; long-term TaskArtifact storage (a copy handed in by the main Agent via World).

**Reference**: [mem.md](../modules/mem.md)

### Step 12 — Main Agent (the turn)

Wire the deterministic turn lifecycle in `backend/agent.py`.

**Implement**:
- **Pre-hook**: append the user turn to the event stream. The turn discriminator is the presence of a `dax`
  (no `turn_type`): a `dax` present → **click** → run `NLU.react()` (fills required slots, no LLM) → dispatch,
  no model loop. No `dax` → **utterance** → enter PEX's loop (await NLU on the gating path).
- **Loop**: run PEX's tool-calling loop; plain text with no tool calls ends the turn.
- **Post-hook**: record the agent turn, `serialize()` the Dialogue State, run the compaction check, **wait for**
  pending async NLU/MEM tasks to settle, then deliver the single aggregated TaskArtifact — a
  processed version to the user (webserver) and a copy to MEM (via the World object).
- **Three levels**: main Agent (deterministic) → NLU/PEX/MEM loops → PEX sub-agents (no fourth level).
- **World instance**: session-scoped container holding `states[]`, `flow_stack`, `context`, the Ambiguity
  Handler, and the Session Scratchpad. Modules receive the World and unpack what they need.

**Reference**: [architecture.md](../architecture.md)

### Step 13 — Self-Check Gate

Evaluation-owned checks injected into the **post-hook**, before artifact delivery.

**Rule-based** (always, zero LLM): intent drift, slot coverage, empty response, length bounds.
**LLM-based** (dev only, behind a flag): semantic alignment (Haiku: "Does the response answer the request?").
On failure: fan out the D5 violation channel — write a `TaskArtifact(violation)`, append a Scratchpad
violation entry (notifies NLU), and record a Context Coordinator system action (notifies MEM); then return
control to the main Agent. (This replaces the removed `has_issues`.)

**Reference**: [evaluation.md § Self-Check Gate](../utilities/evaluation.md)

---

## File Changes Summary

| Action | File | Description |
|---|---|---|
| Modify | `backend/components/dialogue_state.py` | four-block belief + `understand`/`classify_intent`/`detect_flow`/`fill_slots` |
| Modify | `backend/components/flow_stack/` | FlowStack + Workflow Planning (stack.py, slots.py, parents.py, flows.py, __init__.py) |
| Modify | `backend/components/context_coordinator.py` | L1 event stream |
| Modify | `backend/components/prompt_engineer.py` | model-agnostic interface |
| Modify | `backend/components/task_artifact.py` | A2A artifact + Part oneof |
| Modify | `backend/components/ambiguity_handler.py` | 4 levels, 4 methods (on the World) |
| Create | `backend/components/user_preferences.py` | L2 tier (`recall`) |
| Create | `backend/components/business_context.py` | L3 tier (`retrieve`) |
| Modify | `backend/modules/nlu.py` | understand loop |
| Modify | `backend/modules/pex.py` | acting loop + sub-agents |
| Modify | `backend/modules/mem.py` | recap/recall/retrieve |
| Modify | `backend/agent.py` | deterministic main-Agent turn |

(The Session Scratchpad lives on the World, beside the Ambiguity Handler — no separate module file. There is
**no** `res.py` and **no** `memory_manager.py`.)

---

## Verification

- [ ] Dialogue state serializes/deserializes (round-trip); four blocks, no `flags` block
- [ ] `understand` returns serialized state; `classify_intent`/`detect_flow`/`fill_slots` write belief
- [ ] FlowStack push/pop/peek with `flow_classes`; depth cap 16; contiguous Active block enforced
- [ ] `complete_flow` is grounding-gated; PEX (not NLU) stacks flows
- [ ] Context coordinator stores/retrieves turns; `compile_history()` / `recent_turns()`
- [ ] Prompt Engineer makes LLM calls and parses responses
- [ ] TaskArtifact: Part oneof enforced; PEX curates N artifacts → 1 per turn
- [ ] Ambiguity handler: 4 levels, `declare`/`present`/`ask`/`resolve`; on the World
- [ ] Scratchpad: `append_to_scratchpad` stamps writer + triggers NLU; `update_scratchpad` NLU-only
- [ ] MEM exposes `recap`/`recall`/`retrieve`; does not write the belief file
- [ ] NLU `prepare()` rejects invalid input; `react()` fills required slots with no LLM call
- [ ] NLU loop awaits on the gating path; async housekeeping settles at turn boundary
- [ ] PEX loop dispatches sub-agents (no fourth level); aggregates artifacts
- [ ] Main Agent: click-bypass vs. utterance loop; post-hook serialize + deliver to user + MEM
- [ ] No `res.py`, no `memory_manager.py`, no Internal flows anywhere
