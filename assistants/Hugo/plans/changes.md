# Hugo Redesign — Orchestrator Architecture (changes.md)

This is the plan of record for redesigning Hugo from the deterministic `Agent → NLU → PEX → RES`
pipeline into a central LLM orchestrator that runs in a while-loop and reaches everything else
through tool-calls. The reference architecture is the **Hermes agent**
(github.com/NousResearch/hermes-agent) — Hugo should operate very similarly, with one key
difference: **a flow stack structures sub-agents and tasks, not a Kanban board.**

This file is deliberately larger than a normal plan file: it records the design, the Hermes
alignment, the per-file impact, the verification strategy, the migration phases, and the open
questions, so any session can pick up the work without re-deriving context.

No code has been written. Every section below is a proposal until implemented and verified.

---

## 0. Decisions already made (locked in with Derek, 2026-06-11)

1. **Verification = parity harness.** The old pipeline stays intact and runs beside the new
   orchestrator. The old pipeline is the oracle: the new one must match it on the existing E2E
   scenarios before the old one is deleted in one cut.
2. **Test targets = end-state DB checks + utterance quality judge + tool-call traces.** Traces
   have no ground truth today, so building one is part of this exercise: a small dev set of
   **10 manually approved trajectories** (human approval required, then frozen as fixtures).
3. **Build strategy = parallel build.** New orchestrator lives beside the old pipeline behind a
   second entry point / config flag. The frontend keeps being served by the old path until parity,
   then the old path is deleted in one cut.
4. **Tool granularity = hybrid by frequency.** Hot-path operations get dedicated tools with tight
   schemas; long-tail component surfaces are grouped under per-component dispatch tools — the
   pattern PEX already uses today (`handle_ambiguity`, `coordinate_context`, `manage_memory`).
5. **Reference architecture = Hermes**, with the flow stack replacing the Kanban board as the
   structure for sub-agents and tasks (see §2).
6. **Conversation substrate = persistent message list** (Hermes-style). One message list per
   session, including tool calls and results; every turn resumes it. Not a fresh loop per turn.
7. **Flow handoff = completion record.** A flow reaching `Completed` writes one scratchpad entry
   `{flow, summary, metadata}` — the structured handoff later flows (and the orchestrator) read.
8. **Belief injection = hybrid.** L2 User Preferences are frozen into the orchestrator system
   prompt at session start (Hermes memory pattern, cache-friendly); per-session DialogueState
   user beliefs stay live via the state tool, since they change mid-session by design.
9. **Context compression = build it now, copying Hermes wholesale** (required by decision 6).
   No compaction design decisions of our own: take Hermes's strategy and defaults as-is, and
   change the method later only if we ever want to.
10. **Session retention = keep last N.** `close()` prunes `database/sessions/` to the most
    recent N sessions (config value); `reset()` deletes and recreates the current session.
11. **Session dir is THE persistence format.** Reopening a conversation_id rehydrates from its
    session dir; `DialogueState.from_dict` is retired. One serialization format.
12. **Message list persists** as `messages.jsonl` in the session dir — restart-safe resume, and
    the raw orchestrator transcript is on disk for trace approval and debugging.
13. **Action turns = hybrid by payload.** Pure clicks (dax + payload, no free text) take a
    deterministic bypass (resolve flow → dispatch → respond tool, no loop); action turns with
    user text go through the loop with the resolved flow injected as context.
14. **Orchestrator model tier = deferred to Phase 3.** Run the smoke scenarios on two tiers and
    pick from latency + judge data; one config change either way.
    *Resolved at the Phase 3 gate (2026-06-11): tier = **mid (claude-sonnet-4-6)**.* Both tiers
    ran the smoke openings fully green (crashes 0, grounding 0/12, end-state ok ×3, judge pass
    3/3 final turns); mid averaged 25.5s/turn vs high (claude-opus-4-6) 28.1s at lower cost, so
    mid wins on the latency+judge criteria. Config: `schemas/tools.yaml` orchestrator
    `model_id=claude-sonnet-4-6` (unchanged). Tier runs: `/tmp/smoke_openings_{mid,high}.json`.
15. **World survives as the thin session container** — owns session-dir lifecycle
    (create/load/prune), holds context + file paths + the artifact of record. Agent stays
    orchestration-only.
16. **Domain tools = read-only allowlist for the orchestrator** (find_posts, read_metadata,
    read_section, search_notes, list_channels, channel_status). All writes go through flows,
    preserving policy invariants and completion records.
17. **Scratchpad stamps `writer`.** The tool implementation (never the LLM) stamps each entry
    with `writer` = 'orchestrator' or the flow name — Hermes's anti-forging authorship pattern.
    Everything else stays schema-free.
18. **Clarification gate = tool reports, loop decides.** `detect_and_fill` returns confidence +
    ranked candidates as data; the orchestrator prompt carries the ask-vs-proceed discipline;
    AmbiguityHandler keeps owning levels and escalation bookkeeping.

---

## 1. Glossary — terms that change meaning

| Term | Today | After the redesign |
|---|---|---|
| Orchestrator | n/a (`Agent` is deterministic glue) | The central LLM agent running the session while-loop |
| Message list | n/a (prompts rebuilt per call) | Persistent per-session list incl. tool calls/results (Hermes-style) |
| DialogueState | Per-turn object; NLU predictions + control flags | Per-session **user beliefs** (theory of mind), file-backed |
| Scratchpad | L1 of MemoryManager, in-memory dict | Per-session JSONL file of **agent beliefs**; sub-agent substrate |
| Completion record | n/a | Scratchpad entry `{flow, summary, metadata}` written when a flow completes |
| State file | n/a | Temp file holding the serialized DialogueState incl. flow stack |
| NLU | Module owning intent + flow + slots | A tool: fine-grained flow detection + slot-filling only |
| Intent classification | NLU phase 1 | The orchestrator's own job (system prompt + reasoning) |
| RES | Module producing the spoken line | A tool surface (templates, naturalize); orchestrator speaks directly |
| keep_going | Control flag looping PEX rounds | Gone — subsumed by the orchestrator loop itself |
| World | In-memory session registry (states, frames, stack, context) | Thin session container: dir lifecycle, context, artifact of record (§8) |

Unchanged concepts: flows are still sub-agents with skills + tools; slots and their 12+4 type
hierarchy are unchanged in shape; TaskArtifact stays the turn-output container; the 34 domain
tools stay as they are.

---

## 2. Hermes alignment — what we adopt, map, and reject

Hermes (`/tmp/hermes-agent`, cloned for study) is a single `run_conversation()` while-loop
(`agent/conversation_loop.py`): the model is called with the full message list; if it returns
tool calls they are validated, dispatched, and their results appended to the list; if it returns
plain text with no tool calls, **that text is the final response and the loop exits**. An
iteration budget bounds the loop. Deterministic prologue/epilogue work happens outside the LLM
(`agent/turn_context.py` pre-turn setup; session persistence post-turn). Sub-agents are spawned
via a `delegate_task` tool — a child agent with a restricted toolset and its own smaller budget —
and the child's final response comes back to the parent **as a tool result**. Memory is two
markdown files (USER.md = beliefs about the user, MEMORY.md = agent notes) frozen into the system
prompt at session start; the system prompt is built once per session in three tiers (stable
identity / project context / volatile memory+timestamp) and kept byte-stable for prefix caching.
Long conversations are compressed: protect the first messages and last ~6 turns, LLM-summarize
the middle, replace it with a summary handoff message.

### 2.1 Adopted directly

| Hermes pattern | Hugo adoption |
|---|---|
| One while-loop; "no tool calls + visible text" = done | The orchestrator loop and its termination signal (§3) |
| Persistent per-session message list | Decision 6; owned by ContextCoordinator (§5.5) |
| Final response is the model's own text | Decision from §0 round 1; `respond` tool is a helper only |
| Iteration budget bounding the loop | Per-turn round cap (successor of `_MAX_KEEP_GOING`); cheap reads don't burn budget the way Hermes refunds `execute_code` |
| Deterministic pre/post turn work outside the LLM | ContextCoordinator pre/post hooks; state-file persistence in the epilogue |
| Sub-agent result returns as a tool result | Flow dispatch returns the completion record as the tool result (§4.1) |
| Structured completion: summary + metadata | The completion record (decision 7) |
| Memory frozen into the system prompt at session start | L2 preferences only (decision 8 hybrid) |
| Three-tier system prompt (stable / context / volatile) | Orchestrator prompt: persona+taxonomy / Hugo workflow+catalog / preferences+session line (§7) |
| Middle-out context compression with summary handoff | Decision 9; built in this redesign (§5.6) |
| Tool-call hygiene: validate names/args, dedupe, bounded retries | Orchestrator loop guardrails (§3.3) |

### 2.2 Mapped: Kanban board → flow stack

Hermes structures multi-step work as a Kanban board (SQLite; tasks with statuses
`triage→todo→ready→running→blocked→review→done`, parent-dependency edges, per-task run history,
worker processes spawned by a dispatcher tick). Hugo keeps the **flow stack** instead:

| Kanban concept | Flow-stack equivalent |
|---|---|
| Task (id, title, body/spec) | Flow (name, goal, slots) |
| Assignee profile | The flow's policy + skill prompt |
| Status lane | Flow lifecycle: `Pending / Active / Completed / Invalid` (unchanged) |
| Parent-dependency edges, fan-out | Stack order + `plan_id` chaining under a Plan flow |
| Dispatcher tick spawning workers | Orchestrator dispatching the top-of-stack flow inline, within the turn |
| `kanban_complete(summary, metadata)` | Completion record written to the scratchpad |
| Worker context assembly (`build_worker_context`: spec + parent results + comments) | Flow context assembly: goal + resolved slots + parent flows' completion records + relevant scratchpad entries |
| Board persistence (kanban.db) | `flow_stack` block of the state file |

### 2.3 Rejected (deliberately not adopted)

- **Asynchronous, process-spawning execution.** Kanban workers are separate processes on a 60s
  dispatcher tick. Hugo flows run inline and synchronously inside the turn — conversational
  latency, not batch throughput. (Async Internal flows stay on the roadmap, out of scope here.)
- **Blocked status / retry circuit breaker / per-flow run history.** Explicitly declined in favor
  of the existing four lifecycle states; failure recovery stays `fallback()` + ambiguity.
- **SQLite as the session substrate.** Hugo uses per-conversation temp files (state JSON +
  scratchpad JSONL) per the locked design, not a database.
- **NLU-less operation.** Hermes has no NLU; the model free-decides everything. Hugo keeps NLU
  as a tool because flow detection over a 48-flow catalog and typed slot-filling benefit from a
  dedicated, schema-constrained call.
- **Skills marketplace / self-improvement loop, multi-platform gateway, credential pools,
  provider fallback chains** — out of scope for a single-domain assistant.

---

## 3. Target architecture — the orchestrator loop

### 3.1 Session and turn lifecycle

```
SESSION START
  create session dir: state.json + scratchpad.jsonl
  build orchestrator system prompt (three tiers, §7); FREEZE for the session
  seed the persistent message list

take_turn(text, dax, payload)                       — one user turn
│
├─ PRE-HOOK    ContextCoordinator.add_turn('User', text)   [deterministic]
│              append user message to the persistent list
│              pure click (dax, no text): BYPASS the loop — resolve flow, activate_flow,
│                respond tool, straight to post-hook (decision 13)
│              action + text: resolved flow injected as context, loop runs as normal
│
├─ LOOP        while rounds < BUDGET:
│                call LLM with (frozen system prompt + persistent message list)
│                ├─ tool calls returned → validate, dispatch, append results to list;
│                │    `activate_flow` runs a flow sub-agent inline; its completion
│                │    record comes back as the tool result
│                └─ no tool calls + visible text → THIS IS THE RESPONSE; exit loop
│
├─ POST-HOOK   ContextCoordinator.add_turn('Agent', utterance)   [deterministic]
│              persist state file; compression check on real token usage (§5.6)
│              build the (unchanged) frontend payload
```

- The loop replaces both the fixed NLU→PEX→RES sequence and the `keep_going` mechanic. Plan
  chaining (today: `has_plan` keeps `keep_going` alive) becomes the orchestrator choosing to
  dispatch the next sub-flow before emitting its final text.
- Termination is the Hermes signal: a response with no tool calls ends the turn, and its text is
  the agent utterance verbatim. No RES pass over it.
- The loop is bounded by a per-turn round budget (successor of `_MAX_KEEP_GOING = 5`; exact value
  picked in Phase 3 with latency data). The top-level `try/except` safety net in `take_turn`
  stays.
- `_self_check` disappears; low NLU confidence becomes a signal the orchestrator handles by
  asking (via the ambiguity tool) rather than a hard bail.

### 3.2 What the orchestrator owns vs. delegates

| Responsibility | Owner |
|---|---|
| Intent classification (coarse: which of 7 intent families) | Orchestrator (system prompt + reasoning) |
| Flow detection (fine: which of 48 flows) + slot-filling | NLU tool |
| Entity extraction / repair | NLU tool (grounding sub-task of slot filling) |
| Flow execution (skills, domain tools) | Flow sub-agents via `activate_flow` |
| Clarification lifecycle | AmbiguityHandler tool |
| Memory tiers | MemoryManager tool (scratchpad gets dedicated hot-path tools) |
| State reads/writes (incl. flow stack ops) | DialogueState tool — sole writer of the state file |
| Response wording | Orchestrator directly (respond tool available as helper) |
| Trivial read-only lookups | Orchestrator directly, via the allowlisted domain tools (decision 16) |
| Turn recording, message list, compression | ContextCoordinator (hooks + epilogue, deterministic) |

### 3.3 Loop guardrails (from Hermes's tool-call hygiene)

- Validate tool names against the catalog and arguments against schemas before dispatch; on
  hallucinated names or malformed args, return a corrective tool error and let the model retry
  (bounded, ~3 attempts) rather than crashing the turn.
- Deduplicate identical consecutive tool calls.
- A thinking-only response (no visible text, no tool calls) gets one nudge retry, then the
  canned fallback — never an empty utterance to the frontend.
- These guardrails are the legitimate exception to the no-defensive-code rule: LLM output is
  genuinely unpredictable input.

---

## 4. Tool catalog (hybrid by frequency)

Seed principle: PEX's existing `_component_tool_definitions` (pex.py:465) already implements the
dispatch-tool pattern. We extend that catalog rather than inventing a new mechanism.

### 4.1 Hot-path dedicated tools (tight schemas, called most turns)

| Tool | Backs onto | Purpose |
|---|---|---|
| `read_state` | DialogueState (file) | Read user beliefs, flow stack, slots, active entity |
| `write_state` | DialogueState (file) | Mutate beliefs / stack / slots; the only state-file writer |
| `detect_and_fill` | NLU | Flow detection + slot-filling + entity extraction for one utterance; returns confidence + ranked candidates as data — the orchestrator decides ask-vs-proceed (decision 18) |
| `activate_flow` | flow sub-agent | Run the named flow's policy/skill inline; returns its completion record |
| `append_scratchpad` | scratchpad JSONL | Append one agent-belief entry |
| `read_scratchpad` | scratchpad JSONL | Read back entries (all, or filtered by keys present) |
| `respond` | RES surfaces | Fill an intent template and/or naturalize a draft line |

Flow-stack operations (`stackon`, `fallback`, `pop_completed`) are **ops of `write_state`**, not
separate tools, because the stack lives inside the state file (§6). `activate_flow` is the
analogue of Hermes's `delegate_task`: sub-agent runs inline, result returns as a tool result.

### 4.2 Long-tail dispatch tools (one per component, `op`-style — already exist in PEX)

| Tool | Backs onto | Today |
|---|---|---|
| `handle_ambiguity` | AmbiguityHandler (declare/ask/resolve/present) | exists (pex.py) |
| `coordinate_context` | ContextCoordinator (compile_history, checkpoints, rewrite, search) | exists |
| `manage_memory` | MemoryManager L2/L3 (preferences, long-term) | exists |

`read_flow_stack` (the 4th existing component tool) is retired — its job moves into `read_state`.

### 4.3 Domain tools — unchanged

The 34 domain tools (PostService 9, ContentService 12, AnalysisService 8, PlatformService 5)
keep their definitions and dispatcher. Flow sub-agents call them through the existing
`PromptEngineer.tool_call` agentic loop, exactly as policies do today. The orchestrator may
additionally call the **read-only allowlist** directly for trivial lookups — `find_posts`,
`read_metadata`, `read_section`, `search_notes`, `list_channels`, `channel_status` (decision
16). Every write still goes through a flow, so policy invariants, grounding discipline, and
completion records stay intact.

---

## 5. The state substrate — two files + one message list per conversation

### 5.1 The belief split (why two files)

- **DialogueState file = user beliefs.** What the agent believes about the *user* — theory of
  mind: their intent, what they have confirmed or rejected, where they are in the 10-step
  workflow, which post/section they are talking about.
- **Session Scratchpad file = agent beliefs.** What the agent learns about the *task or itself*
  as a request progresses — intermediate findings, tool results worth keeping, completion
  records. It is the central substrate for sub-agents (flows) to communicate.
- **User Preferences (L2)** keeps its current role: anything from either file that should carry
  into future sessions gets promoted there explicitly. Per decision 8, preferences are also
  frozen into the system prompt at session start (the Hermes USER.md pattern); promotions made
  mid-session take effect next session — exactly Hermes's snapshot semantics.

### 5.2 State file — serialized DialogueState (JSON, single document)

One JSON document, rewritten on each `write_state`. Proposed top-level shape (extends the
existing `DialogueState.serialize()` rather than replacing it):

```json
{
  "session":      {"conversation_id": "…", "username": "…", "turn_count": 12},
  "user_beliefs": {"intent": "Draft", "goal": "…", "confirmed": [], "rejected": [],
                   "workflow_step": 4},
  "grounding":    {"post": "…", "sec": "…", "snip": "", "chl": "", "ver": true},
  "flow_stack":   [ {"name": "compose", "status": "Active", "stage": "…", "plan_id": null,
                     "slots": {"source": {…}, "depth": {…}}} ],
  "flags":        {"has_issues": false, "has_plan": false}
}
```

- `grounding` is the **single source of truth for the active entity** — `state.active_post`,
  entity-slot duplication, and post-id parameter threading all collapse into this one block.
  Uses the canonical Hugo entity parts `{post, sec, snip, chl, ver}`.
- `flow_stack` entries reuse the existing `BaseFlow.to_dict()` / `Slot.to_dict()` serialization;
  flows are rehydrated from `flow_classes` + saved slot values when `activate_flow` runs one.
- Per-turn flags that no longer make sense per-session (`keep_going`, `confidence`,
  `natural_birth`, `pred_flows`) are dropped, not ported. `pred_intent`/`pred_flow` become loop
  locals of the orchestrator, not persisted state.

### 5.3 Scratchpad file — JSONL, append-only

- One JSON object per line; **each entry carries its own set of keys** — there is no fixed
  schema, with one approved structured shape: the **completion record**.
- The tool implementation stamps every entry with `writer` ('orchestrator' or the flow name) —
  set by code, never by the LLM, so authorship can't be forged (decision 17). It is the only
  stamped key; `read_scratchpad` can filter on it.
- Completion record (decision 7): written when a flow reaches `Completed` —
  `{"flow": "compose", "summary": "<1-3 sentences>", "metadata": {…structured facts…}}`.
  This is the Hermes `kanban_complete` handoff transplanted onto the stack: later flows and the
  orchestrator read it as the result of the finished sub-task. `activate_flow` also returns it
  as the tool result, so it lands in the message list too.
- Append-only during a session (`append_scratchpad`); `read_scratchpad` returns entries, newest
  last. `clear_scratchpad` truncates (used by `reset()`).
- MemoryManager keeps owning the file (it is still L1); the in-memory dict implementation is
  replaced by the file-backed one behind the same method names.

### 5.4 Lifecycle

- Created lazily on the first turn of a conversation, keyed by `conversation_id`.
- `Agent.reset()` deletes/recreates the session's files and message list; `close()` prunes
  `database/sessions/` to the most recent N sessions (config value) — decision 10.
- Location: `database/sessions/<conversation_id>/{state.json, scratchpad.jsonl, messages.jsonl}`
  — inside the repo's existing data root, not `/tmp`, so test runs can snapshot them.
- **The session dir is the persistence format** (decision 11): reopening a conversation_id
  rehydrates state, scratchpad, and message list from disk; `DialogueState.from_dict` is
  retired. Retained sessions double as raw material for trace mining and eval data.

### 5.5 Persistent message list (decision 6)

- One message list per session: system prompt (frozen) + alternating user/assistant messages +
  tool calls and tool results, in order. Every loop round and every subsequent turn resumes it —
  the orchestrator sees its own past tool calls verbatim.
- **ContextCoordinator owns it.** Its `Turn` records remain the human-readable view
  (`compile_history` still works, and is what compression summarizes from); the raw API-shaped
  list is the new addition. This extends ContextCoordinator's contract — flagged as a component
  API change requiring sign-off at implementation time, per the planning rule.
- **Persisted as `messages.jsonl`** in the session dir, appended per message (decision 12) —
  restart-safe resume, and the full orchestrator transcript (tool calls included) is on disk,
  which Phase 6's trace approval needs anyway.

### 5.6 Context compression (decision 9 — copy Hermes, no redesign)

Compaction is **not a design surface in this redesign**: we port Hermes's strategy and defaults
(`agent/context_compressor.py`) as directly as the codebase allows, and revisit only if we ever
want a different method.

- **Trigger:** real prompt-token usage from the last API response crossing the configured
  threshold — checked in the post-hook epilogue, never mid-loop (Hermes checks
  `response.usage.prompt_tokens`, not estimates).
- **Shape (Hermes defaults):** protect the head (first non-system messages) and the tail (last
  ~6 turns with tool calls intact); summarize the middle with a cheap auxiliary model; replace it
  with a single summary handoff message carrying Hermes's reference-only prefix semantics.
  Summary budget follows Hermes's ratio/floor/ceiling defaults (20% of context, 2k–12k tokens).
  Hermes's old-tool-output pruning placeholder comes along as part of the copy.
- The one local substitution: Hermes rotates session ids with `parent_session_id` lineage in its
  SQLite DB; Hugo has no session DB, so a ContextCoordinator checkpoint records the compression
  event instead. Everything else is a copy.
- **Synergy with the state substrate (free bonus, not a design input):** beliefs, grounding, and
  flow state live in the state file and scratchpad, not the transcript, so a lossy summary risks
  less here than in Hermes, which must carry working state inside the summary itself.

---

## 6. Grounding — single source of truth

The whole point of folding the flow stack and slots into the state file:

- Today: post-id is passed across flows, copied onto each per-turn state, stored in SourceSlot
  values, and reconciled by `_resolve_source_ids`. Four places, four ways to disagree.
- After: the `grounding` block in the state file always holds the active entity. Slot-filling
  writes it (through `write_state`); policies and flows read it (through `read_state` or the
  resolved-context prefill). Nothing else carries entity identity.
- `BasePolicy._resolve_source_ids` / `_build_resolved_context` shrink to thin reads of the
  grounding block plus the existing fuzzy `resolve_post_id` for user-typed references.
- The PEX post-hook invariant ("`state.active_post` must be set when the flow is entity-grounded,
  else flip `has_issues`") becomes a validation on `write_state`: an entity-grounded flow cannot
  reach `status='Completed'` while `grounding.post` is empty. Post-hooks validate; they do not
  mutate.

---

## 7. The orchestrator system prompt

The one genuinely new prompt artifact. Built once per session and frozen (byte-stable for prefix
caching — the Hermes pattern), in three tiers:

1. **Stable** — Hugo persona (`build_system(engineer.persona)`), the intent taxonomy (absorbed
   from NLU's phase-1 prompt), tool-use policy and loop discipline (when to call NLU vs. answer
   directly, when to dispatch a flow, when to ask via ambiguity, completion-record discipline).
2. **Context** — the 10-step blog workflow, the flow catalog summary, outline-level constants.
3. **Volatile (frozen at session start)** — L2 User Preferences snapshot (decision 8), session
   line (conversation_id, username, date).

Mid-session preference writes (via `manage_memory`) land in L2 immediately but only enter the
prompt at the next session — Hermes snapshot semantics, accepted deliberately.

---

## 8. Per-file impact map

### backend/ — modules

| File | Fate | Notes |
|---|---|---|
| `agent.py` | **Rewritten** (parallel) | Old `_take_turn` kept until cutover; new orchestrator loop added beside it behind a config flag |
| `modules/nlu.py` | **Shrinks to a tool** | Keeps `_detect_flow`, `_fill_slots`, `_extract_entities`, `_repair_entities`, schemas. Loses `_classify_intent` (→ orchestrator prompt), `understand` (→ tool entry point), `_build_state`/`_push_or_get` (→ `write_state` ops) |
| `modules/pex.py` | **Splits** | Tool registry + `_dispatch_tool` + component tool defs survive (they ARE the new catalog). `execute`, the policy dispatch loop, and per-round state synthesis go away; validation hooks (`_security_check`, `_validate_artifact`) re-attach to `activate_flow` and `write_state` |
| `modules/res.py` | **Becomes a tool surface** | `generate` (template fill) + `naturalize` exposed via `respond` tool; `respond`/`start`/`finish` orchestration removed; `pop_completed` becomes a `write_state` op |
| `modules/policies/*` | **Adapted** | Same policy-per-flow structure, now entered via `activate_flow`; entity access rewired to the grounding block; completion = status change via `write_state` + completion record to scratchpad |
| `modules/templates/*` | **Unchanged** | Served through the `respond` tool |

### backend/ — components

| File | Fate | Notes |
|---|---|---|
| `components/dialogue_state.py` | **Rewritten** | File-backed; user-belief fields added; per-turn flags dropped; becomes the read/write tool implementation. `from_dict` retired — the session dir is the restore path (decision 11) |
| `components/world.py` | **Shrinks to session container** | `states`/`frames` lists die (state is the file; the message list is the transcript). Keeps: `context`, session-dir paths + create/load/prune-last-N lifecycle, artifact of record (decision 15) |
| `components/flow_stack/stack.py` | **Reshaped** | Same operations, but state-file-backed: load → mutate → save inside `write_state` ops. `flows.py`/`slots.py`/`parents.py` unchanged except serialization round-trip fidelity |
| `components/context_coordinator.py` | **Extended** | Pre/post hooks; owns the persistent message list (§5.5) and compression (§5.6) — a contract extension requiring sign-off; everything else already behind `coordinate_context` |
| `components/memory_manager.py` | **L1 reimplemented** | Scratchpad goes file-backed JSONL behind existing method names; L2 additionally snapshotted into the system prompt at session start; L3 untouched |
| `components/ambiguity_handler.py` | **Unchanged** | Already fully behind `handle_ambiguity` |
| `components/task_artifact.py` | **Unchanged** | Still the turn-output container; frontend contract frozen |
| `components/prompt_engineer.py` | **Unchanged** | The orchestrator loop is built on the existing `tool_call` agentic loop |

### backend/ — prompts

| File | Fate | Notes |
|---|---|---|
| `prompts/nlu/` intent prompt | **Absorbed** | Intent taxonomy moves into the orchestrator system prompt tier 1 |
| `prompts/nlu/<intent>_slots.py` | **Unchanged** | Still consumed by the NLU tool's `_fill_slots` |
| `prompts/skills/*` | **Unchanged** | Flow sub-agents load them exactly as today |
| orchestrator system prompt | **New** | Three-tier assembly (§7) |
| compression summary prompt | **New** | The middle-summarizer for §5.6 |

Nothing in `database/`, `schemas/tools.yaml` (domain section), or the frontend changes, except
the new `database/sessions/` directory.

---

## 9. Verification plan (the backbone)

### 9.1 Parity harness

A test harness (lives in `utils/tests/`) that runs **both** pipelines on the same scenario and
compares outcomes. The old pipeline is the oracle.

- **Scenarios:** the existing 14-step E2E scenarios (Vision / Observability / Voice). Per
  established practice they are a dev set, not a frozen regression gate — we iterate against
  them, run in two halves to avoid cascading-failure waste.
- **Baseline capture (Phase 0):** run the old pipeline once, record per-turn: final utterance,
  artifact block summary, grounded entity, and end-of-scenario DB state. These recordings are the
  oracle fixtures; the old pipeline does not need to re-run on every comparison.
- **Comparison axes** (per turn unless noted):
  1. **End-state DB checks** — post exists / title / status / section content / outline shape at
     scenario end. Exact assertions; robust to orchestrator non-determinism.
  2. **Grounding check** — the entity the turn acted on matches the oracle's.
  3. **Utterance quality judge** — an LLM judge scores the new utterance against the oracle's
     for task adequacy (answered the question / asked the right clarification / proposed the
     right next step). Not string equality. Judge prompt + rubric are part of the harness.
  4. **Tool-call traces** — see 9.2; only on the approved dev set, not on every scenario.
- **Cutover gate:** all scenarios pass axes 1–3, and the 10 approved trajectories (9.2) replay
  within tolerance. Then the old pipeline, per-turn state plumbing, and old snapshots are deleted
  in one cut, and the parity harness collapses into the ongoing test suite.

### 9.2 Tool-call trace dev set — 10 human-approved trajectories

There is no ground truth for "which tools should the orchestrator call". Creating it is an
explicit deliverable:

1. **Select 10 turns/short-sequences** spanning the space: one clean single-flow turn per major
   intent (Draft, Revise, Publish, Research), a slot-missing clarification round, an ambiguity
   escalation, a plan with chained sub-flows (completion-record handoff visible), an action-turn
   (dax payload), a memory recall, and a grounding switch between two posts.
2. **Record** the new orchestrator on each: ordered list of `(tool_name, key_args)` plus the
   dispatched flow, completion records written, and final utterance.
3. **Human approval:** each trajectory is rendered to a readable markdown sidecar and Derek
   approves or annotates it. Approval is the ground-truth event; approved sidecars are committed.
4. **Replay tolerance:** a trace matches if (a) required calls are present in order — e.g.
   `detect_and_fill` precedes any `write_state` that fills slots; persistence tools called
   exactly the approved number of times — and (b) no forbidden calls appear (e.g. no domain
   writes during a clarification turn). Incidental reads (`read_state`, `read_scratchpad`) are
   not order-pinned. Tolerance rules live next to the sidecars, not hard-coded.
5. Re-approval is required whenever a behavior change deliberately alters a trace — same
   discipline as today's snapshot-sidecar rule (PR-body justification).

### 9.3 Test pyramid after cutover

| Layer | What | Speed | Inherits from |
|---|---|---|---|
| Unit | State file round-trip, scratchpad JSONL ops, completion-record shape, flow/slot serialization fidelity, grounding validation on `write_state`, message-list bookkeeping | <1s, no LLM | `unit_tests.py` + `test_artifacts.py` (Hypothesis FlowStack state machine ports to the file-backed stack) |
| Component | NLU tool in isolation, respond tool in isolation, compression summarizer on a recorded long transcript (the established isolated-component pattern) | seconds, some LLM | existing isolated harnesses |
| Trace | 10 approved trajectories replay within tolerance | minutes | new (9.2) |
| E2E | Scenario runs with end-state DB checks + utterance judge | 5–8 min | `e2e_agent_evals.py`, snapshots re-recorded for the new shape |

The free-tier (<1s) layer must survive the redesign — file-backed substrates are *easier* to unit
test than the in-memory World, and we lean on that.

### 9.4 Per-phase verification gates

Every phase in §10 ends with a named gate. No phase starts until the previous gate is green.

---

## 10. Migration phases

**Phase 0 — Harness + baseline.**
Build the parity harness skeleton; capture oracle fixtures from the old pipeline on all
scenarios. *Gate:* fixtures recorded and reviewed; old pipeline still green on existing tests.

**Phase 1 — Substrate.**
State file + scratchpad JSONL (incl. completion-record shape) + the
`read_state`/`write_state`/scratchpad tool implementations, including flow-stack-as-state-file
ops and the grounding block. Old pipeline untouched. *Gate:* unit layer green, including
Hypothesis state-machine equivalence between the in-memory FlowStack and the file-backed one
(same op sequence → same stack).

**Phase 2 — Tool surfaces.**
NLU tool (`detect_and_fill`), `respond` tool, `activate_flow` wrapper, catalog wiring for the
dispatch tools. Each tested in isolation against recorded inputs before any loop exists.
*Gate:* component layer green; NLU-tool outputs match old `nlu.understand` predictions on the
baseline turns.

**Phase 3 — Orchestrator loop v1.**
New entry point behind a config flag; three-tier system prompt (frozen, preferences snapshot);
persistent message list in ContextCoordinator; bounded loop with the §3.3 guardrails on
`PromptEngineer.tool_call`. Target: complete the three simplest scenario openings end-to-end.
Run the smoke scenarios on two model tiers and pick the orchestrator tier from the latency +
judge data (decision 14). *Gate:* smoke scenarios pass end-state + judge axes; tier chosen.

**Phase 4 — Flow migration.**
Policies/flows rewired to the grounding block, `activate_flow`, and completion records; plan
chaining via the loop; ambiguity + memory paths. *Gate:* all scenarios pass axes 1–3 of the
parity harness.

**Phase 5 — Compression.**
Port the Hermes compactor (§5.6) — trigger, protect head/tail, middle-summarizer, summary
handoff — with its defaults; no tuning work beyond making it run on Hugo's message list.
*Gate:* a synthetic long-session test (scripted 30+ turn conversation) survives two compression
rounds with grounding intact and the judge axis still passing on post-compression turns.

**Phase 6 — Trace dev set + cutover.**
Record, approve, and freeze the 10 trajectories; stabilize across reruns. Then delete the old
pipeline, per-turn state plumbing, dead World fields, and old snapshots in one cut; re-record E2E
snapshots for the new shape. *Gate:* full pyramid green on the orchestrator-only codebase.

---

## 11. Risks and mitigations

- **Latency/cost regression.** The orchestrator adds LLM round-trips per turn on top of flow
  skills. Mitigation: the frozen system prompt + persistent message list are exactly the shape
  prompt caching rewards (the Hermes design exists for this); hot-path tools so common turns
  need few rounds; intent classification rides in the first orchestrator call rather than a
  separate NLU phase-1 hop (may net out cheaper); measure per-turn latency in the parity harness
  from Phase 3 onward.
- **Non-determinism breaks tests.** Accepted up front: structural per-turn snapshots are replaced
  by end-state checks, a judge, and tolerance-based traces. The deterministic unit layer moves
  *down* into the substrate where determinism is real.
- **Frontend payload drift.** The `{'message', 'actions', 'artifact'}` contract and TaskArtifact
  block shapes are frozen; the parity harness diffs block summaries to catch drift early.
- **Action turns (dax payloads).** Today `NLU.react` short-circuits deterministically. The loop
  must not "re-decide" a button click. Resolved (decision 13): pure clicks bypass the loop
  entirely; action+text turns run the loop with the resolved flow injected. The bypass is a
  second code path — the trace dev set and parity harness cover it explicitly.
- **Serialization fidelity.** Flows/slots must round-trip through the state file without losing
  stage, fill status, or entity values. Mitigation: Phase 1's Hypothesis equivalence gate exists
  precisely for this.
- **Compression eats grounding.** A bad middle-summary could lose what the conversation was
  about. Mitigation: the state file and scratchpad are authoritative for beliefs/grounding/flow
  state — the transcript summary only carries narrative (§5.6); Phase 5's gate tests exactly
  this.
- **Message-list growth within a turn.** Verbose tool results (full post reads) bloat the list
  fast. Mitigation: tool results follow today's card-shaped summaries rather than raw dumps;
  compression handles the rest. Hermes's old-tool-output pruning pattern is available if needed.
- **Yield-when-stacked, fallback, contemplate.** Subtle behaviors encoded in module sequencing
  (LESSONS.md Part II) must be re-expressed as orchestrator prompt rules or write_state
  validations. The trace dev set deliberately includes these cases.
- **Dual maintenance during parallel build.** Old pipeline is feature-frozen from Phase 0 —
  bug fixes only, no new flows until cutover.

---

## 12. Open questions — all resolved (2026-06-11)

Q1–Q7 were settled one at a time with Derek and folded into decisions 10–18 (§0):
Q1 → decisions 10–12 (keep last N; session dir is the persistence format; messages.jsonl).
Q2 → decision 13 (hybrid by payload). Q3 → decision 14 (tier deferred to Phase 3 data — the one
intentionally deferred item). Q4 → decision 15 (World stays as session container). Q5 →
decision 16 (read-only allowlist). Q6 → decision 17 (`writer` stamp). Q7 → decision 18 (tool
reports confidence, loop decides). Compression questions dissolved earlier under decision 9
(straight Hermes copy).

Nothing else is blocked on a user decision; remaining choices (loop budget value, retention N,
allowlist tweaks) are config values picked empirically during their phases.

---

## 13. Out of scope

- Frontend changes of any kind (payload contract frozen).
- New flows, new slot types, or changes to the 48-flow catalog and DAX codes.
- Dana / Kalli — they keep the 3-module pipeline until Hugo's redesign is proven; this document
  is the template they would later follow.
- Async/parallel Internal flows (Hermes-style background workers / dispatcher ticks) — the loop
  makes it *possible*, but it is explicitly not part of this redesign.
- Hermes features rejected in §2.3: Kanban statuses/retries, SQLite substrate, skills
  self-improvement, multi-platform gateway, provider fallback chains.
