# PEX — Policy Execution Orchestrator (the Hands)

PEX takes the **actions** that interact with the outside world. Its goal is to complete tasks in an
**efficient and reliable** manner — even when the request is long or complex. PEX produces the user-facing
response and the progress messages; its triggered outputs form the **telemetry logs**.

PEX sits at the **middle level** of three:

- **Level 0 — the main Agent** (deterministic code): governs the turn lifecycle and delivers outputs. See
  [architecture](../architecture.md).
- **Level 1 — PEX** (this module): a continuous LLM-loop that runs the central tool-calling loop, consulting
  [NLU](nlu.md) (understand) and [MEM](mem.md) (remember) **in parallel**.
- **Level 2 — sub-agents**: the per-flow policies PEX activates. They cannot nest deeper; a sub-agent that
  needs more work **stacks on** a flow, which re-surfaces at the PEX layer rather than spawning a fourth level.

PEX owns the acting loop, **[Workflow Planning / Sub-agent Routing](#workflow-planning--sub-agent-routing)**,
the **[Policies](#policies-run-via-activate_flow)**, the **[Tools and MCP](#tools-and-mcp)** it calls, and the
two surfaces it produces with — the **[Task Artifact](../components/task_artifact.md)** and the
**[Prompt Engineer](../components/prompt_engineer.md)**.

---

## The acting loop

`PEX.execute()` is PEX's tool-calling engine — the acting loop the **Assistant** calls *after* it has gated
NLU at turn entry (see [NLU § when the Assistant gates NLU](nlu.md)). By then NLU has written its prediction
(intent, ranked flows, confidence, slots) into the Dialogue State belief, so `execute()` **reads the belief
and decides by intent** — it does not re-detect:

- **Click** → the Assistant already ran `understand(op=react)`; `execute()` finds the resolved flow in
  belief and activates it.
- **Utterance, no active entity** → the Assistant awaited `understand(op=think)`; the detection is in belief
  before `execute()` runs.
- **Utterance, active entity** → `understand(op=think)` runs on a **parallel thread** while `execute()`
  proceeds on the standing belief; the pre-tool hook joins the thread on a belief read (the Plan/Clarify
  wait), flow execution picks up a landed detection without blocking (see
  [hook points](#policy-hook-points--the-6-hook-sub-agent-framework)), and the turn boundary joins
  whatever remains.

**Intent dispatch — PEX's first step.** Given a new user turn, PEX's main job begins by committing to one
of the 7 intents. Each intent sets how the turn treats the (possibly still-running) parallel detection:

- **Plan** — wait on NLU, then kick off the Workflow Planner.
- **Clarify** — wait for NLU's predicted dialogue state, then send PEX's best guess to the Ambiguity
  Handler.
- **Converse** — prepare the params, call any tools as needed, then respond directly.
- **Research / Draft / Revise / Publish** — go directly to flow execution; the NLU update is optional at
  the hook points.

All 7 intents keep multiple hook points where NLU can come in. **Plan and Clarify are required to wait**
for NLU's response; the other five continue if NLU has not returned anything. When NLU has returned and
the predicted flow already matches the active flow, nothing needs to change — that is the speed-up. Since
95%+ of turns are Plan turns or some flow activation, NLU flow detection is almost always integrated into
the turn.

Inside the loop (`_run_loop`, bounded to `_MAX_ROUNDS`), PEX calls the model with a frozen three-tier system
prompt, the message list, and the tool catalog. Each round:

- Tool calls are validated against the catalog; identical consecutive calls are de-duplicated; a
  consecutive-failure cap (`_MAX_CORRECTIVE`) stops runaway error loops.
- A thinking-only response is nudged once, then falls back.
- **PEX decides `keep_going` each round.** Each round it emits a model response — **any number of tool calls
  and/or the turn's [TaskArtifact](../components/task_artifact.md)** (the main response) streamed over the
  WebSocket — then loops again until it chooses to stop. The moves in a round: **activate a flow**
  (`activate_flow` — promote top-of-stack pending flow(s) to active and run their sub-agents), **shape the
  stack** (`stackon` / `fallback` / `pop_completed`), **consult or gather** (`understand`, MEM
  `recall`/`recap`/`retrieve`, the scratchpad, `handle_ambiguity`, the read-only domain allowlist), and
  **respond to the user**. `complete_flow` is **not** a PEX move — each flow's policy completes itself.
  `keep_going` isn't a menu choice — it's just whether PEX runs another round.
- Exhausting the round budget or the corrective cap triggers a single no-tools `_final_emit` wrap-up, so
  completed work is never buried behind a canned fallback.

When the turn ends, the main Agent's post-hook records the agent turn, persists state, runs
the compaction check, and delivers the [Task Artifact](#task-artifact--rendering) (below).

### Owns vs. delegates
PEX owns **control** — the ask-vs-proceed decision, sequencing flows (via the Workflow Planner Skill over the
FlowStack), and the spoken close. **Coarse intent is NLU's authoritative write** — PEX's own intent sense is
internal reasoning, biased to Plan/Clarify under uncertainty, and is never committed to belief. It delegates
**work** — understanding and belief writes ([NLU](nlu.md)), memory ([MEM](mem.md)), and per-flow execution to
its sub-agents. **All domain mutations go through an activated flow's sub-agent** (`activate_flow`) — never a
domain tool directly. The **[TaskArtifact](../components/task_artifact.md) is the main response to the user**;
PEX words it **directly** via a **voice Skill** in its system prompt over the turn's artifacts, tool results,
and sub-agent results. There is no separate naturalization step.

### Tool catalog (by call frequency)

| Tier | Tools | Surface |
|---|---|---|
| Read | `read_state` | reads the Dialogue State belief NLU wrote (intent, ranked flows, confidence, slots, grounding). NLU's `classify_intent`/`detect_flow`/`fill_slots` are **NLU-internal** — not PEX tools; `understand` is the Assistant→NLU entry, not a PEX tool |
| Hot-path | `stackon`, `fallback`, `pop_completed` | PEX — Workflow Planner stack ops |
| Hot-path | `activate_flow` | PEX — promote top-of-stack pending flow(s) to active, run their sub-agents |
| Policy | `complete_flow` | the flow's **policy** marks itself done (grounding-gated) — not a PEX move |
| Hot-path | `append_to_scratchpad`, `read_scratchpad` | [Session Scratchpad](../components/session_scratchpad.md) (`update_scratchpad` is NLU-only) |
| Long-tail | `handle_ambiguity` (NLU), `recap` / `recall` / `retrieve` + `store_preference` (MEM) | component skills |
| Domain (read-only) | `find_posts`, `read_metadata`, `read_section`, `search_notes`, `list_channels`, `channel_status` | safe to call directly |

Every **mutating** domain action is reached only through `activate_flow`. The read-only allowlist lets PEX
gather context cheaply without a flow.

### Loop guardrails (Hermes tool-call hygiene)
Catalog validation, consecutive-call de-dup, the corrective cap, the thinking nudge, no-tool-text-ends-turn,
and `_final_emit` are the loop-level guardrails. Component/tool errors surface **as corrective tool results**
(`{_success: False, _error, _message}`), not exceptions — PEX reads them and retries.

### The system prompt
Built once per session and frozen:
- **Tier 1 — stable:** persona, the 7-intent taxonomy, tool policy, loop discipline.
- **Tier 2 — context:** the workflow recipe, the flow catalog grouped by intent, the outline levels.
- **Tier 3 — volatile:** the L2 user-preferences snapshot and the session line.

---

## Workflow Planning / Sub-agent Routing

Workflow Planning (equivalently, Sub-agent Routing) is the **activity PEX's LLM performs** to decide which
sub-agents to run, handle **fallbacks** and **stack-ons** (including contemplation and re-routing), and track
how far through a complex request the agent is. The flows themselves are stored in the **FlowStack** data
structure (code: `flow_stack.py`) — see [Workflow Planner](../components/workflow_planner.md) for the storage
model, the depth-16 bound, and the contiguous-active-flows rule.

**Multiple active flows can run in parallel** when their branches are independent; the stack is bounded to
prevent unbounded branching. Each activated sub-agent gets an **isolated context**, distinct from the central
PEX loop.

---

## Policies (run via `activate_flow`)

`activate_flow(flow_name)` promotes the top-of-stack pending flow to active and runs its policy as a
**sub-agent**. It puts the flow on top of the live stack (live-stack
hit, else reload from the state file, else `stackon`), re-attaches the security and artifact checks, runs
the per-intent policy, and on completion writes a `{flow, summary, metadata}` **completion record** to the
scratchpad and returns it. A non-completed run returns the flow status plus any pending clarification.
Grounding comes from the state file's grounding block; **all domain writes happen here**.

Each policy is defined by three things:

- **Instructions** — the per-flow skill prompt + starter.
- **Guardrails** — the pre-hook `check()` and post-hook `verify()` invariants below.
- **Verification criteria** — per-flow success checks beyond the closed violation set; deliberately a place to
  grow much more robust.

### Policy organization
**Net five policy files per domain.** Converse is **one** sub-agent — a single `converse` policy handles all
its flows, not one per flow. The four domain intents (e.g., Hugo: `research`, `draft`, `revise`, `publish`)
keep **per-flow** sub-agents, one policy file each. **Plan has no policy** — the Workflow Planner decomposes
and sequences it directly (see [Plan policy](#plan-policy) below). **Clarify has no policy** — it is an
NLU-only label, never a flow or sub-agent. Flows within a file are domain-specific even when structurally
similar across domains.

### Flows are agentic; deterministic operations are tools
Every flow is an **agentic sub-agent** — it reasons over a skill prompt and selects from its tools. There is
no deterministic-flow path: a purely deterministic operation (a calculator, a formatter, a single derivable
API call) is a **tool**, not a flow. A flow's skill lives at `backend/prompts/pex/skills/<flow>.md` with a
starter at `.../starters/<flow>.py`; the policy calls `llm_execute`, which runs the skill's tool loop and
returns `(text, tool_log)`, then reads the trajectory to verify persistence and build the artifact. The skill
owns persistence — the policy never double-writes behind it.

### Sub-agent toolset
An activated sub-agent gets `flow.tools` (its domain tools) plus a fixed set of cross-module tools. It
**cannot activate another flow** — there is no fourth level; it stacks on instead, which re-surfaces at the
PEX layer. A stacked-on flow is **re-activated from scratch** on a later round — there is no suspended
coroutine; all cross-invocation state travels through the [scratchpad](../components/session_scratchpad.md).

**Talk to [NLU](nlu.md) (the Heart):**
- `append_to_scratchpad` — append a finding; this **triggers NLU to pay attention**, and is also how
  sub-agents and the PEX orchestrator communicate (paired with `read_scratchpad`).
- `understand` — read the Dialogue State; returns a serialized dict (flow name, intent, confidence, slots,
  grounding, and other relevant fields).
- `handle_ambiguity` — operate the Ambiguity Handler via its four methods: `declare` (record an ambiguity,
  level + observation + metadata), `present` (is there an unresolved ambiguity?), `ask` (generate the
  clarification text), `resolve` (clear it once answered).

**Talk to [MEM](mem.md) (the Head):**
- `recap` — trigger the Context Coordinator skill (L1 session events).
- `recall` — trigger the User Preferences skill (L2 account defaults).
- `retrieve` — trigger the Business Context skill (L3), including KB + vector-DB retrieval.
- `store_preference(content, key=None)` — write a user preference to L2 (explicit "remember X" or onboarding/config).

A sub-agent never writes the belief file and never assembles the final turn artifact alone.

### Method-shape contract
Every policy follows one skeleton with a single exit:

```python
def <flow>_policy(self, flow, state, context, tools):
    # 1. Guard the entity slot — partial/general ambiguity returns early.
    # 2. Branch on slot state (most lines live here): specific ambiguity,
    #    a prerequisite stackon, or activate.
    # 3. Dispatch via llm_execute; classify tool_log; build the artifact.
    # 4. complete_flow(...) on success; leave Active on violation/ambiguity.
    return artifact
```

Completion goes through `complete_flow(flow, state, summary, metadata)` — the single call where a policy marks
a flow done. It sets the flow's `Completed` status (grounding-gated — an entity-grounded flow cannot complete
while `grounding` is empty, so the check fires here) and writes the completion record.

### Closed violation vocabulary (8 codes)
Cite by name; never extend without explicit approval. Specifics go in `thoughts` (prose) or `code` (raw
payload) — never in nested-underscore metadata keys.

| Code | Fires when |
|---|---|
| `failed_to_save` | a persistence tool ran but produced no effect |
| `scope_mismatch` | the flow ran at the wrong granularity |
| `missing_reference` | a slot entity doesn't exist on the post |
| `parse_failure` | skill output couldn't be parsed |
| `empty_output` | skill returned nothing when prose was expected |
| `invalid_input` | a tool rejected (or would reject) the arguments |
| `conflict` | two slot values contradict |
| `tool_error` | a deterministic tool returned `_success=False` |

### Pre-hook `check()` and post-hook `verify()`
`check()` validates cheaply before spending tokens: active flow on top, policy registered, required slots
filled, elective groups satisfied, tool manifest resolves, and the **Lethal Trifecta** gate (any tool with
all three of `accesses_private_data` + `receives_untrusted_input` + `communicates_externally` forces
`requires_approval`). `verify()` confirms the artifact is non-null, slots intact, no duplicate flows, flags
coherent.

### Policy hook points — the 6-hook sub-agent framework
`check()` and `verify()` are two of **six hook points** around a policy's sub-agent run. **Only PEX needs
the full set** — flows take **destructive** action; the NLU and MEM orchestrators get just two hooks (a
quick check before and after their LLM loop). The six: ① **pre-LLM** (≈ `check()`), ② **pre-tool-call**,
③ **post-tool-call**, ④ **tool-retry** (a pre-tool-call hook for retries only — ≈ `retry_tool`),
⑤ **post-LLM**, ⑥ **verification** (≈ `verify()`). Each is an interception point for an **NLU signal** or a
**user interrupt**.

**Plain names (2026-07-03):** ① is the **pre-flow** hook, ⑤+⑥ together are the **post-flow** hook, ②
(with ④ as its retry variant) is **pre-tool**, ③ is **post-tool**. These six are the complete set — the
work at `execute()` entry and the end-of-turn checkpoint is ordinary turn lifecycle, not a hook. Since both
the orchestrator loop and every sub-agent route tool calls through the same dispatch, the pre/post-tool
hooks cover both levels from one place.

**Who waits on NLU (2026-07-03):** on the parallel-think path (utterance + active entity), the hooks are
where this turn's detection comes in. **Plan and Clarify are required to wait**: their first move is a
belief read (`read_state`), and the pre-tool hook joins the NLU thread there — the read blocks until
detection lands. **The other five intents never block**: flow execution's pre-flow hook only picks up a
detection that has already landed (NLU still running → the flow proceeds on standing belief). When the
predicted flow already matches the active flow, nothing needs to change — that is the speed-up. The
turn-boundary join settles whatever remains.

**Belief state injection (2026-07-03):** once per turn, the landed detection (intent, top flows +
confidence, slots) is injected into the orchestrator's context — mismatch or not. Injection is attempted
at hooks ② pre-tool-call, ③ post-tool-call, ④ tool-retry, and ⑤ post-LLM until it succeeds once; ①
pre-LLM is too early (NLU has usually not answered yet) and ⑥ verification is too late (the work is
already done). None of these hook points force an NLU response — each checks briefly whether NLU has
completed, incorporates what NLU has to say if so, and otherwise continues. This is in contrast to the
injection points caused by Plan and Clarify, which require awaiting NLU. After injection: the predicted
flow differs but the intent matches → the ORCHESTRATOR decides whether to continue the original flow or
go with NLU's proposal, deferring to NLU in most cases (80%+); the predicted INTENT differs → code
forces a FALLBACK — the active flow is marked Invalid (never returned to) and NLU's detection takes
over as Active. Any other issue during policy execution
re-consults `nlu.contemplate()` (the narrowed failed-flow re-route), never `think()`.

**Signal = read from belief** (no separate channel — the Dialogue State is the single source of truth):
each hook reads `pred_intent` (NLU writes it on the branch-3 parallel `think()`) and compares it to the
**active flow's intent** — **differs ⇒ medium** severity, **aligns ⇒ low**. A **user interrupt** is
**high** (its channel is **TODO**). Severity → **stop** (mid-task; high) | **go on** (low) | reconsider
(medium — bespoke per situation).

```
PEX picks a domain intent → its 1:1 default flow → activate → policy spins up a sub-agent
   ├─① pre-LLM hook ............ before the sub-agent starts
   │      ▼  sub-agent LLM loop:
   │      ├─② pre-tool-call hook ...... before a tool call   (④ tool-retry = pre-tool-call, retries only)
   │      ├─ [tool executes]
   │      └─③ post-tool-call hook ..... after a tool call
   │      ▼
   ├─⑤ post-LLM hook ........... after the sub-agent completes
   └─⑥ verification hook ....... end of policy, after verification
        each hook ↯ NLU signal (read pred_intent vs active flow) / user interrupt →  STOP | GO ON
```

### Plan policy
There is **no Plan policy** — Plan decomposition and sequencing are the **Workflow Planner's** job, not a
sub-agent's. PEX's Workflow Planner decomposes a complex task into sub-flows rather than calling a tool. It
generates a freeform plan (shared with the user) and a structured plan (stored on the state, not the
scratchpad — the structure must survive); on approval it `stackon`s ALL sub-flows at once — reverse execution order, first-to-run pushed last as the one Active flow, the rest waiting as Pending — so the stack itself holds the plan (observable by any agent; survives orchestrator mistakes and compaction). The loop
drives sub-flow sequencing and mid-plan replanning, reading sub-flow results from their completion records in
the scratchpad. See [Workflow Planner § Plan Flow Lifecycle](../components/workflow_planner.md).

### Failure channels & recovery
Three distinct channels — never conflated:

| Failure | Channel |
|---|---|
| Tool-call failure (network, API, `_success=False`) | error artifact (`tool_error`); retry once if transient |
| Ambiguous intent (missing slot, unresolved entity) | `handle_ambiguity` — PEX asks |
| Malformed skill output | error artifact (`parse_failure`) |

Tools return a `{_success: bool}` dict (with `_error` / `_message` on failure) — there is no
`status` / `error_category` / `retryable` taxonomy. A tool that returns `_success=False` is **classified by
the policy** into the closed 8-code violation vocabulary on the artifact (`tool_error`, etc.); the result
itself carries no severity field.

A **self-check / `verify()` failure** fans out across three surfaces so each consumer learns of it: (1) a
`TaskArtifact` carrying the `violation` in its classification dict, (2) an appended **Session-Scratchpad**
violation entry, which notifies [NLU](nlu.md), and (3) a **Context Coordinator** system-action event, which
notifies [MEM](mem.md). This is the error channel that replaces the removed `has_issues` flag.

When a failure looks like *wrong flow detection*, PEX re-consults [NLU `contemplate`](nlu.md) with a narrowed
search space; a true sibling mismatch uses the Workflow Planner's `fallback`. **Tool-down is never an ambiguity
question for the user.**

---

## Tools and MCP

Tools are the deterministic action surface PEX calls — a Python function or a single-prompt LLM call, and
sometimes just a call to an **MCP server**. This surface is where general capability lives: the read-only and
component tools in the catalog above, called directly when no domain mutation is involved. Access is
**two-tier**: the orchestrator loop reaches the cross-module/component tools and the read-only domain
allowlist directly, while **mutating domain tools are flow-scoped** — callable only inside the sub-agent whose
policy declares them. Component skills (`understand`, scratchpad, MEM) sit in both tiers. Tool design (the
compositional dact grammar, tight schemas) lives in [Tool Smith](../utilities/tool_smith.md).

---

## Task Artifact & rendering

Each activated **sub-agent** builds its own **[Task Artifact](../components/task_artifact.md)** — origin,
parts, blocks, thoughts. When several flows are active in one turn, PEX **curates** the sibling artifacts into
a **single** TaskArtifact (stack order, dedup identical blocks; see
[Task Artifact § Lifecycle](../components/task_artifact.md#artifact-lifecycle)) and hands it up to the main
Agent. The sub-agents **propose** the blocks; curation defaults to passing them through (ordered, deduped)
with minimal change — PEX authors blocks from scratch only as an optional summarization step for a clearer,
more concise turn. The main Agent then sends a processed version to the user (through the webserver) and a copy to
[MEM](mem.md) for long-term storage (through the World object). PEX composes the spoken reply directly from
these artifacts plus the tool and sub-agent results via a **voice Skill** in its system prompt — there is no
naturalization tool. Every model call PEX or its sub-agents make routes through the
**[Prompt Engineer](../components/prompt_engineer.md)** (tier abstraction, caching, retry, structured-output
parsing).
