# Round 0.1 — Component interface taxonomy (ownership, persistence, access)

Status: **draft for review** — nothing here is recorded as final. On sign-off, the taxonomy and the
approved consolidations merge into `_specs/architecture.md` (the summary tables and access matrix)
with the per-interface detail pushed into the existing `_specs/components/*.md` files; this file
stays as the round record. The consolidation proposals then become the round's build work.

The taxonomy covers the seven components and the three module parents. Each component is
deterministic code living inside one module — that is why a component can be exposed as a **tool**:
calling it has no model in the loop, only the module's LLM decides *when* to call it.

## Who owns what

Ownership follows tense. Each module answers one question about execution:

| Module | Tense | Question it answers | Components it owns |
|---|---|---|---|
| **NLU** | future | what *should* be executed? (our best initial attempt) | Ambiguity Handler, Dialogue State |
| **PEX** | present | what is *actively* being processed? | Flow Stack (managed through the Workflow Planner skill), Session Scratchpad |
| **MEM** | past | what *actually got* executed and recorded? | Context Coordinator, User Preferences, Business Context |

A write belongs to the module whose tense it is — and the rule holds even for a single concept: a
predicted belief about what we will put on the stack belongs to NLU, an actual stack update is
present so PEX manages it, and a snapshot of the stack at end of the turn is a record, so that
belongs to MEM. A module may **read** another module's components freely, but writing is restricted.

Each component exposes a small set of **methods** (deterministic code). There is no single
cross-agent super tool per component: every agent and sub-agent gets its own **scoped set of
tools**, each calling the appropriate component method — either fewer tools or fewer parameters per
tool at every call site, which keeps tool-calling simple. The **Assistant's calls are not tool
calls** — the Assistant is code, not a model, so it invokes component methods directly. Each section
below lists the exposed methods, then how every caller touches them. All session files live in the
session dir (`database/sessions/<convo_id>/`) — the dir IS the persistence format.

---

## NLU components (natural language understanding)

### Ambiguity Handler

Exposed Methods:
| Method | Inputs | Output |
|---|---|---|
| `recognize` | `level` (general/partial/specific/confirmation), `metadata` (level-shaped, validated), `observation` | `{_success}` — the ambiguity is recorded |
| `ask` | `flow_name` | `{question}` — the level-specific clarification text |
| `present` | | returns the highest level of ambiguity present, if any |
| `recover` | | `{recovery}` a tool call to MEM and reviews scratchpad in an attempt to resolve an ambiguity internally without consulting the user. Results are written to Session Scratchpad. |
| `resolve` | `explanation` how the issue was cleared and/or the root cause | `{_success}` — the pending ambiguity is cleared |

**NLU agent** (owner):
  - calls `recognize_ambiguity()` on low-confidence flow detection or intent classification. Triggers `self.recognize()` and also `self.recover()` when the ambiguity level is specific or confirmation level.
  - reacts when asked by others to `recover`. Makes a query to MEM in an attempt to recover from the uncertainty before resorting to human escalation.
  - reacts when asked by others to `resolve`. Returns a resolution verdict and an optional explanation.
  - reacts when asked by others to generate a clarification question. Returns a thoughtful question to maximize information gain which will become the agent utterance.

**PEX agent**:
  - can call `ask_clarification_question` tool which triggers `self.ambiguity.ask()` to generate a clarification 
  question; PEX should rely on this tool rather than generate its own clarification question since NLU has 
  larger purview of the session scratchpad, belief state, and other ambiguities.
  - can call `recover_from_ambiguity` tool which triggers `self.ambiguity.recover()` to try to pull extra information to resolve an issue internally 

**MEM agent**:
  - no access.

**Sub-agents**:
  - can call `declare_ambiguity` tool which triggers `self.ambiguity.recognize(...)` in code when a slot is missing or an
  entity can't be resolved (`partial`/`specific`), or if some something needs to be confirmed.

**Assistant**:
  - deterministically calls `self.ambiguity.present()` to see if any ambiguity remains, and if so call `resolve()` to ask NLU if it is able to take care of it. NLU's agent will decide if resolution is appropriate
  - then calls `present()` again to get the updated result, and injects this information into PEX agent. PEX then starts its loop by deciding on the current intent.

### Dialogue State

NLU's structured belief — the prediction of what should run (intent, ranked flows, confidence, slots) plus the grounding block (the active entity) and other flags. Only the NLU module can write (or validate) the dialogue state. Persistence: `state.json`, one write per belief write; per-turn snapshots for `undo`.

Exposed Methods:
| Method | Inputs | Output |
|---|---|---|
| `read_state` | — | the serialized belief document: session, user_beliefs, grounding, flow_stack*, flags. Joins the parallel NLU thread first — Plan/Clarify wait here |
| `write_state` | the belief / grounding fields to set | the belief document after the write — belief and grounding only; stack ops are `manage_flows`' |
| `react` | the `dax` + `payload` from a UI click (the dax names the flow — no detection needed) | belief written from the resolved flow; slots filled from the payload |
| `think` | the latest user text (supplied by code, not the caller); the intent hint (derived in code from the stack top) | the fresh detection: `{intent, flow_name, confidence}` — belief re-written |
| `contemplate` | the failed flow + ambiguity observation (both read from state by code) | the corrected detection: `{intent, flow_name, confidence}` — belief re-routed |
|`validate` | | asserts that the dialogue state is in a valid form (ie. the pred flow belongs to the pred intent, and other checks) |

**NLU agent** (owner):
  - calls `read_state()` tool which triggers self.read_state()
  - calls `write_state()` tool which triggers self.write_state()

**NLU models**:
  - reacts to when other calls think() or contemplate() to produce a calibrated prediction for flow detection, intent classification, and slot-filling.

**PEX agent**:
  - can call `understand(op=read)` tool which triggers `self.state.read_state()` to read the current
  belief (intent, pred_flows, pred_slots, grounding) before routing; the read joins the parallel NLU
  thread, so Plan and Clarify turns wait here
  - can call `understand(op=think)` tool which triggers `self.state.think()` to get a second opinion on a flow, used during workflow planning
  - can call `understand(op=contemplate)` tool which triggers `self.state.contemplate()` to reconsider a previously detected flow, used when a sub-agent hits an error or violation

**MEM agent**:
  - can call `get_dialog_state(...)` tool with additional parameters if the default state information fed in by the Assistant is not sufficient. This will trigger `self.state.read_state()`

**Sub-agents**:
  - no direct access.
  - However, if a sub-agent hits an error, then the policy will notify the PEX agent. The PEX agent then has a choice to contemplate (ie. re-consider detecting a new flow) or some other recovering mechanism.

**Assistant**:
  - deterministically calls `self.state.react()` when a user takes an action in the UI
  - calls `self.state.think()` after receiving PEX's initial intent prediction. Will pass in a hint into the think if PEX classified the intent as Research, Draft, Revise, or Publish.
  - calls self.store_state() after PEX is done. This function will call`self.state.read_state()` to prepare the basic view of the dialogue state. This information is then packaged and sent to MEM for the memory process.

---

## PEX components (policy execution)

### Flow Stack

What is actively being processed: the stacked flows with their slots, tools, and lifecycle status
(Pending / Active / Completed / Invalid). The Workflow Planner skill guides PEX in manipulating the stack data structure.
The stack lives in-memory and questions about it's state talk to the stack directly; the on-disk copy is a snapshot which is MEM's responsibility to write at the end of a turn.

Exposed Methods:
| Method | Inputs | Output |
|---|---|---|
| `stackon` | `flow_name` | the pushed flow (Pending; matching slot values hand over from the prior flow) |
| `fallback` | `flow_name` | the top flow replaced with the named one, slots transferred; old flow → Invalid |
| `pop` | — | removes Completed AND Invalid flows all at once, surfacing the next Pending flow, returns the state of the flow stack, which is very useful for the PEX agent in forming a response |
| `get_flow` | optional `status` filter | the top-of-stack flow (or the top flow with that status), or None |
| `find_by_name` | `flow_name` | the live (non-Completed/Invalid) flow with that name, or None |
| `to_list` | — | the serialized stack entries (feeds MEM's end-of-turn snapshot and belief reads) |
| `activate` | `flow_name` | <fill in> |

**NLU agent**:
  - no access.

**PEX agent** (owner):
  - calls `manage_flows(op = update | stackon | fallback | activate | pop)` tool — the op family is
  cohesive, so it stays one tool with an op parameter. `stackon`/`fallback`/`pop` trigger the
  matching methods above; `update` mutates the top flow's slots/stage/status (corrections only);
  `activate` triggers `PEX.activate_flow()`, the policy runner (module code, not a stack method).
  A flow's `status` is also set by a policy's `complete_flow` (grounding-checked) — a present-tense
  write, so it lives on this surface too.

**MEM agent**:
  - no tools. MEM's code reads `to_list()` at the turn boundary to write its end-of-turn snapshot
  record (N1).

**Sub-agents**:
  - can call `read_flow_stack` tool which triggers `self.flow_stack.to_list()` to see what other
  flows are queued (e.g. outline checks whether a compose follows it).
  - can call `stackon_flow` tool which triggers `self.flow_stack.stackon(flow_name)` for a
  prerequisite push (the current flow needs another flow's output first).
  - can call `fallback_flow` tool which triggers `self.flow_stack.fallback(flow_name)` when the
  request belongs to a sibling flow.  This is equivalent to a hand-off to pass the responsibility to another flow.
  No activate (there is no fourth level) and no pop/updat (lifecycle bookkeeping belongs to the planner).

**Assistant**:
  - deterministically fills up the stack when reopening a session, from MEM's latest snapshot
  record.

### Session Scratchpad

What the swarm is currently working on: the loosely-structured cross-flow channel where sub-agents
share findings, produced output, and completion records within one session. Present tense — working
material, not an archive (64-entry cap, LRU-evicted; past-tense material graduates OUT via MEM
promotion). PEX owns it because the swarm doing the work is PEX's — **but PEX's rights stop at
append**: only NLU may revise existing entries so that parallel sub-agents do not referee their own entries
The NLU editor privilege sit structurally outside of the writing sub-agents. Persistence:
`scratchpad.jsonl` in the session directory.

Exposed Methods:
| Method | Inputs | Output |
|---|---|---|
| `read` | optional filters: `writer` ('orchestrator' or a flow name), `keys` (entries carrying every named key — `['flow', 'summary']` selects completion records) | matching entries, newest last |
| `append` | `entry` (schema-free dict); the `writer` stamp is added in code | the entry count after the append |
| `update` | `key`, the revision | the revised entry — **NLU-only**: merge duplicates, reconcile contradictions, prune stale notes, maintain `used_count` (§3.3 work) |
| `write_completion` | `flow`, `summary`, `metadata` | the completion record — the code path `complete_flow` uses; not a tool |
| `clear` | — | empties the pad (session reset) |


**NLU agent**:
  - the **sole editor**: appending triggers NLU review, and `update_scratchpad` (its scoped tool
  onto `self.scratchpad.update()`) is the one sanctioned cross-module write (§3.3 work).
  - reads the pad during detection when useful.

**PEX agent** (owner):
  - can call `read_from_scratchpad` tool which triggers `self.scratchpad.read()` to read earlier
  completion records or findings before chaining a dependent flow.
  - can call `append_to_scratchpad` tool which triggers `self.scratchpad.append()` to persist a
  finding worth keeping; authorship is stamped in code. Append-only — no revise right.

**MEM agent**:
  - can call `read_scratchpad` tool at promotion time — an entry worth keeping becomes an L2
  preference or L3 record (auto-promotion is a background MEM task, designed-not-built, stub S-2).

**Sub-agents**:
  - can call `save_findings` tool which triggers `self.scratchpad.append()` with the structured
  findings shape (`{findings, summary, references_used}`); the key is stamped from the flow's name in code.
  - can call `read_scratchpad` tool to pick up prerequisites left by earlier flows — the
  cross-invocation state channel (flows re-activate from scratch and resume from here).
  - completion records land via `complete_flow` → `write_completion` (code, not a tool). Append-only.

**Assistant**:
  - deterministically binds the pad to the session's `scratchpad.jsonl` at session open and calls
  `clear()` on session reset.

---

## MEM components (memory)

### Context Coordinator

The record of what actually happened in this session: user/agent/system turns, action annotations,
checkpoints, and the raw API message list the acting loop runs on. Past tense — nothing here is a
plan; it is history the moment it lands. Persistence: `messages.jsonl` in the session dir (the
message list); turns rebuild in memory.

Exposed Methods:
| Method | Inputs | Output |
|---|---|---|
| `add_turn` | `speaker`, `text`, `turn_type` (utterance/action) | the turn is recorded |
| `compile_history` | `look_back` (default 5), `keep_system` | the rendered `convo_history` string |
| `get_turn` | `turn_id` | one turn as a dict, or None |
| `save_checkpoint` / `get_checkpoint` | `label` (+ `data` on save) | — / the saved checkpoint dict |
| `append_message` | one API message | the message, also appended to `messages.jsonl` |
| `compress_messages` | `summarize` fn, `protect_tail`, `prompt_tokens` | bool — whether compaction ran |

**MEM agent** (owner):
  - serves `recap` (its L1 skill) by calling `self.context.compile_history()`.
  - runs compaction in the turn epilogue — `compress_messages()` rewrites the middle of the message
  list and `messages.jsonl` (code, off the critical path).

**NLU agent**:
  - no tools; NLU's code calls `compile_history()` to build every detection and slot-fill prompt.

**PEX agent**:
  - can call `get_history` tool which triggers `self.context.compile_history(look_back)` to pull
  more history than the loop's window carries.
  - can call `get_checkpoint` tool which triggers `self.context.get_checkpoint(label)` to read a
  saved mid-session marker (`get_turn` likewise for one specific turn).
  - its loop code appends messages (`append_message`) and records the end-of-turn checkpoint as a
  System turn — code, not tools.

**Sub-agents**:
  - no tools; `convo_history` is injected into their skill prompts by code.

**Assistant**:
  - deterministically records the turns — `add_turn` in the pre/post hooks. Writing the record is
  the turn lifecycle acting *for* MEM, the way a court clerk writes the transcript.

### User Preferences

L2 memory — durable per-account defaults learned from past sessions (typed `Preference` records:
value, endorsed, rankings, triggers, confidence). Persistence: none today — a real gap; L2 must
survive the session (see Divergences).

Exposed Methods:
| Method | Inputs | Output |
|---|---|---|
| `store_preference` | `key`, a value / dict / `Preference` record | the preference is recorded |
| `get_preference` | `key`, `default` | the value string |
| `read` | optional `query` | `{key: value}` view (what `recall` returns) |
| `render` | — | the endorsed-vs-guessed block for system prompt tier 3 |

**MEM agent** (owner):
  - serves `recall` (its L2 skill) by calling `self.preferences.read(query)`.
  - promotion from the scratchpad calls `store_preference` in code (background task,
  designed-not-built).

**PEX agent**:
  - can call `store_preference` tool which triggers `self.preferences.store_preference(key, value)`
  — the user just stated a durable preference, record it. Already the right scoped shape: one
  purpose, two parameters.

**NLU agent / Sub-agents**:
  - no tools; they see preferences only through the frozen system prompt (`render`, tier 3).

**Assistant**:
  - deterministically calls `render()` when building the frozen system prompt at session start.

### Business Context

L3 memory — the vetted business-knowledge corpus, including FAQs. Whole-corpus LLM rerank today
(<50 entries); vector retrieval is designed-not-built. Persistence: seeded read-only from
`database/faq_data/faqs.json`; runtime `insert_record` is RAM-only (see Divergences).

Exposed Methods:
| Method | Inputs | Output |
|---|---|---|
| `search_documents` | `query`, `top_k=3` | the ranked matching documents (renamed from `search_faqs` — FAQs are one document type) |
| `search_all` | `query`, `top_k` | candidate documents (whole corpus today) — internal step of `retrieve` |
| `rerank` | `query`, `candidates`, `top_k` | LLM-ranked matches — internal step of `retrieve` |
| `insert_record` | one document `record` | the record joins the corpus — ingestion / promotion entry |

**MEM agent** (owner):
  - serves `retrieve` (its L3 skill) by running `search_all` → `rerank` in code.
  - promotion from the scratchpad calls `insert_record` in code (background task).

**PEX agent**:
  - can call `search_documents` tool which triggers `self.business.search_documents(query)` to
  answer a vetted-knowledge question without dispatching a flow.

**Sub-agents**:
  - can call `search_documents` tool (same scoped read, on the flow tool menus that list it).

**NLU agent**:
  - no access.

**Assistant**:
  - no access.

---

## Module parent interfaces

The Assistant (`agent.py`) is the only caller that sees all three modules; modules reach each other
only through the component tools above.

| Module | Entry | Inputs | Output |
|---|---|---|---|
| **NLU** | `NLU.understand(op, user_text, dax, payload, hint)` — the Python entry behind PEX's `understand` tool and the Assistant's direct calls | op = react (a click; dax names the flow) / think (an utterance; ensemble detection) / contemplate (failed-flow re-route); `hint` = PEX's first-pass intent selection, derived deterministically from the stack top (domain intents narrow detection; Plan/Clarify/Converse blank) | the validated `DialogueState` — belief written |
| **PEX** | `execute(state, context, system_prompt, dax, payload, text, nlu_thread)` | the turn's inputs + the parallel NLU thread to join at belief reads | the spoken utterance (str); artifacts/blocks ride the tool results to the frontend |
| **MEM** | `recap(n_turns, filter)` / `recall(query, flow_name)` / `retrieve(query, top_k, documents)` | the three memory reads: session (L1 via context/scratchpad), preferences (L2), business knowledge (L3) | rendered history str / preference dict / ranked records |

Per turn: the Assistant records the user turn (Context Coordinator), kicks off NLU (awaited, or on a
thread when an entity is active), runs `PEX.execute`, then the epilogue does MEM's bookkeeping
(compression check, persistence). MEM has no `backend/modules/mem.py` yet — `MemoryManager` is the
module facade wrapping its three components (Round 4 makes it a full module).

## Access matrix

R = reads, W = writes, `—` = no access. The channel is named where it isn't obvious.

| Component | NLU agent | PEX agent | Sub-agents (policies) | MEM agent | Assistant (code) |
|---|---|---|---|---|---|
| Ambiguity Handler | **W** (owner: recognize/recover/resolve/ask) | W via `ask_clarification_question`, `recover_from_ambiguity` | W via `declare_ambiguity` | — | calls `present()`/`resolve()` directly |
| Dialogue State | **W** (owner: `read_state`/`write_state`) | R via `understand(op)` | — (errors route through PEX) | R via `get_dialog_state` | calls `react()`/`think()`/`read_state()` directly |
| Session Scratchpad | editor (sole revise right, `update_scratchpad`) + R | **W** (owner) via `read_scratchpad`/`append_to_scratchpad`, append-only | W via `save_findings` + completions, append-only | R via `read_scratchpad` (promotion) | binds file, `clear()` on reset |
| Flow Stack | — | **W** (owner) via `manage_flows(op)` | W via `read_flow_stack`/`stackon_flow`/`fallback_flow` | R (end-of-turn snapshot → its record) | rehydrates on session open |
| Context Coordinator | R (`compile_history` in code) | R via `get_history`/`get_turn`/`get_checkpoint`; W (loop messages, checkpoint) | R (convo_history injected) | **W** (owner: compaction) + R (`recap`) | records turns (`add_turn`) |
| User Preferences | R (prompt tier 3) | W via `store_preference` | R (prompt tier 3) | **W** (owner: promotion) + R (`recall`) | calls `render()` at prompt build |
| Business Context | — | R via `search_documents` | R via `search_documents` | **W** (owner: ingestion) + R (`retrieve`) | — |

## Proposed consolidations (for sign-off)

Redundant or drifted interfaces found while building this taxonomy, plus the naming standard that
falls out. Nothing below is built — each line is a proposal.

### Tool level — scoped per-agent toolsets, no cross-agent super tools

Every agent and sub-agent gets its own scoped set of tools calling the appropriate component
methods — either fewer tools or fewer parameters per tool at each call site. An op parameter
survives only where one caller uses a cohesive op family (`understand`, `manage_flows`); everything
else is a flat, single-purpose tool.

| # | Proposal | What it removes |
|---|---|---|
| T1 | Where an op family survives, the parameter is named `op` (never `action`) | the second name for the same idea |
| T2 | Retire `manage_memory` — its scratchpad actions duplicate the scoped scratchpad tools; its `read_preferences` has no LLM caller (preferences reach prompts via `render`) | a whole tool that is two other tools |
| T3 | Keep `store_preference` as PEX's scoped preference write — already the right shape (one purpose, two parameters); no merge | the earlier `manage_preferences(op)` merge idea |
| T4 | Replace `call_flow_stack(action, details)` with the sub-agents' scoped flow tools: `read_flow_stack` / `stackon_flow` / `fallback_flow` | the duplicate stack tool, its arg shape, and its missing persistence |
| T5 | Keep `save_findings` as the sub-agents' scoped scratchpad append — its structured shape (`{findings, summary, references_used}`) is the point; the orchestrator gets `read_scratchpad` / `append_to_scratchpad` | the earlier merge-into-one-scratchpad-tool idea |
| T6 | Rename `search_faqs` → `search_documents` (FAQs are one document type in the corpus) | the too-narrow FAQ scope. (The earlier `understand` → `understand_user` and `scratchpad` → `manage_scratchpad` renames are superseded: the scratchpad splits into scoped flat tools, and the latest sketch keeps `understand` — confirm.) |

Resulting scoped toolsets (component tools only — domain tools ride separately):

| Caller | Scoped tools |
|---|---|
| **NLU agent** | `read_state`, `write_state`, `update_scratchpad`, `recognize_ambiguity` (and serves `recover` / `resolve` / `ask` on request) |
| **PEX agent** | `understand(op)`, `manage_flows(op)`, `read_scratchpad`, `append_to_scratchpad`, `ask_clarification_question`, `recover_from_ambiguity`, `get_history`, `get_turn`, `get_checkpoint`, `store_preference`, `search_documents` (+ the read-only domain allowlist) |
| **MEM agent** | `get_dialog_state`, `read_scratchpad` (+ its skills `recap` / `recall` / `retrieve` run component methods in code) |
| **Sub-agents** | `declare_ambiguity`, `save_findings`, `read_scratchpad`, `read_flow_stack`, `stackon_flow`, `fallback_flow` (+ the flow's domain tool menu) |
| **Assistant** | none — code, not a model; it calls component methods directly |

### Component-method level — merges and renames

| # | Component | Proposal |
|---|---|---|
| C1 | FlowStack | Drop `peek()` — it is `get_flow()` with no filter (both return top-of-stack). Keep `get_flow`. |
| C2 | FlowStack | Rename `pop_completed()` → `pop()` to match the tool op vocabulary (it pops Completed and Invalid, so the old name under-describes it anyway). |
| C3 | ContextCoordinator | Drop `find_turn_by_id()` — duplicate of `get_turn(turn_id)` plus a bookmark side effect. |
| C4 | ContextCoordinator | snake_case the outliers: `setbookmark` → `set_bookmark`, `storecompleted_flows` → `store_completed_flows`. |
| C5 | ContextCoordinator | Three revision paths (`rewrite_history`, `revise_user_utterance`, `Turn.add_revision`) — collapse to one entry that routes to `Turn.add_revision`. |
| C6 | SessionScratchpad | `write(key, value)` OR `write(entry_dict)` is a dual-shape signature — standardize on `write(entry: dict)` (one clean contract; callers pass the key inside the entry). |
| C7 | AmbiguityHandler | Superseded by the redesign above: `present()` now returns the highest ambiguity level present (or none) — one return shape, no `name=` flag. Also `declare` → `recognize`, and `recover(…)` is a new method (internal resolution attempt via MEM + scratchpad before asking the user). |
| C8 | DialogueState | Three serializers (`serialize`, `serialize_session`, `read_state`) — keep two: `serialize` (persistence form) and `read_state` (the tool view, which absorbs `serialize_session`). |
| C9 | UserPreferences | Drop `read_all()` — `read(query=None)` already returns everything. |
| C10 | BusinessContext | Make `search_all` and `rerank` private (`_candidates`, `_rerank`) — they are internal steps of MEM's `retrieve`; the public surface is `search_documents` + `insert_record`. |

### New interfaces (required by the ownership split, not speculative)

| # | Proposal | Why |
|---|---|---|
| N1 | An end-of-turn stack snapshot in MEM's record, plus `FlowStack.load()` to rehydrate from the latest one on session open | divergence 1 — the live stack is PEX's and in-memory; the on-disk copy is a record (past), so MEM writes it at the turn boundary |
| N2 | `UserPreferences.save()` / `.load()` (per-account file) | divergence 4 — L2 is defined as surviving the session |

## Divergences from current code (the reconcile list)

1. **Flow stack persistence crosses the ownership line.** Today the stack is saved on every op as a
   block inside `state.json` by `DialogueState.write_state(..., stack=...)` — NLU's class persists
   PEX's data. Target: the live stack is in-memory (PEX's); MEM records a snapshot of it at end of
   turn (N1); `write_state` keeps belief ops only; reopening a session rehydrates the stack from
   MEM's latest record. (`rehydrate_flow` moves to the flow_stack module with it.)
2. **`call_flow_stack` duplicates `manage_flows`** for sub-agents, with a different arg shape and no
   persistence. Merge into one `manage_flows` tool with the trimmed sub-agent op menu (read /
   stackon / fallback).
3. **`complete_flow` writes flow status through `state.write_state`** — a stack write routed through
   the belief writer. Moves with (1) to the flow-stack surface.
4. **User Preferences are not persisted** — L2 is defined as surviving the session; today it is
   RAM-only.
5. **Business Context inserts are RAM-only** — promotion writes vanish on restart; the corpus file
   is read-only.
6. **No `backend/modules/mem.py`** — MEM is the `MemoryManager` facade; Round 4 makes it a module
   with the same three-component ownership as this document.
