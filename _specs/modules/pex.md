# PEX — Policy Execution Orchestrator (the Hands)

PEX takes the **actions** that interact with the outside world. Its goal is to complete tasks in an
**efficient and reliable** manner — even when the request is long or complex. PEX produces the user-facing
response and the progress messages; its triggered outputs form the **telemetry logs**.

PEX sits at the **middle level** of three:

- **Main Assistant** (deterministic code): governs the turn lifecycle and delivers outputs. See
  [architecture](../architecture.md).
- **PEX agent** (this module): a thin code wrapper around a continuous agent-loop that runs the central tool-calling loop, consulting [NLU](nlu.md) (understand) and [MEM](mem.md) (remember) **in parallel**.
- **Sub-agents**: the per-flow policies the runtime executes. They cannot nest deeper; a sub-agent that
  needs more work **stacks on** a flow, which re-surfaces at the PEX layer rather than spawning a fourth level.

PEX owns the agent loop, **[Workflow Planning / Sub-agent Routing](#workflow-planning--sub-agent-routing)**,
the **[Policies](#policies-run-by-the-runtime)**, the **[Tools and MCP](#tools-and-mcp)** it calls, and the
two surfaces it produces with — the **[Task Artifact](../components/task_artifact.md)** and the
**[Prompt Engineer](../components/prompt_engineer.md)**.

---

## One turn through PEX — pseudo-code

Two agentic loops run inside PEX (the Assistant above them is deterministic code):

1. the **PEX Agent** — triggered by `pex.orchestrate()`; the PEX module is a thin code
   wrapper around this agent.
2. the **policy sub-agent** — triggered by `pex.execute()`; the policy is the code wrapper
   around the sub-agent.

Tools, policies, and MCP servers are treated identically, so the verb is **call**: the three
services are `call_tool()`, `call_policy()`, and `call_mcp()`, and each returns a
`{_success: bool, ...}` dict. `prepare()` is PEX's first step of every turn; `verify()` is the
last step of every sub-agent run.

Both loops make model rounds the same way: `engineer(...)` is the single round primitive — one
call, one model round. PEX owns its loop and calls it once per `orchestrate()`; a policy wants a
finished run, so `flow_execute` loops the same primitive inside the engineer and returns
`(text, tool_log)`.

**Standardization.** Every predictor — a user action (golden dax), the TypeSafe model, NLU's
ensemble — writes the same belief: `state.pred_intent` and `state.pred_flows`, mapped to flows at
prediction time. `prepare()` looks nothing up and stacks nothing; the PEX agent stays the main
driver, stacking and running flows through `manage_flows`. Nothing downstream knows which
predictor made the prediction.

### The Assistant drives the turn

```python
def take_turn(text, dax=None, payload={}):
    context.add_turn('user', content)              # kind 1 (utterance) or kind 2 (click)
    if dax:
        nlu.react(dax, payload)                    # golden dax — stacks the named flow, fills slots
    else:
        state.classify_intent(engineer, context)   # TypeSafe — writes pred_intent + pred_flows
        spawn nlu.think(text)                      # ensemble — worker thread, may re-stack mid-turn

    pex.prepare()                                  # first step — hook point 1
    while state.keep_going:
        if contemplation_requested():              # 3.4.7 — a policy stalled and asked to re-route
            nlu.contemplate()                      # NLU re-detects over the failed flow; the agent
                                                   #   runs the re-stacked flow next round
        reply = pex.orchestrate()                  # one PEX-Agent round; '' until the terminal round
    mem.recap(reply, ...)                          # records the reply turn (kind 3); MEM stores
                                                   #   Completed flows only, never Invalid ones
```

### prepare() — PEX's first step (hook point ①)

```python
def prepare():
    recently_finished, reads = [], 0               # every flow popped this turn — Completed or Invalid
    turn_start = context.num_utterances
    state.keep_going, rounds = True, 0             # True until the terminal emit words the reply
    if state.pred_intent in ('Plan', 'Clarify'):   # the only intents that wait on NLU
        wait(nlu_done, timeout=30)                 # expiry raises — the turn fails loudly
    pred_flow = state.pred_flows[0]                # mapped at prediction time — no lookup, no stackon
    if the user turn is an action:                 # golden dax — react() already stacked it; force it
        note = (f"[click] The user selected '{pred_flow}' directly. You MUST run it as your "
                f"next step with manage_flows (update status='Active').")
    else:                                          # TypeSafe — a prediction the agent may override
        note = (f"[typesafe] intent={state.pred_intent} — the predicted flow is '{pred_flow}'. "
                f"Stack and run it with manage_flows (op='stackon'), pick a different flow, or "
                f"reply directly.")
    context.add_turn('system', {'text': note})     # kind 5 — round 1 sees the prediction
```

### execute() — run Flow sub-agents until the stack settles

Called only from inside a `manage_flows` call, whenever an op surfaces runnable work (stackon,
fallback, a promoting pop, a status write of 'Active').

```python
def execute(start=None):
    curr_flow = start or flow_stack.get_flow()
    while curr_flow and curr_flow.status in ('Pending', 'Active'):
        curr_flow.status = 'Active'
        state.ground_flow(curr_flow)               # fills only EMPTY entity slots; idempotent
        if security_check(curr_flow):              # lethal-trifecta gate → confirmation block
            return approval_result                 # no sub-agent run
        artifact = call_policy(curr_flow)          # ← the policy sub-agent runs inside
        check = verify(artifact, curr_flow)        # last step — hook point 6
        wait(nlu_done, timeout=30)                 # hook point 3 — NLU may have re-stacked
        if curr_flow.status == 'Completed':
            popped = pop Completed and Invalid flows   # in code, never the agent's job
            recently_finished += popped            # every popped flow — Completed or Invalid
            surface next_flow + NLU's note in the tool result
            break
        prev_flow, curr_flow = curr_flow, flow_stack.get_flow()
        if curr_flow is prev_flow:
            break                                  # stall (question or violation) — agent decides
        if curr_flow.intent == prev_flow.intent:
            surface NLU's announcement; break      # same-intent conflict — PEX 5 decides
        # different intent — code re-routes silently; the loop continues on curr_flow
    return the policy result as the manage_flows tool result
```

### call_policy() — the code wrapper around one sub-agent run

```python
def call_policy(flow):
    policy = policies[flow.intent]                 # five policy objects per domain
    return policy.<flow>_policy(flow, state, context, call_tool)

def <flow>_policy(flow, state, context, tools):    # the one skeleton every policy follows
    if not flow.slots[flow.entity_slot].filled:    # 1. guard the entity slot
        ambiguity.recognize('partial')
        return TaskArtifact(flow.name())
    # 2. branch on slot state — specific ambiguity, a prerequisite stackon, or execution
    text, tool_log = llm_execute(flow, ...)        # 3. the sub-agent LLM loop: skill + starter +
                                                   #    flow.tools; every call routes through
                                                   #    call_tool (hook points 2 / 3 / 4)
    artifact = classify(text, tool_log)            #    violations from the closed 8-code set
    if succeeded:
        complete_flow(flow, summary, metadata)     # 4. the policy completes itself
    return artifact
```

### orchestrate() — one PEX-Agent round

```python
def orchestrate():
    rounds += 1
    response = engineer(system_prompt, context.compile_messages(), family='claude',
                        tier='high', tools=catalog, max_tokens=4096)
    text, tool_uses = split(response)

    if not tool_uses:
        if text:
            wait(nlu_done, timeout=30)             # hook point 5 — post-LLM, no tools ran
            if unconsumed_nlu_announcement():
                record text as a kind-4 turn; append the note as a system turn
                return ''                          # PEX 5 — one more round to decide
            state.keep_going = False               # terminal round — the turn is worded
            return text                            # the reply is PEX's final result
        nudge once (system turn); a second miss goes through _final_emit() — the wrap-up call
        return ''

    results = [call_tool(tu.name, tu.input) for tu in tool_uses]
    # a manage_flows op that surfaces runnable work calls execute() inline; its policy
    # result IS the tool result
    context.add_turn('agent', {text, tool_uses, results}, 'action')  # one kind-4 turn per round
    if a flow completed this round: rounds = 0     # every plan step starts a fresh budget
    if rounds == max_rounds or corrective_cap_hit:
        state.keep_going = False
        return _final_emit()                       # one no-tools wrap-up call — the reply
    return ''                                      # mid-turn round — no reply yet
```

### call_tool() / call_mcp() — the uniform call surface

```python
def call_tool(name, args):                         # every tool call, both levels, one guard site
    if name not in catalog:                  return corrective('invalid_input')
    if identical_to_last_successful_call:    return corrective('duplicate_call')
    if read_only_tool and reads >= max_reads: return corrective('read_cap')
    if catalog[name].served_by_mcp:
        return call_mcp(catalog[name].server, name, args)
    try:
        return bound_method(**args)                # services return {_success, ...}
    except Exception as ecp:
        return corrective('server_error', ecp)     # corrective errors, never raises

def call_mcp(server, name, args):
    return mcp_clients[server].call(name, args)    # same {_success, ...} contract as call_tool
```

### verify() — the last step of every sub-agent run (hook point ⑥)

```python
def verify(artifact, flow):
    if ambiguity.is_present:            return passed             # the question IS the outcome
    if 'violation' in artifact.data:    return failed(error_path)  # already classified; no retry
    if artifact_has_no_data:            return failed('no data')
    if artifact.thoughts == last_user_utt: return failed('echo')
    if flow.name() in content_validation: run_llm_quality_check()  # stubbed today
    return passed
```

---

## The PEX Agent loop

`PEX.orchestrate()` runs one round of the PEX Agent loop — the PEX module is a thin wrapper around
this agent. PEX 1, the System-1 intent sense, is the TypeSafe `classify_intent` call the Assistant
runs synchronously before either lane starts; it writes `state.pred_intent`, the hint NLU's
ensemble detection then checks in parallel. The turn proceeds on the standing belief and picks up
NLU's verdict as a Session Scratchpad entry at the hook points (see
[hook points](#policy-hook-points--the-6-hook-sub-agent-framework)):

- **Click** → the Assistant runs `nlu.react`; the dax names the flow, so there is no detection.
  `prepare()`'s system note tells the agent it MUST run that flow next — the agent's first round
  is that `manage_flows` call, not a choice.
- **Utterance, clear domain intent** → the intent maps to its basic flow (Converse→chat {000},
  Research→find {001}, Draft→outline {002}, Revise→write {003}, Publish→release {004} — the dax
  codes hold across domains; finer-grained flows are NLU's to choose) — the prediction is
  already in `state.pred_flows`; `prepare()` announces it in a system note and the agent's
  first round stacks and runs it. "Without waiting" means no wait on NLU — detection lands at
  the hook points mid-flow.
- **Utterance, Plan or Clarify** → the only intents that wait: the first move is a belief read at
  hook point ①, blocking until NLU's settled belief lands.

**Intent selection — PEX's first step.** Given a new user turn, PEX's main job begins by committing to one
of the 8 intents. Each intent sets how the turn treats the (possibly still-running) parallel detection:

- **Plan** — wait on NLU, then kick off the Workflow Planner.
- **Clarify** — wait for NLU's predicted dialogue state, then send PEX's best guess to the Ambiguity
  Handler.
- **Continue** — legal only while an Active flow exists; advance that flow by handing it back to the
  runtime, without stacking or re-routing. The Active flow name is NLU's hint for this turn.
- **Converse** — maps to `chat` {000} like any intent; no carve-out in code. The agent chooses:
  reply directly on simple requests, or stack and run `chat` when the reply needs the FAQs.
- **Research / Draft / Revise / Publish** — go directly to flow execution; the NLU update is optional at
  the hook points.

All 8 intents keep multiple hook points where NLU can come in. **Plan and Clarify are required to wait**
for NLU's response; the other six continue if NLU has not returned anything. When NLU has returned and
the predicted flow already matches the active flow, nothing needs to change — that is the speed-up. Since
95%+ of turns are Plan turns or some flow execution, NLU flow detection is almost always integrated into
the turn. One extra gate: when the stack already holds an Active flow and PEX 1 sensed a different flow,
the agent's next move (PEX 2) double-checks that selection with the Workflow Planner skill before
stacking over live work — prompt-only, the same agent that later resolves conflicts as PEX 5.

Inside the loop (each `orchestrate()` call is one round, bounded to `max_rounds`), PEX calls the
model with a frozen three-tier system prompt, the message list, and the tool catalog. Each round:

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

When the turn ends, the main Assistant's post-hook records the agent turn, persists state, runs
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
work in `prepare()` and the end-of-turn checkpoint is ordinary turn lifecycle, not a hook. Since both
the orchestrator loop and every sub-agent route tool calls through the same path, the pre/post-tool
hooks cover both levels from one place.

**Who waits on NLU (revised 2026-07-14):** on every utterance turn, NLU's detection runs in parallel
and the hooks are where its verdict comes in. **Plan and Clarify are required to wait**: their first
move is a belief read at hook point ①, which blocks until detection lands. **The other six intents
never block on NLU**: the prediction is already in `state.pred_flows`, the agent's first round
stacks and runs it via `manage_flows`, and the hook ③/⑤ scratchpad read picks up NLU's verdict
mid-flow. When NLU detected the same flow, nothing needs to
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
Assistant. The sub-agents **propose** the blocks; curation defaults to passing them through (ordered, deduped)
with minimal change — PEX authors blocks from scratch only as an optional summarization step for a clearer,
more concise turn. The main Assistant then sends a processed version to the user (through the webserver) and a copy to
[MEM](mem.md) for long-term storage (through the World object). PEX composes the spoken reply directly from
these artifacts plus the tool and sub-agent results via a **voice Skill** in its system prompt — there is no
naturalization tool. Every model call PEX or its sub-agents make routes through the
**[Prompt Engineer](../components/prompt_engineer.md)** (tier abstraction, caching, retry, structured-output
parsing).
