# Overall Structure

We model the problem as a POMDP where the observation is the user utterance, and the hidden aspect is the user's intent. Each state within the MDP is a flow. Each flow is historically called a dialogue act.

There is a central orchestrator that calls upon 3 modules, 7 core components, and 4 utilities.

## Modules

All modules have a pre-hook for set-up (eg. validating that pre-requisite information is available) and a post-hook for clean-up (eg. validating the dialogue state is not corrupted). Each module entry point is wrapped with a top-level error decorator that catches unhandled exceptions and returns a safe error message — the scaffold's `@handle_breaking_errors` pattern serves as a reference implementation.

1. **[NLU](./modules/nlu.md)** (Natural Language Understanding) — Routes user requests towards up to 64 different flows. Predicts the flow via `think`, and recovers from mis-predictions via `contemplate`.

2. **[PEX](./modules/pex.md)** (Policy Executor) — Holds all policies associated with each flow. Each policy has access to 1-3 tools that run deterministically; dynamic behavior lives in the policy surrounding the tool.

3. **[RES](./modules/res.md)** (Response Generator) — Writes the agent response or visual display back to the user. Operates independently of the policy that was executed; only requires the dialogue state.

## Agent (Orchestrator)

The Agent class is the concrete implementation of the orchestrator pattern. It drives the turn pipeline, manages flow lifecycle, handles failures, and also manages session-level concerns (data loading, session state, user lookup). The orchestrator is not a separate entity — it is the Agent itself.

### Turn Pipeline

Every user turn follows this sequence:

| Step | Owner | Action |
|---|---|---|
| 1 | NLU `think()` / `react()` | Predict intent and flow, fill slots |
| 2 | PEX `execute()` | Run the active flow's policy and tools |
| 3 | RES `respond()` | Route to `generate()` for text, `clarify()` for clarification, or `display()` for visuals as needed |

Self-checks are not a separate gate — they happen within the pre-hooks and post-hooks of each module (NLU `validate()`, PEX `verify()`, RES `finish()`).

If `keep_going` is set on the dialogue state after step 3, the Agent loops back to step 2 (PEX) internally with the next flow on the stack. NLU is not re-invoked — the remaining flows were already stacked. The `keep_going` loop is contained inside the Agent, not at the communication layer (e.g., WebSocket).

**Mid-plan replanning**: When `has_plan` is set, the Agent performs a replanning check between steps 3 and 2 on each iteration. After RES completes and the active sub-flow is marked Completed, the Agent checks whether the remaining plan still makes sense given what was discovered. The Plan flow sits at the bottom of the stack — e.g., Plan X adds sub-flows A, B, C → stack is `[X, C, B, A]`. After A completes and is popped, the Agent can: (a) continue to B as planned, (b) reorder or drop remaining sub-flows based on scratchpad findings, or (c) push new sub-flows if the completed flow revealed the need. The Plan flow (X) is not popped until it makes a prompted decision that the overall task is complete — successful completion of a Plan flow is not just successful tool execution, but a deliberate assessment. See [Flow Stack § Plan Flow Lifecycle](./components/flow_stack.md).

### World

The Agent owns a `World` instance — a session-scoped container that acts as the data registry and state archive. World stores:

- **State history**: All prior `DialogueState` objects for the session
- **Frame collection**: All frames produced by policies (the Agent's frame archive)
- **Data registry**: Valid tables, columns, and per-table/column metadata for the current session
- **Domain context**: Domain-specific session context (e.g., campaigns, channels for marketing; calendars for scheduling)

World is not a core component — it lives inside the Agent and provides the session-level storage that individual components reference. Dialogue State tracks beliefs; World tracks what the agent has seen and produced.

### Flow Lifecycle Management

The Agent manages flows that bypass NLU:

- **Internal intent triggering** — Internal flows (memory cleanup, state repair, session summarization) are triggered directly by the Agent, never predicted by NLU. See [Dialogue State § Intent](./components/dialogue_state.md).
- **`keep_going` continuation** — When a plan has stacked multiple flows, the Agent continues through each without waiting for user input. The active flow completes, RES cleans up, and the next Pending flow becomes Active. See [Dialogue State § Flags](./components/dialogue_state.md).
- **Internal parallelization** — Internal flows carry lightweight dependency annotations. The Agent parallelizes independent Internal tasks while preserving order for dependent ones. Internal flows operate as a lightweight swarm: each gets focused context, minimal tool access, and shares state only via the session scratchpad. See [Flow Stack § Concurrency Model](./components/flow_stack.md).

### Input Validation Routing

Pre-hook failures produce lightweight paths that skip the full pipeline:

| Failure point | What happens | Reference |
|---|---|---|
| NLU `prepare()` (7 checks) | No flow stacked; Agent passes rejection directly to RES | [NLU § Pre-Hook](./modules/nlu.md) |
| PEX `check()` (`has_issues`) | Flow already stacked; Agent receives control back | [PEX § Pre-Hook](./modules/pex.md) |

### Failure Handling

Two tiers of failure handling operate at different levels:

**Tier 1 — PEX repair loop** (within PEX `execute()`): When a new Frame is produced but has an error (`frame.error` is set), PEX attempts to repair it inline (up to 4 attempts). Repair strategies escalate: deterministic fixes first (regex-based corrections, parameter adjustments), then LLM-generated replacement queries. This handles code generation errors, empty results, broken dataframes, and similar execution failures. See [PEX § Execute](./modules/pex.md).

**Tier 2 — Agent-level cascade** (when no usable Frame was produced): When PEX returns without a valid Frame, or when PEX `recover()` declares ambiguity, the Agent chooses from three strategies in order:

1. **Re-route** — Send to NLU `contemplate()` to re-predict with a narrowed search space. See [NLU § Contemplate](./modules/nlu.md).
2. **Skip** — If inside a plan (`has_plan`), skip the failed step, set `keep_going`, continue to the next flow. See [Flow Stack § Failure Recovery](./components/flow_stack.md).
3. **Escalate** — If neither works (often General ambiguity), go to RES for user clarification.

## Core Components

1. **[Dialogue State](./components/dialogue_state.md)** — Grounds the agent in its beliefs. Tracks hierarchical predicted state (intents and flows), slot-filling, flow stack, and various control flags. Supports snapshots for rollback.

2. **[Flow Stack](./components/flow_stack.md)** — Stack-based data structure within the dialogue state for managing multiple workflows. Ensures a single active flow at all times; supports stacking, popping, and falling back.

3. **[Context Coordinator](./components/context_coordinator.md)** — Stores conversation history as structured turns (role, form, content). Provides retrieval utilities and checkpoint support for long-term storage.

4. **[Prompt Engineer](./components/prompt_engineer.md)** — Model-agnostic LLM interface. Handles streaming vs. regular responses, output parsing, guardrails (JSON, SQL, Python), and data preview formatting.

5. **[Display Frame](./components/display_frame.md)** — Decouples data transformation (policy's job) from data display (RES's job). Holds the core entities for the current turn that RES needs to render the correct views.

6. **[Ambiguity Handler](./components/ambiguity_handler.md)** — Declares, tracks, and resolves uncertainty at four levels: general, partial, specific, and confirmation. First-class citizen for agent reliability.

7. **[Memory Manager](./components/memory_manager.md)** — Three-tier cache hierarchy: Session Scratchpad (L1/L2, in-context), User Preferences (RAM, per-account), and Business Context (Hard Disk, per-client with vector retrieval).

## Utilities

Engineering constructs that live outside the agent.

1. **[Evaluation](./utilities/evaluation.md)** — E2E agent evaluation, runtime metrics, and user feedback. Continuous.
2. **[Server Setup](./utilities/server_setup.md)** — Server infrastructure: FastAPI app setup, middleware, and credentials.
3. **[Configuration](./utilities/configuration.md)** — Per-domain configuration with shared defaults. Startup-only, immutable.
4. **[Building Blocks](./utilities/blocks.md)** — Building blocks for creating a web app.
5. **[Flow Selection](./utilities/flow_selection.md)** — Compositional dact grammar and domain builder guide.

Also look into [hidden folder](./hidden/additional.md) for additional documentation.