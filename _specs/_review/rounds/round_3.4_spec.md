# Round 3.4 — NLU ↔ PEX Flow Handoff and Grounding Refill

Maps to **Master Plan · Round 3 (NLU)**. This proposal covers two failures at the boundary where
NLU turns a prediction into live flow state for PEX. Neither is fundamentally a FlowStack primitive:
one concerns how NLU hands a detection to PEX, and the other concerns how NLU refills a grounded
Active flow without losing entity identity.

Design decisions below were settled with Derek on 2026-07-11, revised on 2026-07-14, and are
written inline; the wiring-problems section at the bottom carries each verdict.

---

## Canonical Turn

One turn is not a strict sequence. The Assistant opens the turn, and then two lanes run: NLU's
policy prediction — intent classification + flow detection, the System-2 authority — and the PEX
Agent's acting loop, whose first reasoning move is a System-1 intent sense (prose in its own
reasoning, never a separate call). Modules never call each other; they share components through
the World, and control passes between the lanes at four touch points, all deterministic code
(dialogue_state.md § Predicting the Belief State):

1. **The hint** (PEX 1 → Assistant → NLU `check`) — Assistant code, never a tool argument. The
   Assistant passes PEX's first-pass selection to NLU, where `check` stores it before thinking
   starts. An Active flow on the stack is the Continue signal: its name narrows NLU's candidates
   because NLU now has a strong prior, and PEX's selection seeds the vote as one med-tier voter.
   Plan/Clarify/Converse carry no real signal, so detection runs over the full ontology.
2. **The scratchpad message** (NLU `validate` → the policy's hook points) — `validate` ends
   NLU's thinking by writing to the Session Scratchpad: an aligned entry when the flows match,
   or an entry announcing the flow NLU has already stacked (with its rationale) when they
   differ. A hook point is a module-code read of the Session Scratchpad that decides whether
   anything warrants notifying the PEX agent. The entry is read at hook point 3
   (post-tool-call) or 5 (post-LLM), whichever comes first. A different-intent top is handled
   by that code directly — the new top runs and the agent is never notified. A same-intent
   conflict goes to the agent: PEX 5 decides at that hook — run the new flow or pop it. Hook
   point 6 is `verify()` itself, where code pops completed flows deterministically; PEX 5 never
   runs there. This replaces `inject_belief_state`'s context note, which retires.
3. **The blocking read** (PEX module → NLU) — Plan and Clarify are the only intents that wait:
   PEX calls `understand(op='read')` at hook point 1 and blocks on NLU's settled belief before
   decomposing or questioning. Every other intent starts its read-only work without waiting.
4. **The failed-flow re-route** (policy stall → NLU) — after a policy stalls on grounding, the
   agent calls `understand(op='contemplate')`, handing control back to NLU mid-turn to re-detect
   over the failed flow's edge flows (wiring problem 1). Contemplation is a recovery move, not a
   planning one — it never runs before the policy has.

Today's code runs the lanes back-to-back — `take_turn` (assistant.py:40) finishes
`nlu.understand` before `pex.execute` starts (round 0.3 de-threaded the loop) — but the contract
is written for the parallel model, and nothing in 3.4 depends on the lanes being sequential.

Every LLM input is a prompt built by code; every LLM output is a schema-constrained JSON object
(NLU) or a tool call / plain text (PEX), and code executes each tool call. Clarification
questions never bubble up as errors — they ride inside tool results as `question` and the PEX
Agent relays them. Only exceptions bubble to `take_turn`'s safety net.

Phase names carry the execution model. `PEX n` / `NLU n` / `MEM n` rows are agent actions —
async LLM moves; `PEX module` / `NLU module` / `MEM module` rows are plain code, synchronous.
The numbers are shared time slots: rows with the same number run largely concurrently (NLU 2's
flow detection alongside PEX 2's flow management), and NLU 2 follows PEX 1 because detection waits on
the selection the Assistant relays. The module pre/post verbs are canonical (architecture.md):
NLU `check`/`validate`, PEX `prepare`/`verify`, MEM `start`/`finish`.

The turn at a glance — the Assistant's `take_turn` wraps the whole turn; the three modules are
columns; time flows down; PEX 2 and NLU 2 run concurrently (`∥`):

```
Assistant · take_turn ═ the wrapper around the whole turn ═══════════════════════════════════════
  open: ambiguity ask-count reset · save the user turn (MEM) · route to PEX

   PEX                              NLU                           MEM
   ───                              ───                           ───
                                                                  add_turn(user utterance)
   module  prepare()
   PEX 1   _run_loop: System-1 intent sense
     │
Assistant · run NLU ─ relay PEX's first-pass selection ─▶
                                    module  check(): store PEX's intent
   module ◀──── control returns ─────┘
   clear intent → proceed
   Plan/Clarify → wait (hook point 1)
   PEX 2   manage_flows()      ∥    NLU 2   _detect_flow + tally
   gates a stackon over an
   Active flow; usually skipped
                                    module  think(): same flow → continue,
                                            else create + stackon() the new flow
                                    NLU 3   slot-fill (_fill_slots)
                                    module  validate() — one of two:
                                     1 same flow → fill it + aligned entry
                                     2 new flow  → already stacked; slots
                                                   filled + entry announcing it
   module  execute(): code stackon + policy start;
   no I/O wait, so often done during NLU 2
   module  hook point 1 · pre-flow — before the sub-agent
   starts; Plan/Clarify block here on NLU's settled belief
   PEX 4   policy sub-agent (llm_execute)
           ├ hook point 2 · pre-tool — before each tool call
           │   [tool executes]
           ├ hook point 3 · post-tool — read the Scratchpad
           └ hook point 4 · tool-retry — pre-tool, retries only
   module  hook point 5 · post-LLM — the Scratchpad read when
   the sub-agent called no tools. Either read: different
   intent → code re-routes, agent not notified
   PEX 5   manage_flows(): same-intent conflicts only, at
           hook 3/5 — run the new flow or pop() it; else skipped
   module  verify() — hook point 6: checks + the code pop()
   PEX 6   respond: generate the reply from popped flows
     │
Assistant · wrap-up ─ send the reply · save the agent turn (MEM) ─▶ add_turn(agent utterance)
  Pending flows remain → back to PEX 2; otherwise start_to_finish():
                                                                  module  start(): add the system
                                                                          turn · reset is_newborn
                                                                  MEM 7   _compaction + _promote
                                                                  module  finish(): save state.json
                                                                          · turn-end shape check
```

| phase | method | role |
|---|---|---|
| Assistant | `take_turn` (assistant.py:40) | save the user utterance as a turn within MEM, per-turn ambiguity ask-count reset, route to PEX module |
| PEX module | `prepare()` (pex.py:280) | per-turn setup code: note/read budgets reset, the user message appended, the bounded loop entered |
| PEX 1 | `_run_loop` (pex.py:334) | the first agent move: a rough System-1 version of intent classification, formed in the agent's own reasoning |
| Assistant | run NLU | receive information from PEX, pass information along to NLU |
| NLU module | `check()` | First, we check what intent was detected by PEX because that will influence future decisions. Store it as a variable, and then start thinking. Hand back control to Assistant, who can move forward on PEX module |
| PEX module | — | If PEX agent output a clear domain intent (ie. Research/Draft/Revise/Converse/Publish/Continue), then proceed to the agent to perform Workflow Planning immediately. In contrast, if PEX 1 output Plan or Clarify, then wait on NLU until hook point 1. The intent→flow mapping is definitional: each intent maps to its basic flow — Converse→chat {000}, Research→find {001}, Draft→outline {002}, Revise→write {003}, Publish→release {004}. Flow names vary by domain; the dax codes do not. Finer-grained flows are NLU's to choose. |
| PEX 2 | manage_flows() | the same agent loop, one move after PEX 1. Meaningful when the stack already has an Active flow and PEX 1 predicted a different one: PEX 2 double-checks that result with the Workflow Planner skill and makes the final flow-management call — a stackon over live work is gated by this second look. Skipped when the stack is empty or the turn is a plain Continue (no model call; `execute()` code handles those). Prompt-only — PEX 2 and PEX 5 are the same agent, no new code. |
| NLU 2 | `_detect_flow` + tally (nlu.py:419, 637) | ensemble flow detection over the hinted candidates — 2-5 voters, confidence = voter agreement; on a low-confidence cross-intent split, `_classify_intent` tie-breaks and one narrowed re-detect runs |
| NLU module | `think` (nlu.py:111-134) | First, we check what intent was detected by PEX because that will influence future decisions. Then NLU does it's own thinking. If the flow stack already has a flow and NLU detected the same one, then just continue with it. This is NLU's version of the Continue intent. Otherwise, create a new flow to fill and stack it on directly with `world.flows.stackon()` — any disagreement, same intent or different, is resolved on PEX's side. |
| NLU 3 | slot-fill call in `_fill_slots` (nlu.py:491) | fill missing slots; let the schema decide what needs filling |
| NLU module | `validate()` to end the thinking (nlu.py:209) | validation includes entity repair, writing the predicted belief to the state. If NLU detected the same flow as PEX, then just fill that existing flow with the newly predicted slots (NLU's fill wins if it contradicts what PEX wrote earlier) and append an aligned entry to the Session Scratchpad. If NLU detected a different flow, the flow is already on the stack from `think`; validate fills its slots and the scratchpad entry announces it with NLU's rationale. |
| PEX module | `execute()` | if we were blocking read based on Plan/Clarify to settle belief, then PEX waits at hook point 1 to read the results from NLU thinking. It is still too early for contemplation. PEX calls update, stackon, fallback or pop as commanded. The policy is started. `execute()` has no I/O dependency, so its code-based stackon of the mapped flow is likely already done before NLU 2's detection calls finish; any race is PEX 5's to clean up. |
| PEX 4 | policy sub-agent — `llm_execute` (policies/base.py:61) | the sub-agent executes the flow's task with its scoped tools; This is technically the sub-agent, rather than the agent running. |
| PEX module | — | At the end of the first tool-call (hook point 3) or post-LLM call (hook point 5), whichever comes first, the active policy must wait for NLU's response. A hook is a module-code read of the Session Scratchpad checking whether anything warrants notifying the PEX agent. A different-intent top needs no agent decision — the code re-routes and the new top runs (back to PEX 4); the agent is never notified. A same-intent conflict is the one thing surfaced to the agent. |
| PEX 5 | manage_flows() | the same agent as PEX 2 decides same-intent conflicts only — given the flow_stack, the status of the Active flow, and NLU's scratchpad messages: run the new flow, or pop() it and stay; update, stackon, anything it needs. Different-intent re-routes never reach it, since code already handled them. It decides at the hook that surfaced the conflict — 3, or 5 when no tool ran — and never at hook point 6. On most turns there is no conflict and PEX 5 is skipped. |
| PEX module | `verify()` | hook point 6, the verification hook: wrap up the policy by running any verification checks; code pops Completed and Invalid flows deterministically — no agent call |
| PEX 6 | `respond` | feed popped flows to the agent to generate agent response |
| Assistant | `take_turn` (assistant.py:84-86) | send agent response + artifact blocks to frontend, save the agent utterance as a turn within MEM, if flow_stack still has pending flows go back to PEX 2 to loop, otherwise hand control to MEM by running start_to_finish() |
| MEM module | `start()` | add the system turn into Context Coordinator (completed flows · the active flow · the grounded post), reset is_newborn on every remaining flow, clears consumed grounding choices, bumps the turn count |
| MEM 7 | `_compaction` + `_promote` (mem.py:80) | when prompt-token usage crosses the threshold, summarize the message middle; decide if any content from Scratchpad is promoted as a record into User Preferences or as a document into Business Knowledge |
| MEM module | `finish()` | save a snapshot into state.json, check turn-end shape, compaction trigger read |

---

## 3.4.1 — Flow handoff: message passing between NLU and PEX

### Problem

Evidence from the round-2.12 evaluation: `B02.C15` ended with a five-deep Pending tower
(`rework, audit, audit, write, release`). NLU places every detection on the stack through
`_stack_detected_flow`, but PEX does not necessarily accept and run every prediction NLU places.
When PEX asks for grounding or otherwise responds without running the proposal, the Pending flow is
left on the shared stack. Repeated turns accumulate more proposals; the turn-end invariant warning
fired 13 times in the cited run.

A Pending top is not harmless residue. The permanent planner contract requires each turn to end
with either an empty stack or an incomplete Active top, with intentional Pending work only beneath
it. NLU uses that shape on the next turn to decide whether to fill an existing flow or place a new
one. PEX reads the same top to decide what to execute, and FlowStack uses it for transfer and dedupe.
A stale proposal can therefore receive a later answer, transfer slots into an unrelated task,
suppress a legitimate push, or eventually run despite never being accepted.

This belongs in Round 3 because the problematic state is created by NLU as a proposal and becomes
real work only when PEX accepts it. The missing contract is the handoff between the two modules, not
the mechanics of push/pop themselves.

### Root cause

NLU proposals and PEX-owned queued work have the same representation: both are ordinary Pending
flows. Lifecycle status cannot distinguish:

- an **NLU proposal** made visible for PEX to consider but never accepted;
- a **queued plan step** deliberately placed with `stackon(active=false)`;
- a previously executed flow suspended beneath newer work and expected to resume.

The earlier `turn_ids == []` heuristic is invalid. Queued plan steps also have no turn ids before
they run, and policy execution does not currently maintain `turn_ids` reliably enough to make
absence meaningful. That heuristic would delete legitimate plans while failing to encode actual
ownership.

Cleaning only when the next detection arrives is also too late. It persists an illegal Pending top,
allows it to affect the next turn, and leaves the final proposal forever when the conversation ends.

### Target contract

NLU stops leaving unresolved proposals. No new field, no new stack operation, no turn-end
cleanup — existing primitives only. NLU's thinking ends with exactly one of two outcomes:

1. **Same flow** as the one on the stack → fill that existing flow with the newly predicted
  slots (NLU's fill wins if it contradicts what PEX wrote earlier) and append an aligned entry
  to the Session Scratchpad. No stack change.
2. **Different flow** — same intent, different intent, or Converse, it makes no difference →
  `think` stacks the new flow directly with `world.flows.stackon()` (the flow beneath reverts
  to Pending), NLU 3 fills its slots, and `validate`'s scratchpad entry announces it with NLU's
  rationale. PEX resolves the stack in the same turn: the entry surfaces at hook point 3
  (post-tool-call) or 5 (post-LLM). On an intent difference the hook's code re-routes — the
  agent is never notified, and no enforcement code is needed beyond `_top_policy` running the
  top of the stack, so doing nothing already means NLU's flow executes. On a same-intent
  difference the agent is notified and PEX 5's manage_flows call decides — run the new flow,
  or pop it and stay. A Converse
  detection gets no carve-out: `chat` stacks, runs trivially (the streamed reply is its
  execution), pops, and the flow beneath reactivates.

Under this contract the `B02.C15` tower cannot form: every flow NLU stacks is resolved in the
same turn — run or popped — and the resolution point is deterministic module code (the hook
3/5 read, with hook point 6 — `verify()` itself — as the last stop), not agent goodwill. Plan steps
queued with `stackon(active=false)` are PEX-owned work and can never be confused with NLU
output. MEM's turn-end shape check (mem.py:54) remains the log-only guard for the crash window
between a stackon and its resolution.

### Design for message passing:

There is no boolean called 'proposal'. No new concepts. Instead we use existing concepts:

**PEX -> NLU**
NLU knows what intent and flow were predicted by PEX because it can look at the flow_stack during `check()`

**NLU -> PEX**
   - If NLU predicted the same flow as PEX, just place a basic message in Session Scratchpad that everything is aligned.
   - If NLU predicted a different flow — same intent, different intent, or Converse — then NLU has already stacked it, so PEX can just read the top flow from the stack; the Session Scratchpad entry carries NLU's rationale. The hook code reads this message at hook point 3 (post-tool-call) or 5 (post-LLM hook). A different intent re-routes in code without notifying the agent; a same-intent conflict goes to PEX 5 — run the new flow, or pop it and stay.
In most cases, the entry is at hook point 3, but occasionally, a sub-agent might complete without calling any tools in which case we will definitely intervene by hook point 5.

### Implementation surfaces

- `backend/modules/nlu.py` — `check` grabs PEX's first-pass selection from the stack; `think`
  stacks a divergent detection directly with `world.flows.stackon()`; `validate` fills slots,
  repairs entities, and writes the aligned or announcement entry. `_stack_detected_flow` is
  deleted — stacking already has its primitive, and every stacked flow is a detected flow, so
  the wrapper adds nothing.
- Session Scratchpad — carries the aligned / announcement entries through the existing
  `append_entry`; no new entry fields (the `think` divergence note at nlu.py:122-128 is the seed
  of the announcement entry).
- `backend/modules/policies/base.py` — the hook point 3/5 scratchpad read; a different-intent
  top stops the displaced policy right there in code, without notifying the agent. A
  same-intent conflict is the only thing surfaced to the agent — that resolution belongs to
  PEX 5.
- `backend/modules/pex.py` — the PEX 2 gate and the PEX 5 resolution are prompt-only changes to
  the same agent (through the Workflow Planner skill), no new code; `inject_belief_state`
  retires with its dead forced-fallback branch (wiring problem 4); `_record_checkpoint` is
  deleted.
- `backend/modules/mem.py` — no `store_turn`: the wrap-up is `start()` (add the checkpoint as
  the System turn through `context.add_turn()`, reset `is_newborn`) and `finish()` (save the
  state snapshot, check the turn-end shape), with compaction and L2/L3 promotion between them.
- Workflow Planner and Dialogue State permanent specs — document the two `validate` outcomes
  and the hook-point reads. `modules/pex.md` is already updated (2026-07-14): the loop entry,
  Who-waits-on-NLU, and signal blocks now match this round, and the belief-injection block is
  replaced by the scratchpad message.

### Verification

- A same-flow detection fills the existing flow; the stack gains nothing.
- A same-intent different-flow detection is stacked by NLU and resolved in the same turn — the
  agent runs it or pops it; the entry surfaces at hook point 3, or 5 when the sub-agent called
  no tools.
- A different-intent detection runs in the same turn — the top of the stack is what executes;
  the displaced policy stops cleanly at its hook point.
- An acknowledgment turn stacks `chat`, which runs (the streamed reply is its execution) and
  pops; the flow beneath reactivates.
- `active=false` plan steps still run on later turns, empty `turn_ids` and all.
- Replay `B02.C15`: no Pending accumulation and no turn-end invariant warnings.

## 3.4.2 — Whole-entity refill after partial grounding

### Problem

NLU's grounding doctrine is one complete entity object: `{post, sec, snip, chl}`. On an answer turn,
NLU should preserve the established `post` and `sec`, add narrower grounding only when supported,
and return the whole entity rather than a disconnected part. In particular, `snip` is a sentence
index or end-exclusive `[start, end]` slice from `schemas/tools.yaml`; descriptive prose such as
“the rambling paragraph” is not a snippet id.

The current generic fill schema excludes every slot whose `filled` flag is true. A SourceSlot may
satisfy its minimum requirement with only `post` or `post + sec`. Once it does, the entire source
slot disappears from the Active-flow refill schema. NLU cannot return the same entity with a newly
available snippet id even though the flow is still incomplete at the requested granularity.

This pressures prompts and policies into unsafe workarounds: emit only `snip`, store descriptive
text where an id belongs, ask the user again, or let the policy guess. Grounding is the safety
boundary for writes, so silently changing a post/section or inventing a snippet is worse than
declaring uncertainty.

### Root cause

The implementation conflates two meanings of “filled”:

1. sufficient to satisfy the flow's minimum slot requirement;
2. complete and therefore ineligible for any additional grounding.

Those meanings are not equivalent for a composite SourceSlot. `_fill_slots_schema` uses the first
meaning to enforce the second, making partial composite grounding impossible to refine.

Prompt corrections alone cannot solve this because the model cannot return a field excluded by the
JSON schema. Conversely, merely including the slot is unsafe unless code preserves stable identity
and validates snippet ids.

### Target contract

Eligibility keys on the slot's declared `entity_part`: `SourceSlot.check_if_filled`
(slots.py:141-147) counts an entity only when `post` and the `entity_part` are both present, so
a `write` source (`entity_part='snip'`, flows.py:246) stays in the fill schema until a snippet
id lands, while a `rework` source (`'sec'`) stops asking once a section is grounded. Render the
current normalized entity and require a whole entity shape whenever new grounding is supplied.

Entity repair in deterministic code (`validate`):

- preserve existing non-empty `post` and `sec`;
- never silently accept a different post or section on the matching Active-flow answer path;
- accept `snip` only as a valid sentence index or two-item end-exclusive slice;
- leave `snip` empty when context contains only a description;
- preserve `chl` unless the user supplies a valid channel change;
- never ask NLU to predict `ver`.

A conflicting post/section indicates that the matching-flow assumption or entity resolution needs
confirmation; it must not overwrite the live target.

### Design: check the slot's entity part

1. As long as the slot's entity part is not filled, then include the slot as a candidate for
   filling — this is exactly what `SourceSlot.check_if_filled` already computes
   (slots.py:141-147), so eligibility is simply `not slot.filled`.
2. Do not invent new `refill_entity` parameter or other concepts. Reuse what already exists.
3. Merge _fill_slots and _fill_active_flow since these are actually the same function with the same responsibility.

### Implementation surfaces

- `backend/modules/nlu.py::_fill_slots_schema` — eligibility is `not slot.filled`; no override
  parameter, since `SourceSlot.check_if_filled` already keys on the declared `entity_part`.
- `_fill_slots` — absorbs `_fill_active_flow` (one function, one responsibility); provides the
  current entity and runs the code-side entity repair before `fill_slot_values`.
- `backend/prompts/for_nlu.py` and NLU slot exemplars — show full-entity preservation and correct
  snippet-id behavior.
- `prompts/nlu/revise_slots.py` — remove any remaining snip-only or descriptive-snip examples.
- Dialogue State permanent spec — distinguish minimum flow readiness from refinable composite
  grounding.

### Verification

- `{post=A, sec=intro}` + valid `[2, 5]` → `{post=A, sec=intro, snip=[2, 5]}`.
- `{post=A, sec=intro}` + “the rambling paragraph” → same post/sec and empty snip.
- Proposed post B or another section does not silently replace established grounding.
- The whole entity reaches `pred_slots`, the live flow, serialized state, and policy input unchanged.

---

## Scenario walkthroughs

Eleven single-turn traces, each expanded over the Canonical Turn's phase rows — same rows, same
order. A row reading "same" matches the standard turn exactly; the spelled-out rows are what
make the scenario unique. S3-S9 and S11 exercise this round's contracts.

### S1 — Fresh task, clean run

"Put together an outline for a post on container gardening." Empty stack.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | empty stack; op=think; route to PEX module first |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | System-1 sense: Draft — clear |
| Assistant | run NLU | passes PEX's Draft selection along |
| NLU module | `check` | map Draft to outline flow {002}, starts thinking |
| PEX module | - | clear domain intent → map Draft intent to outline {002} flow |
| PEX 2 | - | skipped, stack is empty so no model call needed to manage workflow |
| NLU 2 | `_detect_flow` | full-ontology candidates; the vote converges on `outline` |
| NLU module | `think` | since detected flow matches PEX, go straight to validate() |
| NLU 3 | N/A | skipped, since detected flow matches PEX |
| NLU module | `validate()` | add aligned entry into Session Scratchpad |
| PEX module | `execute` | `stackon('outline')` → policy starts → policy will run `fill_slots_by_label` |
| PEX 4 | policy sub-agent | the outline sub-agent drafts and saves |
| PEX module | `understand` | the hook-3 read shows the aligned entry → proceed |
| PEX 5 | manage_flows() | same |
| PEX module | `verify()` | checks pass; complete; `pop` |
| PEX 6 | `respond` | review popped flows, generate response |
| Assistant | `take_turn` | no Pending flows remain → hand control to MEM |
| MEM module | `start()` | system turn added: completed: outline · active: none |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

Given a standard process we end up skipping PEX 2 and NLU 3.

### S2 — Continue: the answer fills the Active flow

`release` is Active and incomplete, waiting on a channel. "Substack works."

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | `release` is Active |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | System-1 sense: Continue |
| Assistant | run NLU | passes Continue |
| NLU module | `check` | given Continue, reads the Active flow from the stack, which is `release` |
| PEX module | — | Continue is clear → proceed |
| PEX 2 | - | skipped, Continue doesn't need a new flow |
| NLU 2 | `_detect_flow` | suppose the vote lands on `release` |
| NLU module | `think` | the stack already has `release` and NLU detected the same |
| NLU 3 | - | skipped, since detected flow matches PEX |
| NLU module | `validate()` | add aligned entry into Session Scratchpad |
| PEX module | `execute` | policy starts → policy will run `fill_slots_by_label` on the missing `chl` |
| PEX 4 | policy sub-agent | the policy releases the post |
| PEX module | — | the hook-3 read shows the aligned entry |
| PEX 5 | manage_flows() | same |
| PEX module | `verify()` | checks pass; complete; `pop` |
| PEX 6 | `respond` | same |
| Assistant | `take_turn` | no Pending flows remain → hand control to MEM |
| MEM module | `start()` | system turn added: completed: release · active: none |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

### S3 — Snippet narrowing, NLU suggests a flow, PEX declines

`rework` Active, grounded `{post=A, sec=intro}`. "Just fix sentences 2 through 5."

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | `rework` is Active |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | System-1 sense: Continue |
| Assistant | run NLU | same |
| NLU module | `check` | same |
| PEX module | — | Continue is clear → proceed |
| PEX 2 | - | skipped, Continue doesn't need a new flow, PEX doesn't know about disagreement yet |
| NLU 2 | `_detect_flow` | vote lands on `write` because the scope has narrowed to a snippet, now there is contention |
| NLU module | `think` | create a `write` {003} flow and stack it on directly |
| NLU 3 | `_fill_slot` | slot-filling stores `post=A, sec=intro, snip=[2, 5]` using `fill_slot_values()` **follow 3.4.2**  |
| NLU module | `validate()` | entity repair verifies the post/sec identity and validates the slice; entry added to Scratchpad notifying a new flow was added |
| PEX module | `execute` | no wait, since PEX predicted Continue → policy starts; no slot-filling occurs because rework only need `sec` to proceed |
| PEX 4 | policy sub-agent | operates on the narrowed span to apply the fix |
| PEX module | `understand` | hits hook point 3, mis-alignment finally discovered |
| PEX 5 | manage_flows() | Since this is same intent, PEX agent gets to decide what to do. It can pop {003} from the stack and proceed with just rework {006}; Or it can `update_flow(flow_name='rework', status='invalid')` and proceed with write {003}. |
| PEX module | `execute` | In this case, PEX agent decides to reject NLU's suggestion because it feels that 'rework' flow already finished the intended task to fix the sentences; no need to do more writing |
| PEX 6 | `respond` | same |
| Assistant | `take_turn` | no Pending flows remain → hand control to MEM |
| MEM module | `start()` | system turn added: completed: rework · active: none |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

In this case, the correct flow is *indeed* 'write', but PEX agent decided to override the decision because the work was already done.

### S4 — Descriptive span (3.4.2 conservative path)

Same setup as S3; "the rambling paragraph near the end."

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | `rework` is Active |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | System-1 sense: Continue |
| Assistant | run NLU | same |
| NLU module | `check` | same |
| PEX module | — | Continue is clear → proceed |
| PEX 2 | - | skipped, Continue doesn't need a new flow |
| NLU 2 | `_detect_flow` | a vague description is not a snippet-narrowing signal — the vote stays on `rework` |
| NLU module | `think` | same flow → go straight to validate() |
| NLU 3 | `_fill_slots` | runs as always; rework's `source` is filled (its entity part `sec` is grounded), so the schema leaves it out — and a descriptive phrase is not a `snip` id anyway |
| NLU module | `validate()` | `{post=A, sec=intro}` unchanged; aligned entry |
| PEX module | `execute` | no wait; `rework` re-runs |
| PEX 4 | policy sub-agent | reads the section and locates the passage itself — policy-side snippet discovery, out of scope for NLU |
| PEX module | — | the hook-3 read shows the aligned entry |
| PEX 5 | manage_flows() | skipped, nothing to resolve |
| PEX module | `verify()` | checks pass; complete; `pop` |
| PEX 6 | `respond` | same |
| Assistant | `take_turn` | no Pending flows remain → hand control to MEM |
| MEM module | `start()` | system turn added: completed: rework · active: none |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

### S5 — NLU suggests a flow, PEX agrees

`refine` (Draft) Active, mid-paragraph. "Should we write this out as text now?" — NLU hears a
`compose` request; the agent reads it as part of the refinement under way.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | `refine` is Active |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | System-1 sense: Continue |
| Assistant | run NLU | same |
| NLU module | `check` | same |
| PEX module | — | Continue is clear → proceed |
| PEX 2 | - | skipped, Continue doesn't need a new flow, PEX doesn't know about disagreement yet |
| NLU 2 | `_detect_flow` | vote lands on `compose` because NLU thought the user wanted to convert outline to prose |
| NLU module | `think` | create a `compose` {3AD} flow and stack it on directly |
| NLU 3 | `_fill_slot` | slot-filling stores the post using `fill_slot_values()` (compose's `source` is post-level) |
| NLU module | `validate()` | entry added to Scratchpad notifying a new flow was added |
| PEX module | `execute` | no wait; since PEX predicted Continue → policy starts |
| PEX 4 | policy sub-agent | `refine` keeps polishing the paragraph, unaware the user asked to convert the outline to prose |
| PEX module | `understand` | hits hook point 3, mis-alignment finally discovered |
| PEX 5 | manage_flows() | Since this is same intent, PEX agent gets to decide what to do. It can pop {3AD} from the stack and proceed with just refine {02B}; Or it can `update_flow(flow_name='refine', status='invalid')` and proceed with compose {3AD}. |
| PEX module | `execute` | In this case, PEX agent decides to accept NLU's suggestion. Thus, PEX now executes the 'compose' policy by going back to PEX 4 step. Eventually, it pops both {3AD} because it is completed and {02B} because it is invalid |
| PEX 6 | `respond` | same |
| Assistant | `take_turn` | no Pending flows remain → hand control to MEM |
| MEM module | `start()` | system turn added: completed: compose · invalid: refine · active: none |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

### S6 — NLU picks different-intent flow from PEX

`refine` Active; "ha, fair point!"

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | `refine` is Active |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | reads the turn as approval of the task in progress — Continue |
| Assistant | run NLU | same |
| NLU module | `check` | same |
| PEX module | — | proceed — the sense is Continue, not Converse |
| PEX 2 | - | skipped, Continue doesn't need a new flow |
| NLU 2 | `_detect_flow` | the vote lands on `chat` (Converse) |
| NLU module | `think` | create a `chat` {000} flow, marks the underlying 'refine' {02B} flow as Pending, automatically push the new flow on top of the stack |
| NLU 3 | `_fill_slot` | this is a no-op though because `chat` has no slots |
| NLU module | `validate()` | entry added to Scratchpad notifying a new flow was added |
| PEX module | `execute` | no wait; since PEX predicted Continue → execute `refine` policy |
| PEX 4 | policy sub-agent | `refine` tries to continue, but since no new information was gained, we probably remain stuck |
| PEX module | — | hook point 3: the top is `chat` {000}, a different intent → code re-routes back to PEX 4; the agent is not notified |
| PEX 4 | policy sub-agent | `chat` runs trivially — the streamed acknowledgment is its execution — and completes |
| PEX module | pop() | no same-intent conflict to decide; pop() clears the completed {000}, and the {02B} underneath reactivates and re-runs. Given that no new information was really gained from the user, we likely hit whatever issue we still had earlier. |
| PEX 6 | `respond` | This should trigger some clarification question again. |
| Assistant | `take_turn` | same |
| MEM module | `start()` |  system turn added: completed: chat · active: refine |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

There is no special handling for Converse. All intents are processed the same way.
Unlike S3 and S5, since the intent is different, NLU automatically wins out and PEX runs the new flow without a decision.

### S7 — Plan: multiple stacked (not queued) steps

"Find my three best posts, draft a new one on that theme, then schedule it." Starting on an empty stack.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | empty stack |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | System-1 sense: Plan — no real signal |
| Assistant | run NLU | passes Plan along |
| NLU module | `check` | stores {29D} |
| PEX module | — | **wait** Plan blocks on NLU until hook point 1 |
| PEX 2 | - | skipped, stack is empty so no model call needed to manage workflow |
| NLU 2 | `_detect_flow` | the vote converges on `plan`, ideally detects find {001}, outline {002}, and schedule {4AC} |
| NLU module | `think` | agrees that this is multi-step mode so set `self.dialogue_state.has_plan = True` |
| NLU 3 | _fill_slots() | skipped, since state.has_plan |
| NLU module | `validate()` | skipped, state.has_plan |
| PEX module | `execute` | the blocking read at hook point 1 — `understand(op='read')` returns the detected flows from NLU → decompose into three steps: `stackon('schedule' active=false)`, then `stackon('outline', active=false)`, and lastly `stackon('find')` → which automatically activates the `find` policy |
| PEX 4 | policy sub-agent | `find` looks for three posts |
| PEX module | — | look at scratchpad, but nothing is there from NLU this turn |
| PEX 5 | manage_flows() | skipped |
| PEX module | `verify()` | same |
| Assistant | `take_turn` | the plan steps wait Pending → back to PEX 2 to loop; each pass runs the next step until no Pending flow remains. There's a good chance we get stuck on schedule since we haven't converted the outline to prose yet. Schedule may try to stack on 'compose', but let's assume the agent decides to ask for clarification this time. |
| PEX 6 | `respond` | Ask a clarification question with `ambiguity.ask()` |
| MEM module | `start()` | system turn added: completed: find, outline · active: schedule |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

### S8 — Clarify: waiting on NLU results

"Can you come up with a few angles for describing the bifurcation process?"
This is a brainstorm {39D} flow, but PEX can't choose this flow since the Draft intent really only lines up with outline {002}. Thus, PEX will have to choose Clarify {09F} as the fallback.
NLU takes on the responsibility for choosing the correct flow.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | empty stack |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | System-1 sense: Clarify — no real signal |
| Assistant | run NLU | passes Clarify along |
| NLU module | `check` | stores {09F} |
| PEX module | — | **wait** Clarify blocks on NLU until hook point 1 |
| PEX 2 | - | skipped, because PEX made no actionable prediction |
| NLU 2 | `_detect_flow` | the ensemble detects `brainstorm` {39D} |
| NLU module | `think` | since PEX made no prediction, there is no possible conflict, so NLU directly places {39D} on the stack |
| NLU 3 | _fill_slots() | NLU predicts slots for brainstorm and runs `fill_slot_values()` |
| NLU module | `validate()` | makes sure slot-values are valid, writes the detected flow as an entry in the scratchpad |
| PEX module | `understand` | hits hook point 1, reads `world.state.flow_name(string=False)` to get {39D} |
| PEX module | `execute` | execute the `brainstorm` policy |
| PEX 4 | policy sub-agent | `brainstorm` comes up with some ideas |
| PEX module | — | we've already incorporated NLU feedback at hook point 1, so no further actions at hook point 3 |
| PEX 5 | manage_flows() | skipped |
| PEX module | `verify()` | same |
| Assistant | `take_turn` | same |
| PEX 6 | `respond` | same |
| MEM module | `start()` | system turn added: completed: brainstorm |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |


### S9 — Differing Intent: NLU dominates and re-routes

Currently iterating on an outline. Empty stack to start
User Utterance: "The second section needs to go deeper into the trade-offs between scalability and persistence since more nodes is harder to reconcile."
PEX predicts Revise intent, but NLU disagrees completely. 

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | empty stack |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | System-1 sense: Revise - clear intent |
| Assistant | run NLU | passes Revise along |
| NLU module | `check` | maps to 'write', stores {003} into pred flows |
| PEX module | — | clear domain intent → map Revise intent to {003} |
| PEX 2 | - | skipped, stack is empty when PEX agent tries to run |
| NLU 2 | `_detect_flow` | the ensemble detects `refine` {02B} |
| NLU module | `think` | since PEX made a conflicting decision and the disagreement is at intent level, the current 'write' flow is marked Invalid, then NLU runs `stackon(refine)` to override PEX's decision |
| NLU 3 | _fill_slots() | NLU predicts slots for 'refine' and runs `fill_slot_values()` |
| NLU module | `validate()` | makes sure slot-values are valid, notifies that a new flow has replaced PEX's detected flow as a scratchpad entry |
| PEX module | `execute` | hits hook point 1, but is unaware of the issue yet, so PEX stackon('write') → runs the `write` policy |
| PEX 4 | policy sub-agent | `write` attempts to change the outline |
| PEX module | — | possibly hits a violation or error since write shouldn't be able to operate on outlines. In any case, hook point 3 is triggered — the top is a different intent, so code re-routes without notifying the agent. |
| PEX 5 | manage_flows() | skipped, since this is a different intent, NLU prediction always overrides, so PEX agent is not needed to make any decisions. Immediately execute `refine` policy.  |
| PEX module | `verify()` | run verification against 'refine' results, complete the flow |
| PEX 6 | `respond` | same |
| Assistant | `take_turn` | same |
| MEM module | `start()` | system turn added: completed: refine |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

`execute()` has no I/O dependency, so its code-based `stackon('write')` typically lands before
NLU 2's three detection calls finish — that is how `think` finds a write flow to mark Invalid.
Any remaining race is PEX 5's to clean up.

### S10 — Pure click

The frontend sends dax + payload, no text. Suppose the flow is audit {13A}

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | dax present, no text → op=react |
| PEX module | `prepare` | the `_execute_click` path (pex.py:317) — no agent loop this turn |
| PEX 1 | `_run_loop` | skipped |
| Assistant | run NLU | op=react goes straight to NLU |
| NLU module | `check` | stores the dax from the user |
| PEX module | — | skipped |
| PEX 2 | - | skipped |
| NLU 2 | `_detect_flow` | skipped — the dax names the flow, no detection needed |
| NLU module | `think` | `react` (nlu.py:178) instead: dax→flow; payload slices unpacked |
| NLU 3 | slot-fill | only if the payload left the flow unfilled |
| NLU module | `validate()` | belief written at confidence 0.99; the resolved flow goes straight to the runtime |
| PEX module | `execute` | `stackon('audit')` → policy starts → policy will run `fill_slots_by_label` |
| PEX 4 | policy sub-agent | the audit sub-agent uncovers and fixes AI slop |
| PEX module | - | skipped, no message from NLU |
| PEX 5 | — | skipped |
| PEX module | `verify()` | checks pass; complete; `pop` |
| PEX 6 | `respond` | same |
| Assistant | `take_turn` | audit might be multi-turn, ask user for feedback → hand control to MEM |
| MEM module | `start()` | system turn added: active: audit |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

### S11 — PEX 2 gates a stackon over live work

`summarize` is Active and incomplete, mid-summary on post A. "Ha, I could never get my
conclusions this tight." PEX 1 reads the turn as banter, so its prediction differs from the
Active flow — the one case where PEX 2 is not skipped.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | `summarize` is Active |
| PEX module | `prepare` | same |
| PEX 1 | `_run_loop` | System-1 sense: Converse — banter, not task content |
| Assistant | run NLU | passes Converse along |
| NLU module | `check` | stores {000} |
| PEX module | — | clear intent → map Converse to chat {000} and proceed |
| PEX 2 | manage_flows() | fires: the stack has an Active `summarize` and PEX 1 predicted a different flow. With the Workflow Planner skill it makes the final call — here it accepts the sense and runs `stackon('chat')`. It could equally have judged the remark mid-task noise and continued `summarize`. |
| NLU 2 | `_detect_flow` | ∥ the vote lands on `chat` too |
| NLU module | `think` | PEX 2's stackon has already landed, so the top is `chat` — same flow, go straight to validate() |
| NLU 3 | - | skipped — `chat` has no slots |
| NLU module | `validate()` | add aligned entry into Session Scratchpad |
| PEX module | `execute` | run the `chat` policy |
| PEX 4 | policy sub-agent | `chat` runs trivially — the streamed reply is its execution — and completes |
| PEX module | — | the hook-3 read shows the aligned entry |
| PEX 5 | manage_flows() | skipped — NLU and PEX aligned, nothing to decide |
| PEX module | `verify()` | the code pop() clears the completed {000}; the `summarize` underneath reactivates — the turn ends with it as the incomplete Active top |
| PEX 6 | `respond` | same |
| Assistant | `take_turn` | same |
| MEM module | `start()` | system turn added: completed: chat · active: summarize |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

---

## Wiring problems found during review

1. **`understand` op="contemplate" was promised but not wired.** The PEX Agent prompt
   (for_orchestrator.py:146-151) instructs calling `understand` with op="contemplate" after a
   partial stall, but the tool schema only allows `op: 'read'` (pex.py:1042-1046) and
   `_understand_user` (pex.py:720) ignores `op` and returns a state read — the model silently gets
   the wrong data. **Decision: wire it now.** `understand(op='contemplate')` is the tool-call
   signature; the implementation routes through the shared component surface
   (`self.world.state.contemplate()`), not a module-to-module call — the re-route logic currently
   in `nlu.contemplate` (nlu.py:165) moves behind that surface. Open detail for review: the
   re-route makes an LLM call, so the component surface needs engineer access (the same way the
   Ambiguity Handler's `recover` is an NLU-owned component that PEX already calls through the
   World).
2. **A Pending detection runs instead of the flow the PEX Agent named.** `_top_policy`
   (pex.py:620-629) always activates the top of the stack, so a continue write (update
   status='Active', even naming the buried flow) runs whatever NLU last placed. **Decision:
   superseded by the message-passing redesign** — every flow NLU stacks is resolved in the same
   turn at PEX's hooks (run or popped), so nothing NLU placed can linger for a later continue
   write to bypass. `_top_policy`'s top-activation stands unchanged.
3. **`SourceSlot.add_one` erases fields on update.** When updating an existing `post-sec` entity,
   `add_one` overwrites `snip`, `chl`, and `ver` with the incoming call's defaults
   (slots.py:124-139). **Decision: leave `add_one` unchanged; compensate in entity repair** —
   3.4.2's entity repair reads the current entity first and always passes the complete entity in
   one `add_one` call (entity parts travel together).
4. **The forced intent fallback in `inject_belief_state` is unreachable.** The branch
   (pex.py:659-669) fires only when a flow with a different domain intent is still Active when
   the loop reads the note. No current path produces that shape: whenever NLU detects a
   different flow, `_stack_detected_flow` has already placed the detection and reverted the
   Active flow to Pending, so `get_flow(status='Active')` returns None; the fill-active and
   Converse paths keep the flow Active but never carry a different domain intent. **Decision:
   the branch retires along with `inject_belief_state` itself** — 3.4.1's scratchpad message
   and dominant re-route replace the context note entirely (Derek, 2026-07-11: drop functions,
   use existing primitives).

## Out of scope

- Continue-intent coordination and voter composition.
- Same-type entity dedupe, which remains a FlowStack/PEX task in Round 2.13.
- Policy-side snippet discovery after NLU correctly leaves a descriptive `snip` empty.
- Dealing with retries with contemplate when the sub-agent hits an issue
- Handling routing and recovery due to ambiguity. This requires working much more closely with MEM.

## Verification

1. Add focused NLU and PEX handoff tests for the two `validate` outcomes: the aligned fill, and
   the stacked divergence resolved by PEX (run or pop) — exercised for same-intent,
   different-intent, and Converse detections.
2. Add schema, entity-repair, and end-to-end entity-refill tests.
3. `run_suite.py --tests` remains green.
4. Replay `B02.C15` and the round-3.3 active-answer trace cases.
