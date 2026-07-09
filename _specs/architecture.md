# Overall Structure

We model the problem as a POMDP: the observation is the user utterance, the hidden variable is the user's
intent, and each state in the underlying MDP is a **flow** (historically, a dialogue act). The agent's job
each turn is to infer intent, advance the right flow, and ground itself in verifiable beliefs.

The system has **three levels**:

- **Level 0 — the main Agent.** Deterministic code (`Agent.take_turn`). It governs the turn: appends the user
  turn to the event stream, chooses the entry path, runs the module loop, persists belief, and delivers the
  turn's outputs. Being code, it is fast and predictable — the trustworthy frame around the model.
- **Level 1 — three continuous LLM-loops.** **[NLU](./modules/nlu.md)** understands (the Heart),
  **[PEX](./modules/pex.md)** acts (the Hands), and **[MEM](./modules/mem.md)** remembers (the Head). Each is
  its own loop with a distinct goal; they run **in parallel**, not as a fixed pipeline.
- **Level 2 — sub-agents.** PEX — and only PEX — goes deeper, activating per-flow **policies** as sub-agents.
  Sub-agents **cannot** open a fourth level; when one needs more work it **stacks on** a flow, which
  re-surfaces back at the PEX layer.

```
Level 0   main Agent  ── deterministic code (turn lifecycle, I/O, persistence)
              │ runs the turn
Level 1   ┌── NLU (Heart) ──┐   ┌── PEX (Hands) ──┐   ┌── MEM (Head) ──┐
          │ understands     │   │ acting loop      │   │ remember/retrieve
          │ ephemeral belief│   │ + sub-agent router│   │ durable record │
          └─────────────────┘   └────────┬─────────┘   └────────────────┘
                                          │ activate_flow (PEX only)
Level 2                          sub-agents (per-flow policies) — cannot nest deeper
```

> **Migration note.** Phoenix is the master spec for the **Charlie** assistant (the clean new
> implementation). **Hugo** retains the legacy deterministic pipeline as a reference until cutover. The two
> live side by side — see [Migration](#migration--charlie-vs-hugo).

## The Three Modules

| Module | Role | Goal | Read/Write skew | Owns |
|---|---|---|---|---|
| **[NLU](./modules/nlu.md)** | Heart | Theory of Mind about the user from words + actions | more writes (beliefs churn) | Dialogue State, Ambiguity Handler, Session Scratchpad |
| **[PEX](./modules/pex.md)** | Hands | complete tasks efficiently and reliably; produce the response | drives the acting loop | Workflow Planning, Policies, Tools/MCP, Task Artifact, Prompt Engineer |
| **[MEM](./modules/mem.md)** | Head | remember and retrieve at the right time, pro-actively | more reads than writes | Context Coordinator (L1), User Preferences (L2), Business Context (L3) |

Belief is split three ways: NLU's **Dialogue State** is *grounded, validated* belief (ontology-typed,
queryable); NLU's **Session Scratchpad** is *unvetted, working* belief (a minimal-schema ledger the swarm
shares); MEM is the *durable record* of what happened, what the user prefers, and what the business knows. A
benign user's uploaded knowledge (MEM) outranks the agent's own predictions (NLU) on conflict.

## The Turn (main Agent)

The main Agent runs every turn deterministically:

**Start** Append the user turn to the event stream, then gate NLU via **`understand(op=…)`** (the
Assistant's only NLU entry point):
- **Click** (a `dax`, no free text) → `await understand(op=react)` — fills required slots from the payload
  in code, no model loop.
- **Utterance, no active entity** → `await understand(op=think)` — PEX has no grounding to act on, so the
  Assistant blocks until NLU writes intent/flow/slots to belief (or declares ambiguity).
- **Utterance, active entity** → `understand(op=think)` on a **parallel thread** — PEX proceeds on the
  standing belief while NLU refines; the Assistant joins the thread at the turn boundary.

See [NLU § when the Assistant gates NLU](./modules/nlu.md). NLU writes its prediction into the Dialogue
State belief; the Assistant never calls `react`/`think`/`contemplate` directly, and NLU never stacks.

**Loop.** `PEX.execute()` (bounded to `_MAX_ROUNDS`) runs the model against the frozen system prompt, the
message list, and the tool catalog. It **reads the belief NLU wrote and decides by intent** — a read-only
tool; stage+activate that intent's **1:1 flow** (Research→`find`, Draft→`outline`, Revise→`polish`,
Publish→`release`); the chat policy (Converse); relay ambiguity (Clarify); or the Workflow Planner Skill
(Plan). It never re-detects. Each round emits tool calls and/or a user-facing message over the WebSocket,
then loops until it chooses to stop. `keep_going` is just whether PEX runs another round, not a menu choice.
Exhausting the round budget triggers one no-tools `_final_emit` wrap-up so completed work is never lost.

**End** Record the agent turn, persist `state.json`, run the compaction check,
and deliver the turn's [Task Artifact](#task-artifact-flow): a processed version to the user (through the
webserver) and a copy to MEM for long-term storage (through the World object).

```
Assistant.take_turn
│  pre-hook: ensure_session, append user turn, clear stale ambiguity
│
├─ Branch 1 — click ................. await NLU.understand(op=react) ──┐
├─ Branch 2 — utterance, no entity .. await NLU.understand(op=think) ──┤──► PEX.execute()
│                                                                      │
└─ Branch 3 — utterance, active entity:                                │
       NLU.understand(op=think) ──┐  run in PARALLEL                   │
       PEX.execute() ◄────────────┘  (races ok; thread joins at boundary)

PEX.execute() — reads the belief NLU wrote (pred_intent / pred_flows / pred_slots), then DECIDES:
   ├─ a read-only tool ............... execute it directly
   ├─ Plan ........................... fire the Workflow Planner SKILL   (FlowStack tracks progress)
   ├─ Clarify ........................ signal the Assistant → NLU.understand(op=think)
   ├─ Converse ....................... fire the chat policy (voice)
   └─ Research / Draft / Revise / Publish .. activate the intent's 1:1 flow

post-hook: record agent turn, save state, MEM.remember()
```

### What the loop owns vs. delegates
PEX owns **control** — the ask-vs-proceed decision, sequencing flows, and the spoken close (**coarse intent
is NLU's authoritative write**; PEX's own sense is internal reasoning, biased to Plan/Clarify under
uncertainty). It delegates **work** — understanding and belief writes (NLU), memory (MEM), and per-flow
execution to its sub-agents. It never calls a domain mutation directly; **all domain writes go through
`activate_flow`**.

## Tool Catalog

Tools are organized by call frequency.

**Hot-path** (tight schemas, called most turns):

| Tool | Surface | Role |
|---|---|---|
| `understand` | NLU · Dialogue State | read the four-block belief document (serialized: flow, intent, confidence, slots, grounding) |
| `classify_intent` / `detect_flow` / `fill_slots` | NLU · Dialogue State | record intent, the detected flow + candidates, slot values + grounding |
| `stackon` / `fallback` / `pop_completed` | PEX · Workflow Planner | push / replace / pop flows on the stack |
| `activate_flow` | PEX | promote a top-of-stack pending flow to active and run its policy as a sub-agent; returns the completion record |
| `complete_flow` | PEX · policy | mark the active flow Completed/Invalid (grounding-gated) |
| `append_to_scratchpad` / `read_from_scratchpad` | Session Scratchpad | append findings (triggers NLU) / read; `update_scratchpad` is NLU-only |

**Long-tail** (component skills): `handle_ambiguity` (NLU), `recap` / `recall` / `retrieve` reads + `store_preference` write (MEM).

**Read-only domain allowlist** (safe to call directly): `find_posts`, `read_metadata`, `read_section`,
`search_notes`, `list_channels`, `channel_status`. Every **mutating** domain action goes through
`activate_flow`.

## The State Substrate

Each conversation owns a session directory holding three artifacts.

**1. `state.json`** — the serialized Dialogue State, one document with **four blocks**: `session`,
`user_beliefs`, `grounding`, `flow_stack`. There is **no generic state-writer**; each fact is written by a
purpose-specific tool: `classify_intent` and `detect_flow` write `user_beliefs`; `fill_slots` writes slot
values and the `grounding` block (entity extraction is its sub-task); the Workflow Planner's `stackon` /
`fallback` / `pop_completed` and the policy's `complete_flow` write the `flow_stack`. The main Agent serializes
the document in its post-hook (`serialize()`) — persistence is deterministic code, not a tool. **One writer
per fact** preserves single-source-of-truth.

**2. `scratchpad.jsonl`** — the Session Scratchpad: append-only swarm beliefs and completion records, each
stamped with its `writer` (the loop or a flow name) **in code**, so authorship can never be forged by model
output. Parallel sub-agents write into it, so it is the surface exposed to **race conditions** — NLU is
triggered to review it on every update and keep it uncorrupted.

**3. `messages.jsonl`** — the persistent Anthropic-shaped message list. Reopening a conversation reloads
the transcript.

The **belief split**: the state file holds *grounded, validated* belief (NLU's Dialogue State); the scratchpad
holds *unvetted, working* belief (NLU's swarm ledger); MEM's Context Coordinator holds the *durable event
record*. The belief inside `state.json` is NLU's, written by NLU's own Dialogue State tools; the `flow_stack`
structure is PEX's Workflow Planner. MEM never writes the belief file — its durable write path is the
append-only event stream.

### Grounding — single source of truth
The `grounding` block — `{post, sec, snip, chl, ver}` — is the agent's anchor to the domain entities; `ver`
flags user-approved vs. agent-predicted. `fill_slots` writes the **predicted** grounding (`ver=False`);
verification flips `ver=True` only when PEX confirms it (user-approved or PEX-written). An **entity-grounded** flow (entity slot of type
`source`/`target`/`removal`/`channel`) **cannot reach `Completed` while `grounding.post` is empty** —
`complete_flow` raises. Validation lives at the one tool that can mark `Completed`; it does not silently patch.

## Context Management

MEM's [Context Coordinator](./components/context_coordinator.md) — the L1 event stream — is compacted as it
grows (Hermes-derived): a token threshold triggers compaction in the post-hook; head messages and a protected
tail (with intact `tool_use`/`tool_result` pairs) are preserved; the middle is summarized on the **LOW** model
tier into one reference-only handoff message; `messages.jsonl` is rewritten. A summarizer failure aborts
compaction without eating the turn's reply.

## The System Prompt (three tiers)

Built once per session and frozen:
- **Tier 1 — stable:** persona, the 7-intent taxonomy, tool policy, and loop discipline (ask-vs-proceed,
  `stackon`→`activate`, completion discipline, the read-only allowlist, no-tool-text-ends-turn).
- **Tier 2 — context:** the workflow recipe, the flow catalog grouped by intent, the outline levels.
- **Tier 3 — volatile:** the L2 user-preferences snapshot and the session line.

## Task Artifact Flow

Each active flow's sub-agent builds its own [Task Artifact](./components/task_artifact.md) — origin, parts,
blocks, thoughts. When a turn has several concurrent sub-agents, **PEX curates the N artifacts into one**:
blocks are merged in stack order and de-duplicated, a single-flow-type origin is kept (trivial when all
artifacts share one flow type), and a failed sibling is dropped and logged. Sub-agents **propose** their
blocks; curation defaults to passing them through with minimal change, and PEX rewrites from scratch only as a
summarization step for a clearer, more concise turn. The main Agent receives a **single** artifact per turn. **PEX composes the reply directly** — there is no separate naturalize step — via
a voice Skill, then the main Agent sends a **processed version to the user** (through the webserver) and **a
copy to MEM** for long-term storage (through the World object). The sub-agent declares *what* to show; PEX and
the frontend Blocks decide *how* to deliver it.

## Core Components

Nine components, grouped by owning module:

**NLU (Heart) — ephemeral belief**
1. **[Dialogue State](./components/dialogue_state.md)** — the structured, ontology-filled belief; file-backed,
   exposing the `classify_intent`/`detect_flow`/`fill_slots` tools over a four-block document.
2. **[Ambiguity Handler](./components/ambiguity_handler.md)** — declares / tracks / **resolves** uncertainty
   internally before asking; four levels (general, partial, specific, confirmation).
3. **[Session Scratchpad](./components/session_scratchpad.md)** — the minimal-schema working ledger for swarm
   communication; race-resolved by NLU review on every update.

**PEX (Hands) — action & rendering**
4. **[Workflow Planner](./components/workflow_planner.md)** — the FlowStack storage (code: `flow_stack.py`)
   plus the Workflow Planning / Sub-agent Routing activity; depth-16 bound, contiguous Active flows.
5. **[Task Artifact](./components/task_artifact.md)** — the A2A-aligned artifact (origin, parts/blocks,
   metadata, thoughts) a sub-agent builds and the main Agent delivers.
6. **[Prompt Engineer](./components/prompt_engineer.md)** — model-agnostic interface with a **tier
   abstraction** (`low`/`med`/`high` resolved against the active model family).

**MEM (Head) — durable memory**
7. **[Context Coordinator](./components/context_coordinator.md)** — the **L1** append-only event stream
   (user/agent/system events) + compaction and rolling summaries.
8. **[User Preferences](./components/user_preferences.md)** — the **L2** per-account defaults.
9. **[Business Context](./components/business_context.md)** — the **L3** per-client unstructured knowledge.

## Failure Handling

Failures surface as **corrective tool errors** inside the loop, not as exceptions: a malformed belief-tool call, an
unknown flow, a grounding violation, or an unknown slot name returns `{_success: False, _error, _message}`
that PEX reads and retries against. A failed tool (`_success=False`) is classified by the **policy** into the
closed 8-code **violation** vocabulary — there is no tool-level error taxonomy. A self-check failure then
**fans out** three ways: the sub-agent's [Task Artifact](#task-artifact-flow) records the violation, a
violation entry is appended to the [Session Scratchpad](./components/session_scratchpad.md) (which notifies
NLU), and the [Context Coordinator](./components/context_coordinator.md) logs a system action (which notifies
MEM). The bounded rounds, de-dup, consecutive-failure cap, and `_final_emit`
wrap-up are the loop-level guardrails. Sub-flow policies still repair their own tool errors internally before
returning.

## Utilities

1. **[Evaluation](./utilities/evaluation.md)** — the verification backbone: a **parity harness** (oracle
   fixtures + a three-axis comparator: end-state DB, grounding, LLM judge), a **trace dev set** (human-approved
   tool-call trajectories + tolerance rules), and a layered test pyramid.
2. **[Configuration](./utilities/configuration.md)** — per-domain config with shared defaults; startup-only.
3. **[Server Setup](./utilities/server_setup.md)** — FastAPI app, middleware, credentials.
4. **[Building Blocks](./utilities/blocks.md)** — building blocks for the web app.
5. **[Flow Selection](./utilities/flow_selection.md)** & **[Tool Smith](./utilities/tool_smith.md)** — the
   compositional dact grammar and the tool-design guide.

## Migration — Charlie vs. Hugo

Phoenix specifies **Charlie**, the clean three-level implementation. **Hugo** keeps the legacy deterministic
pipeline as a reference. The new system was proven against Hugo via the parity harness (0 crashes and 0
grounding issues across 42 oracle turns) before the split. Charlie was seeded as a copy of that proven tree;
the legacy execute paths, per-turn state plumbing, and old snapshots are scrubbed incrementally as Charlie is
built out against this spec.
