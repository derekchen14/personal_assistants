# PEX — Policy Execution Orchestrator (the Hands)

PEX takes the **actions** that interact with the outside world. Its goal is to complete tasks in an
**efficient and reliable** manner — even when the request is long or complex. PEX produces the user-facing
response and the progress messages; its triggered outputs form the **telemetry logs**.

PEX sits at the **middle level** of three:

- **Level 0 — the main Agent** (deterministic code): governs the turn lifecycle and delivers outputs. See
  [architecture](../architecture.md).
- **Level 1 — PEX** (this module): a continuous LLM-loop that runs the central tool-calling loop, consulting
  [NLU](nlu.md) (understand) and [MEM](mem.md) (remember) **in parallel**.
- **Level 2 — sub-agents**: the per-flow policies the runtime executes. They cannot nest deeper; a sub-agent that
  needs more work **stacks on** a flow, which re-surfaces at the PEX layer rather than spawning a fourth level.

PEX owns the agent loop, **[Workflow Planning / Sub-agent Routing](#workflow-planning--sub-agent-routing)**,
the **[Policies](#policies-run-by-the-runtime)**, the **[Tools and MCP](#tools-and-mcp)** it calls, and the
two surfaces it produces with — the **[Task Artifact](../components/task_artifact.md)** and the
**[Prompt Engineer](../components/prompt_engineer.md)**.

---

## The PEX Agent loop

`PEX.execute()` is PEX's tool-calling engine — the PEX Agent loop. The **Assistant** routes to PEX
*first*: the loop's opening reasoning move is a System-1 intent sense (PEX 1), which the Assistant
relays to [NLU](nlu.md) as the hint before detection starts. NLU's ensemble detection then runs in
parallel with the loop; `execute()` proceeds on the standing belief and picks up NLU's verdict as a
Session Scratchpad entry at the hook points (see
[hook points](#policy-hook-points--the-6-hook-sub-agent-framework)):

- **Click** → the Assistant runs `understand(op=react)`; the dax names the flow, so there is no
  detection and no agent loop — the resolved flow goes straight to the runtime.
- **Utterance, clear domain intent** → the intent maps to its basic flow (Converse→chat {000},
  Research→find {001}, Draft→outline {002}, Revise→write {003}, Publish→release {004} — the dax
  codes hold across domains; finer-grained flows are NLU's to choose) and `execute()` stacks and
  starts it without waiting.
- **Utterance, Plan or Clarify** → the only intents that wait: the first move is a belief read at
  hook point ①, blocking until NLU's settled belief lands.

**Intent selection — PEX's first step.** Given a new user turn, PEX's main job begins by committing to one
of the 8 intents. Each intent sets how the turn treats the (possibly still-running) parallel detection:

- **Plan** — wait on NLU, then kick off the Workflow Planner.
- **Clarify** — wait for NLU's predicted dialogue state, then send PEX's best guess to the Ambiguity
  Handler.
- **Continue** — legal only while an Active flow exists; advance that flow by handing it back to the
  runtime, without stacking or re-routing. The Active flow name is NLU's hint for this turn.
- **Converse** — map to `chat` {000}; it stacks and runs like any flow (the streamed reply is its
  execution), then pops and the flow beneath reactivates. No carve-out.
- **Research / Draft / Revise / Publish** — go directly to flow execution; the NLU update is optional at
  the hook points.

All 8 intents keep multiple hook points where NLU can come in. **Plan and Clarify are required to wait**
for NLU's response; the other six continue if NLU has not returned anything. When NLU has returned and
the predicted flow already matches the active flow, nothing needs to change — that is the speed-up. Since
95%+ of turns are Plan turns or some flow execution, NLU flow detection is almost always integrated into
the turn. One extra gate: when the stack already holds an Active flow and PEX 1 sensed a different flow,
the agent's next move (PEX 2) double-checks that selection with the Workflow Planner skill before
stacking over live work — prompt-only, the same agent that later resolves conflicts as PEX 5.

Inside the loop (`_run_loop`, bounded to `_MAX_ROUNDS`), PEX calls the model with a frozen three-tier system
prompt, the message list, and the tool catalog. Each round:

- Tool calls are validated against the catalog; identical consecutive calls are de-duplicated; a
  consecutive-failure cap (`_MAX_CORRECTIVE`) stops runaway error loops.
- A thinking-only response is nudged once, then falls back.
- **PEX decides `keep_going` each round.** Each round it emits a model response — **any number of tool calls
  and/or the turn's [TaskArtifact](../components/task_artifact.md)** (the main response) streamed over the
  WebSocket — then loops again until it chooses to stop. The moves in a round: **shape and advance the
  stack** (`update` / `stackon` / `fallback` / `pop` — policy execution follows the runtime-owned rules below),
  **consult or gather** (`understand`, MEM
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
its sub-agents. **All domain writes go through a flow's runtime-executed sub-agent** — never a
domain tool directly. The **[TaskArtifact](../components/task_artifact.md) is the main response to the user**;
PEX words it **directly** via a **voice Skill** in its system prompt over the turn's artifacts, tool results,
and sub-agent results. There is no separate naturalization step.

### Tool catalog (by call frequency)

| Tier | Tools | Surface |
|---|---|---|
| Hot-path | `understand` (ops `read` / `think` / `contemplate`) | the one belief tool: `read` returns the Dialogue State belief NLU wrote (intent, ranked flows, confidence, slots, grounding) and joins the parallel NLU thread; `think` re-runs detection; `contemplate` re-routes over a failed flow. NLU's `classify_intent`/`detect_flow`/`fill_slots` are **NLU-internal** — not PEX tools |
| Hot-path | `manage_flows` (ops `update` / `stackon` / `fallback` / `pop`) | the one flow tool. `stackon` runs by default (`active=true`; `active=false` queues), `fallback` runs its replacement, and `pop` removes all terminal tops then runs a surfaced Pending flow. An `update` that writes `status='Active'` manually re-runs that flow; slot-only updates do not. There is no `activate` op |
| Policy | `complete_flow` | the flow's **policy** marks itself done (grounding-checked) — not a PEX move |
| Hot-path | `scratchpad` (ops `read` / `append`) | [Session Scratchpad](../components/session_scratchpad.md) (`update_scratchpad` is NLU-only) |
| Long-tail | `handle_ambiguity` (NLU), `recap` / `recall` / `retrieve` + `store_preference` (MEM) | component skills |
| Domain (read-only) | `find_posts`, `read_metadata`, `read_section`, `search_notes`, `list_channels`, `channel_status` | safe to call directly |

Every **domain write** is reached only through `manage_flows`. The read-only allowlist lets PEX
gather context cheaply without a flow.

### Loop guardrails (Hermes tool-call hygiene)
Catalog validation, consecutive-call de-dup, the corrective cap, the thinking nudge, no-tool-text-ends-turn,
and `_final_emit` are the loop-level guardrails. Component/tool errors surface **as corrective tool results**
(`{_success: False, _error, _message}`), not exceptions — PEX reads them and retries.

### The system prompt
Built once per session and frozen:
- **Tier 1 — stable:** persona, the 8-intent taxonomy, tool policy, loop discipline.
- **Tier 2 — context:** the workflow recipe, the flow ontology grouped by intent, the outline levels.
- **Tier 3 — volatile:** the L2 user-preferences snapshot and the session line.

---

## Workflow Planning / Sub-agent Routing

Workflow Planning (equivalently, Sub-agent Routing) is the **activity PEX's LLM performs** to decide which
sub-agents to run, handle **fallbacks** and **stack-ons** (including contemplation and re-routing), and track
how far through a complex request the agent is. The flows themselves are stored in the **FlowStack** data
structure (code: `flow_stack.py`) — see [Workflow Planner](../components/workflow_planner.md) for the storage
model, the depth-16 bound, and the contiguous-active-flows rule.

**Multiple active flows can run in parallel** when their branches are independent; the stack is bounded to
prevent unbounded branching. Each executing sub-agent gets an **isolated context**, distinct from the central
PEX loop.

---

## Policies (run by the runtime)

`activate_flow(flow_name)` is internal runtime plumbing, not a planner tool. The runtime calls it after
`stackon` (unless `active=false`), `fallback`, and a `pop` that surfaces a Pending flow. PEX selecting
**Continue** also hands the already Active top flow to it; as a recovery path, an `update` status write to
`Active` does the same. It re-attaches the security and artifact checks, runs the per-intent policy, and on
completion writes a `{flow, summary, metadata}` **completion entry** to the scratchpad and returns it. A
non-completed run returns the flow status plus any pending clarification. Grounding comes from the state
file's grounding block; **all domain writes happen here**.

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
An executing sub-agent gets `flow.tools` (its domain tools) plus a fixed set of cross-module tools. It
**cannot directly run another flow** — there is no fourth level; it stacks on instead, which re-surfaces at
the PEX layer and is run by the runtime. A stacked-on flow is **run from scratch** on a later round — there is no suspended
coroutine; all cross-invocation state travels through the [scratchpad](../components/session_scratchpad.md).

**Talk to [NLU](nlu.md) (the Heart):**
- `scratchpad` op="append" — append a finding; this **triggers NLU to pay attention**, and is also how
  sub-agents and the PEX orchestrator communicate (paired with op="read").
- `understand` — read the Dialogue State; returns a serialized dict (flow name, intent, confidence, slots,
  grounding, and other relevant fields).
- `handle_ambiguity` — operate the Ambiguity Handler via its four methods: `declare` (recognize an ambiguity,
  level + observation + metadata), `is_present` (is there an unresolved ambiguity?), `ask` (generate the
  clarification text), `resolve` (clear it once answered).

**Talk to [MEM](mem.md) (the Head):**
- `recap` — trigger the Context Coordinator skill (L1 session events).
- `recall` — trigger the User Preferences skill (L2 account defaults).
- `retrieve` — trigger the Business Knowledge skill (L3), including KB + vector-DB retrieval.
- `store_preference(content, key=None)` — write a user preference to L2 (explicit "remember X" or onboarding/config).

A sub-agent never writes the belief file and never assembles the final turn artifact alone.

### Method-shape contract
Every policy follows one skeleton with a single exit:

```python
def <flow>_policy(self, flow, state, context, tools):
    # 1. Guard the entity slot — partial/general ambiguity returns early.
    # 2. Branch on slot state (most lines live here): specific ambiguity,
    #    a prerequisite stackon, or policy execution.
    # 3. Execute via llm_execute; classify tool_log; build the artifact.
    # 4. complete_flow(...) on success; leave Active on violation/ambiguity.
    return artifact
```

Completion goes through `complete_flow(flow, state, summary, metadata)` — the single call where a policy marks
a flow done. It sets the flow's `Completed` status (grounding-gated — an entity-grounded flow cannot complete
while `grounding` is empty, so the check fires here) and writes the completion entry.

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
`requires_approval`). `verify()` confirms the artifact is non-null, slots intact, and no duplicate flows.

### Policy hook points — the 6-hook sub-agent framework
`check()` and `verify()` are two of **six hook points** around a policy's sub-agent run. **Only PEX needs
the full set** — flows take **destructive** action; the NLU and MEM orchestrators get just two hooks (a
quick check before and after their LLM loop). The six: ① **pre-LLM** (≈ `check()`), ② **pre-tool-call**,
③ **post-tool-call**, ④ **tool-retry** (a pre-tool-call hook for retries only — ≈ `retry_tool`),
⑤ **post-LLM**, ⑥ **verification** (≈ `verify()`). Each is an interception point for an **NLU
signal** or a **user interrupt**.

**Plain names (2026-07-03):** ① is the **pre-flow** hook, ⑤+⑥ together are the **post-flow** hook, ②
(with ④ as its retry variant) is **pre-tool**, ③ is **post-tool**. These six are the complete set — the
work at `execute()` entry and the end-of-turn checkpoint is ordinary turn lifecycle, not a hook. Since both
the orchestrator loop and every sub-agent route tool calls through the same path, the pre/post-tool
hooks cover both levels from one place.

**Who waits on NLU (revised 2026-07-14):** on every utterance turn, NLU's detection runs in parallel
and the hooks are where its verdict comes in. **Plan and Clarify are required to wait**: their first
move is a belief read at hook point ①, which blocks until detection lands. **The other six intents
never block**: `execute()` stacks the intent's basic flow and starts the policy, and the hook ③/⑤
scratchpad read picks up NLU's verdict mid-flow. When NLU detected the same flow, nothing needs to
change — that is the speed-up.

**The scratchpad message (2026-07-14, round 3.4):** NLU ends its thinking (`validate`) by writing one
Session Scratchpad entry: an *aligned* entry when its detection matches the flow PEX is running, or an
entry *announcing* the different flow NLU has already stacked with `world.flows.stackon()`, carrying
its rationale. A hook point is a module-code read of the scratchpad that decides whether anything
warrants notifying the PEX agent; the entry is read at hook ③ (post-tool-call) or ⑤ (post-LLM),
whichever comes first. A different-intent top is handled by that code directly — the displaced policy
stops, the new top runs, and the agent is never notified. A same-intent conflict is the one thing
surfaced to the agent: PEX 5's `manage_flows` call decides at that hook — run the new flow, or pop it
and stay. Hook ⑥ occurs within the `verify()` function, where code pops Completed and Invalid flows deterministically;
PEX 5 never runs there. Any other issue during policy execution re-consults
`understand(op='contemplate')` (the narrowed failed-flow re-route), never `think()`. This replaces the
retired `inject_belief_state` context note.

**Signal = the scratchpad entry** (no separate channel): each hook reads the Session Scratchpad and
compares the top flow's intent to the displaced flow's — **aligned ⇒ go on**, **different intent ⇒
code re-routes**, **same-intent conflict ⇒ PEX 5 decides**. A **user interrupt** is **high** severity
and stops mid-task (its channel is **TODO**).

```
PEX picks a domain intent → stackon its selected flow → runtime runs its policy sub-agent
   ├─① pre-LLM hook ............ before the sub-agent starts
   │      ▼  sub-agent LLM loop:
   │      ├─② pre-tool-call hook ...... before a tool call   (④ tool-retry = pre-tool-call, retries only)
   │      ├─ [tool executes]
   │      └─③ post-tool-call hook ..... after a tool call
   │      ▼
   ├─⑤ post-LLM hook ........... after the sub-agent completes
   └─⑥ verification hook ....... end of policy, after verification
        each hook ↯ scratchpad read — aligned: go on · diff intent: code re-routes · same-intent conflict: PEX 5
```

### Plan policy
There is **no Plan policy** — Plan decomposition and sequencing are the **Workflow Planner's** job, not a
sub-agent's. PEX's Workflow Planner decomposes a complex task into sub-flows rather than calling a tool. It
generates a freeform plan (shared with the user) and a structured plan (stored on the state, not the
scratchpad — the structure must survive); on approval it queues the sub-flows in reverse execution order
with sequential `stackon(active=false)` calls, then pushes the first-to-run flow with the default
`active=true`. The stack itself therefore holds the plan (observable by any agent; survives orchestrator
mistakes and compaction), with one Active flow on top and the remaining steps Pending beneath it. The loop
drives sub-flow sequencing and mid-plan replanning, reading sub-flow results from their completion entries in
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
notifies [MEM](mem.md). This is the error channel that replaces the removed `has_issues` field.

When a failure looks like *wrong flow detection*, PEX re-consults [NLU `contemplate`](nlu.md) with a narrowed
search space; a true sibling mismatch uses the Workflow Planner's `fallback`. **Tool-down is never an ambiguity
question for the user.**

---

## Tools and MCP

Tools are the deterministic action surface PEX calls — a Python function or a single-prompt LLM call, and
sometimes just a call to an **MCP server**. This surface is where general capability lives: the read-only and
component tools in the catalog above, called directly when no domain write is involved. Access is
**two-tier**: the orchestrator loop reaches the cross-module/component tools and the read-only domain
allowlist directly, while **domain-writing tools are flow-scoped** — callable only inside the sub-agent whose
policy declares them. Component skills (`understand`, scratchpad, MEM) sit in both tiers. Tool design (the
compositional dact grammar, tight schemas) lives in [Tool Smith](../utilities/tool_smith.md).

---

## Task Artifact & rendering

Each executing **sub-agent** builds its own **[Task Artifact](../components/task_artifact.md)** — origin,
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
