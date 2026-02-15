# Phase 5 — Core Agent

Implement all 7 components, full NLU/PEX/RES modules, and the Agent orchestrator. Replace the stubs from Phase 4 with working implementations.

## Context

This is the largest phase. It implements the full agent pipeline: 7 components that provide the infrastructure (state tracking, context, prompts, display, ambiguity, memory), 3 modules that execute the pipeline (NLU → PEX → RES), and the Agent class that orchestrates everything. While this may seem overwhelming, the components are designed to be reusable across domains, so most of the work is already availble to copy and paste from the scaffolding or other domains. By the end, the agent can handle simple interactions end-to-end with hard-coded test flows.

**Prerequisites**: Phase 4 complete — server running, config loaded, database created, all shells exist.

**Outputs**: Fully implemented components, modules, and Agent class handling simple interactions.

**Spec references**: [components/*.md](../components/), [modules/*.md](../modules/), [architecture.md § Agent](../architecture.md)

---

## Steps

### Step 1 — Dialogue State

Implement the state tracking component. The dialogue state grounds the agent in its beliefs.

**File**: `backend/components/dialogue_state.py`

**Implement**:
- **Predicted state**: Hierarchical with two levels — intent (7 modes) and flow (up to 64 per domain)
- **Slot-filling**: Slot priority system (Required, Elective, Optional) with type validation against the 16 slot types
- **Flags**: `keep_going`, `has_issues`, `has_plan`, `natural_birth`
- **Serialization**: `serialize()` → JSON dict, `from_dict(labels)` → reconstruct from persistence or NLU labels
- **State history**: Diffs after every turn, full snapshots when >1 completed flows are popped
- **Rollback**: Reconstruct any prior state by replaying diffs from the nearest snapshot
- **Confidence tracking**: Store top-3 predictions with scores

**Reference**: [dialogue_state.md](../components/dialogue_state.md)

### Step 2 — Flow Stack

Implement the stack data structure within dialogue state.

**File**: `backend/components/flow_stack.py`

**Implement**:
- **Stack operations**: push, pop, peek — single active flow at top
- **Flow lifecycle**: Pending → Active → Completed/Invalid states
- **Flow class hierarchy**: BaseFlow with intent-specific parent classes, each flow inherits `fill_slots_by_label()`, `fill_slot_values()`, `is_filled()`, `needs_to_think()`, `serialize()`
- **Deduplication**: Check if predicted flow already exists on stack in Pending/Active state; carry over if so
- **Plan flow lifecycle**: Plan flow at stack bottom, sub-flows above, `plan_id` tracking, replanning check between sub-flows
- **Fallback protocol**: Create new flow, best-effort slot mapping, mark old Invalid, push new
- **Concurrency model**: Single-threaded user-facing flows, parallel Internal flows with dependency annotations

**Reference**: [flow_stack.md](../components/flow_stack.md)

### Step 3 — Context Coordinator

Implement structured turn storage and retrieval.

**File**: `backend/components/context_coordinator.py`

**Implement**:
- **Turn structure**: `turn_id`, role (agent/user/system), form (text/speech/image/action), content
- **Fast-access window**: `recent` list of last 7 utterance-type turns, pre-filtered
- **`compile_history(turns, keep_system)`**: Primary retrieval method. Small lookbacks use fast-access window; larger ones scan full history
- **Completed flows tracking**: Convenience index of flows finished during session
- **Checkpoints**: Bundle full turn history + dialogue state snapshots, created at session end
- **Turn–flow mapping**: CC stores turns with `turn_id`; flows hold pointers to their `turn_id`s

**Reference**: [context_coordinator.md](../components/context_coordinator.md)

### Step 4 — Prompt Engineer

Implement model-agnostic LLM interface.

**File**: `backend/components/prompt_engineer.py`

**Implement**:
- **Model invocation**: Generic prompt function accepting any caller, streaming vs. regular modes
- **Multi-provider support**: Anthropic, OpenAI, Google — swap providers without changing calling code
- **Prompt composition**: Assemble prompts following the 8-slot format (grounding data → role/task → instructions → keywords → output shape → exemplars → closing reminder → final request)
- **Output parsing**: Parse LLM output into structured format, handle malformed responses
- **Guardrails**: Validate structured output (JSON, SQL, Python), retry with reformulated prompts on failure
- **Backoff & retry**: Exponential backoff on rate limits/timeouts/server errors, configured via resilience settings
- **Data preparation**: Format tables, lists, structured data for LLM consumption
- **Token budget logging**: Track usage across prompt sections
- **Prompt versioning**: Unique ID + version per template, tied to evaluation results

**Reference**: [prompt_engineer.md](../components/prompt_engineer.md)

### Step 5 — Display Frame

Implement the data-display decoupling layer.

**File**: `backend/components/display_frame.py`

**Implement**:
- **Common attributes**: `data`, `code`, `source`, `display_name`, `display_type`
- **Frame lifecycle**: Created by policy in PEX, scoped per flow, consumed by RES, discarded on flow completion
- **Pagination**: First page (512 rows default) with `table_id` reference for full data
- **Domain-specific attributes**: Extension point for domain-specific fields (e.g., `shadow`, `visual` for data analysis)
- **One frame = one block rule**: Each frame maps to exactly one block per turn

**Reference**: [display_frame.md](../components/display_frame.md)

### Step 6 — Ambiguity Handler

Implement four-level uncertainty tracking and resolution.

**File**: `backend/components/ambiguity_handler.py`

**Implement**:
- **4 levels**: General (intent unclear), Partial (entity unresolved), Specific (slot missing/invalid), Confirmation (candidate needs sign-off)
- **State**: Uncertainty counts per level, observation, metadata (key-value, cleared per turn), generation flags
- **Lifecycle**: Recognize → Declare → Respond → Resolve
- **Core functions**:
  - `declare(level, observation, metadata, generation_flags)` — record uncertainty
  - `ask()` → dispatch to `general_ask`, `partial_ask`, `specific_ask`, `confirmation_ask`
  - `generate()` — execute LLM call if generation flags set (lexicalize, naturalize, or compile mode)
  - `resolve()` — clear stored values
  - `present()` — check if unresolved ambiguity exists

**Reference**: [ambiguity_handler.md](../components/ambiguity_handler.md)

### Step 7 — Memory Manager

Implement three-tier cache hierarchy.

**File**: `backend/components/memory_manager.py`

**Implement**:
- **Session Scratchpad (L1/L2)**: In-context, per-conversation. 3–5 summarized snippets per flow. Hard cap 64 snippets. LRU eviction. Written at end of each flow.
  - Access: `memory.scratchpad.write(snippet)`, `memory.scratchpad.read()`
- **User Preferences (RAM)**: Per-account, persists across conversations. Key-value pairs (graph search or ID lookup). Lambda functions that modify agent behavior.
  - Access: `memory.preferences.update(key, value)`, `memory.preferences.get(key)`
  - **Trajectory Playbooks**: Store successful flow trajectories (flow_dact, slots, tool_calls, outcome, user_query). Retrieved by semantic similarity on future requests.
- **Business Context (Hard Disk)**: Per-tenant, shared across users. Documents embedded in vector space. Retrieval: vector search → re-rank to top 10.
- **Promotion triggers**: Salience, surprisal, frequency, explicit user request
- **Conversation summarization**: Rolling summary when scratchpad/turn count grows too large. MM calculates summary; CC stores it.

**Reference**: [memory_manager.md](../components/memory_manager.md)

### Step 8 — NLU Module

Implement full natural language understanding.

**File**: `backend/modules/nlu.py`

**Implement**:
- **`prepare()` pre-hook** — 7 checks: empty input, min length (2 chars), max length (1024 tokens), exact repeat, command shortcuts (Tier 0), system-reserved keywords, unsupported language
- **`think()`**:
  - Step 1 — Intent prediction: single Sonnet call, predict one of 6 user-facing intents (Internal never predicted)
  - Step 2 — Flow prediction: majority vote (3 escalating rounds). Round 1: Sonnet + Gemini Flash (2/2 agree). Round 2: + Opus + Gemini Pro (3/4). Round 3: + Opus with extended thinking (3/5). No majority after 3 → General ambiguity. Flow deduplication check after prediction.
  - Step 3 — Slot-filling: single Sonnet call for domain-specific intents only (Converse/Plan skip). Full conversation context.
- **`contemplate()`** — single Opus call with narrowed search space: exclude failed flow, restrict to related flows using ambiguity metadata, trust region principle
- **`react()`** — lightweight processing for user actions (no prompts, deterministic mapping to dialogue state)
- **`validate()` post-hook** — 5 checks: flow exists in registry, slots match schema, no stack duplicates, confidence well-formed, entity repair

**Reference**: [nlu.md](../modules/nlu.md)

### Step 9 — PEX Module

Implement the policy execution engine.

**File**: `backend/modules/pex.py`

**Implement**:
- **`check()` pre-hook** — 7 checks: active flow exists, policy registered, required slots filled, elective slots satisfied, tool manifest valid, timeout configured, Lethal Trifecta gate
- **`execute()`**:
  - Step 1 — Slot review: pull active flow, check missing slots, fill from CC/MM, declare ambiguity if still missing
  - Step 2 — Tool invocations: assemble skill prompt, provide tools (flow-specific + component), skill runs autonomously in a loop. Code guardrails applied before execution. Optional reflection loop for creative/complex flows. LATS for Plan decomposition.
  - Step 3 — Result processing: branch by outcome (success → create Frame, failure → partial data + warning, uncertain → enter recovery). Route by intent (domain → Frame, Converse → scratchpad, Plan → stack sub-flows, Internal → scratchpad)
  - Step 4 — Flow completion: store Frame, update lifecycle (Completed/Active), set flags, verification, scratchpad update
- **`recover()`** — escalation ladder: retry skill → gather context (Internal flows) → re-route via contemplate → escalate to user
- **`verify()` post-hook** — 5 checks: state consistency, slots intact, output well-formed, no duplicate flows, flags coherent

**Skill output contract** — every skill returns one of:
- `success`: `{"outcome": "success", "data": {...}, "scratchpad_entries": [...]}`
- `failure`: `{"outcome": "failure", "error_category": "...", "message": "...", "partial_data": null}`
- `uncertain`: `{"outcome": "uncertain", "reason": "...", "context": {...}}`

**Reference**: [pex.md](../modules/pex.md)

### Step 10 — RES Module

Implement the response generator.

**File**: `backend/modules/res.py`

**Implement**:
- **`start()` pre-hook** — 4 checks: pop Completed flows (retain as full objects), snapshot trigger (>1 completed), pop Invalid flows, stack integrity
- **`respond()`** — entry point. Routes to generate/clarify/display via lightweight Haiku call. May invoke multiple sub-functions per turn.
- **`generate()`**:
  - Step 1 — Ambiguity check: call `present()`, if present → `ask()` → write clarification to CC → skip to Step 5
  - Step 2 — Response routing: by intent (Converse/domain → Step 3, Plan with keep_going → post-hook, Internal → post-hook)
  - Step 3 — Template fill + naturalize: look up template (domain override by dact → base by intent), fill slots, then naturalize via Prompt Engineer. Multi-flow merge if multiple completed flows.
  - Step 4 — Streaming decision: above threshold → stream, below → buffer
  - Step 5 — CC write: write final response as agent utterance
- **`clarify()`** — generate clarification questions when ambiguity is present
- **`display()`** — no-op if no frame. Pre-hook: frame exists, required attributes set, chart type valid, pagination resolvable. Step 1: map display_type to block type. Step 2: render with data payload. Post-hook: block rendered, truncation bounded, degradation visible.
- **`finish()` post-hook** — 4 checks: response coherence, silent turn valid, lifecycle complete, state consistency

**Template registry**:
- Base templates: one per intent
- Domain overrides: keyed by dact name, full replacement
- Features: `block_hint`, `skip_naturalize`, conditional sections

**Reference**: [res.md](../modules/res.md)

### Step 11 — Agent Orchestrator

Wire the full turn pipeline in `backend/agent.py`.

**Implement**:
- **Turn pipeline**: NLU `think()`/`react()` → PEX `execute()` → RES `respond()`
- **`keep_going` loop**: After RES, if flag set, loop back to PEX with next flow
- **Mid-plan replanning**: When `has_plan` set, check between RES and PEX iterations whether remaining plan still makes sense
- **Input validation routing**: NLU `prepare()` failures → skip pipeline → RES rejection message. PEX `has_issues` → Agent receives control.
- **Failure handling** — two tiers:
  - Tier 1: PEX repair loop (within execute, up to 4 attempts)
  - Tier 2: Agent cascade — re-route → skip → escalate
- **Internal flow triggering**: Agent triggers Internal flows directly, parallelizes independent ones
- **World instance**: Session-scoped container with state history, frame collection, data registry, domain context

**Reference**: [architecture.md § Agent](../architecture.md)

### Step 12 — Self-Check Gate

Implement evaluation-owned logic injected into the RES pipeline.

**Position**: After RES pre-hook, before RES Step 1.

**Rule-based checks** (always run, zero LLM cost):
1. Intent drift — original vs. completed flow intent mismatch
2. Slot coverage — required slot values missing from response/frame
3. Empty response — non-empty required for user-facing intents
4. Length bounds — outside min/max token range

**LLM-based check** (dev only, behind feature flag):
5. Semantic alignment — Haiku call: "Does the response answer the request?"

On failure: set `has_issues`, emit signal, return to Agent.

**Reference**: [evaluation.md § Self-Check Gate](../utilities/evaluation.md)

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Modify | `<domain>/backend/components/dialogue_state.py` | Full implementation |
| Modify | `<domain>/backend/components/flow_stack.py` | Full implementation |
| Modify | `<domain>/backend/components/context_coordinator.py` | Full implementation |
| Modify | `<domain>/backend/components/prompt_engineer.py` | Full implementation |
| Modify | `<domain>/backend/components/display_frame.py` | Full implementation |
| Modify | `<domain>/backend/components/ambiguity_handler.py` | Full implementation |
| Modify | `<domain>/backend/components/memory_manager.py` | Full implementation |
| Modify | `<domain>/backend/modules/nlu.py` | Full implementation |
| Modify | `<domain>/backend/modules/pex.py` | Full implementation |
| Modify | `<domain>/backend/modules/res.py` | Full implementation |
| Modify | `<domain>/backend/agent.py` | Full implementation with turn pipeline |

---

## Verification

- [ ] Dialogue state serializes/deserializes correctly (round-trip test)
- [ ] Flow stack push/pop/peek work correctly
- [ ] Flow lifecycle transitions are valid (no invalid state transitions)
- [ ] Context coordinator stores and retrieves turns
- [ ] `compile_history()` returns correct turns from fast-access window
- [ ] Prompt Engineer makes LLM calls and parses responses
- [ ] Display frame holds data and maps to block types
- [ ] Ambiguity handler declares and resolves at all 4 levels
- [ ] Memory manager reads/writes scratchpad, preferences, business context
- [ ] NLU `prepare()` rejects invalid input (empty, too long, repeat)
- [ ] NLU `think()` predicts intent and flow (test with hard-coded exemplars)
- [ ] PEX `execute()` runs a skill and creates a frame
- [ ] PEX `recover()` escalates through the recovery ladder
- [ ] RES `generate()` fills a template and naturalizes it
- [ ] RES `display()` maps frames to blocks
