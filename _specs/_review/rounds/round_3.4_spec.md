# Round 3.4 — NLU ↔ PEX Flow Handoff and Grounding Slot-Fill

Maps to **Master Plan · Round 3 (NLU)**. This round repairs the boundary where NLU turns a
prediction into live flow state for PEX. The Canonical Turn, the Scenario Walkthroughs, and the
Threaded Turn are background; the Major Themes (3.4.1-3.4.8) are the changes, grouped by theme
and each broken into concrete tasks in the Todo List at the bottom. Design decisions settled
with Derek (2026-07-11 / 14 / 15 / 16) are folded into the themes; Unresolved Issues, right
above the Todo List, is now a resolution record — nothing is open.

---

## Canonical Turn

One turn is not a strict sequence. The Assistant opens the turn with one synchronous call —
`nlu.classify_intent`, the fast TypeSafe System-1 intent model — and then two lanes run: NLU's
policy prediction (flow detection, the System-2 authority) and the PEX Agent's acting loop,
which reads the classified intent rather than deriving one. Modules never call each other; they
share components through the World, and control passes between the lanes at four touch points,
all deterministic code (dialogue_state.md § Predicting the Belief State):

1. **The classified intent** (Assistant → `nlu.classify_intent` → state) — Assistant code,
   rather than a tool argument. The Assistant calls `classify_intent` before either lane starts;
   `classify_intent` stores the prediction on the state, where `check` reads it before thinking
   starts and PEX reads it to map intent → basic flow (`intent2flow` in utils/helper.py — the
   {000}-{004} mapping is definitional). If an Active flow is on the stack, then the set of
   valid intents appends Continue as another option. 'Continue' itself is never stored: the
   classifier maps it to the Active flow's intent before writing `pred_intent` (audit Active +
   Continue → 'Revise'), so a Continue reading downstream is pred_intent matching the belief
   flow's own intent. On a Continue reading the flow's name serves as a strong prior for NLU,
   and the classified intent seeds the vote as one med-tier voter. Plan and Clarify carry no
   real signal, so detection runs over the full ontology.
2. **The scratchpad message** (NLU `validate` → the policy's hook points) — `validate` ends
   NLU's thinking by writing to the Session Scratchpad: an aligned entry when the flows match,
   or an entry announcing the flow NLU has already stacked (with its rationale) when they
   differ. A hook point is a module-code read of the Session Scratchpad that decides whether
   anything warrants notifying the PEX agent. Entries are checked at every hook point — the
   loop matches each entry's metadata (origin, turn_number, used_count) WITHOUT calling
   `read()`, since reading is consuming; only an entry that matches a filter is read()
   (Unresolved 2, 2026-07-17). Points 1, 2, 4, and 6 currently filter for nothing specific,
   so today only hooks 3 and 5 carry a read in code; a later round adds the matching loop at
   1, 2, 4, and 6 when it inserts additional
   filters there. Hook point 3 (post-tool-call) or 5 (post-LLM), whichever comes first, looks
   for messages from NLU that emanated from `validate`. A different-intent top is handled
   by that code directly — the new flow runs and the agent is never notified. A same-intent
   conflict goes to the agent: PEX 5 decides at that hook — run the new flow, or decline it
   (update it to Invalid, then pop). Hook
   point 6 is `verify()` itself, where code pops completed flows deterministically; PEX 5 never
   runs there. This replaces `inject_belief_state`'s context note, which retires.
3. **The blocking read** (PEX module → NLU) — Plan and Clarify are the only intents that wait:
   `prepare()` — hook point 1, the opening of `execute` — blocks until NLU's thinking settles,
   and the agent then reads with `understand(op='read')`.
   The update arrives through the stack, never the belief: a Plan turn arrives already stacked
   (`think` stackons every step — NLU-owned work PEX reviews and runs), and a Clarify turn
   arrives with the pending question to relay. Every other intent starts its read-only work
   without waiting.
4. **The failed-flow re-route** (policy stall → Assistant → NLU) — if a policy stalls due to
   any error violation, the agent calls `understand(op='contemplate')`. The tool does NOT call
   NLU (modules are not attached to the World — no `nlu.world.nlu.state` recursion): it queues
   the request as a scratchpad entry and ends PEX's pass; the Assistant reads the request and
   calls `nlu.contemplate()`, then re-enters PEX (the existing back-to-PEX-2 loop). NLU
   re-detects over the failed flow's edge flows and stacks the re-route. Contemplation is a
   recovery move, not a planning one — it never runs before the policy has.

Every LLM input is a prompt built by code; every LLM output is a schema-constrained JSON object
(NLU) or a tool call / plain text (PEX), and code executes each tool call. Clarification
questions never bubble up as errors — they ride inside tool results as `question` and the PEX
Agent relays them. Only exceptions bubble to `take_turn`'s safety net.

Phase names carry the execution model. `PEX n` / `NLU n` / `MEM n` rows are agent actions —
async LLM moves; `PEX module` / `NLU module` / `MEM module` rows are plain code, synchronous.
The numbers are shared time slots: rows with the same number run largely concurrently (NLU 2's
flow detection alongside PEX 2's flow management), and everything follows NLU 1
(`classify_intent`) because both lanes read its intent.

The module surfaces are canonical (architecture.md). Each module has ONE tool-call name, a few
main methods, and pre/post verbs that bookend its main path; the heavier machinery lives on
the components each module owns:

| module | tool-call name | main methods | bookends | component methods |
|---|---|---|---|---|
| NLU | `understand(op=x)` | react, think, contemplate | `think`: check → detect_flows → fill_slots → validate | DialogueState: classify_intent, detect_flows, fill_slots |
| PEX | `manage_flows(op=x)` | append_to_scratchpad, read_from_scratchpad, execute | `execute`: prepare (hook point 1) → … → verify (hook point 6) | FlowStack: stackon, fallback, update_flow, pop |
| MEM | `remember(op=x)` | recap, recall, retrieve (L1/L2/L3) | `recap`: start → … → finish | — |

`validate` includes repairing incorrect slots by rule, and every flow has an entity slot —
but there is no 'entity repair' concept: there is only filling open slots (`fill_slots`, which
treats the entity slot like any other slot) and validate's rule-based repair after.

The turn at a glance — the Assistant's `take_turn` wraps the whole turn; the three modules are
columns; time flows down; PEX 2 and NLU 2 run concurrently (`∥`):

```
Assistant · take_turn ═ the wrapper around the whole turn ═══════════════════════════════════════
  open: ambiguity ask-count reset · save the user turn (MEM) · route to PEX

   PEX                              NLU                           MEM
   ───                              ───                           ───
                                                                  add_turn(user utterance)
                                    NLU 1   classify_intent: the TypeSafe System-1
                                            intent — the Assistant's one synchronous call
Assistant · run NLU ─ start NLU's thinking ─▶
                                    module  check(): clear prior ambiguity ·
                                            pick the intent's prompt snippet
   module  prepare() — hook point 1, opening execute:
   clear intent → proceed at once
   Plan/Clarify → block here on NLU's settled work
   PEX 2   manage_flows()      ∥    NLU 2   detect_flows + tally
   gates a stackon over an
   Active flow; usually skipped
                                    module  think(): same flow → continue,
                                            else create + stackon() the new flow
                                    NLU 3   slot-fill (fill_slots)
                                    module  validate() — one of two:
                                     1 same flow → fill it + aligned entry
                                     2 new flow  → already stacked; slots
                                                   filled + entry announcing it
   module  execute(): code stackon of the basic flow —
   no I/O wait, lands during NLU 2; the policy runs on
   the agent's first stack action
   PEX 4   policy sub-agent (llm_execute)
           ├ hook point 2 · pre-tool — before each tool call
           │   [tool executes]
           ├ hook point 3 · post-tool — read the Scratchpad
           └ hook point 4 · tool-retry — pre-tool, retries only
   module  hook point 5 · post-LLM — the Scratchpad read when
   the sub-agent called no tools. Hook 3: different intent
   → code re-routes, agent not notified. Hook 5: no policy
   is mid-run to displace — any announcement goes to the agent
   PEX 5   manage_flows(): same-intent conflicts only, at
           hook 3/5 — run the new flow or pop() it; else skipped
   module  verify() — hook point 6: checks + the code pop()
   PEX 6   respond: generate the reply from popped flows
     │
Assistant · wrap-up ─ send the reply · save the agent turn (MEM) ─▶ add_turn(agent utterance)
  Pending flows remain → back to PEX 2; otherwise MEM recap():
                                                                  module  start(): add the system
                                                                          turn · reset is_newborn
                                                                  MEM 7   _compaction + _promote
                                                                  module  finish(): save state.json
                                                                          · turn-end shape check
```

| phase | method | role |
|---|---|---|
| Assistant | `take_turn` (assistant.py:40) | save the user utterance as a turn within MEM, per-turn ambiguity ask-count reset, route to PEX module |
| NLU 1 | `classify_intent` | the turn's first model call — the fast TypeSafe System-1 intent, called synchronously by the Assistant; the prediction lands on the state for both lanes to read |
| Assistant | run NLU | start NLU's thinking (the worker thread in the threaded turn) |
| PEX module | `prepare()` (pex.py:280) | hook point 1, the opening of `execute`: per-turn setup code (note/read budgets reset, the turn's opening turn_id captured); on a Plan/Clarify classification it blocks here until NLU's thinking settles, then the bounded loop is entered |
| NLU module | `check()` | Opens `think` with the preliminary work: resolve prior ambiguity (round 3.4: ALWAYS cleared — dynamic resolution comes in a later round) and pick the extra detection-prompt snippet straight from `dialogue_state.pred_intent` — nothing is passed in; a Continue reading (pred_intent matching the belief flow's intent — 'Continue' is never stored) names its flow via the belief's `flow_name()`, and Continue renders a very different template than Plan or Clarify |
| PEX module | — | If classify_intent output a clear domain intent (ie. Research/Draft/Revise/Converse/Publish/Continue), then proceed to the agent to perform Workflow Planning immediately. In contrast, if it output Plan or Clarify, `prepare` (hook point 1) blocks until NLU settles. The intent→flow mapping is definitional: each intent maps to its basic flow — Converse→chat {000}, Research→find {001}, Draft→outline {002}, Revise→write {003}, Publish→release {004}. Flow names vary by domain; the dax codes do not. Finer-grained flows are NLU's to choose. |
| PEX 2 | manage_flows() | the agent's first move. Meaningful when the stack already has an Active flow and classify_intent predicted a different intent: PEX 2 double-checks that result with the Workflow Planner skill and makes the final flow-management call — a stackon over live work is gated by this second look. Skipped when the stack is empty or the turn is a plain Continue (no model call; `execute()` code handles those). Prompt-only — PEX 2 and PEX 5 are the same agent, no new code. |
| NLU 2 | `detect_flows` + tally (DialogueState) | ensemble flow detection — 2-5 voters, confidence = voter agreement; candidates narrow by `pred_intent` read directly off the belief (on a Continue reading, the belief's flow + its edges, with the seeded vote); on a low-confidence cross-intent split, `classify_intent` tie-breaks by writing `pred_intent` and one narrowed re-detect runs |
| NLU module | `think` (nlu.py:111-134) | check → detect_flows → fill_slots → validate is all inside think. With check()'s setup done and detection in, NLU does its own thinking. If the flow stack already has a flow and NLU detected the same one, then just continue with it. This is NLU's version of the Continue intent. Otherwise, create a new flow to fill and stack it on directly with `world.flows.stackon()` — any disagreement, same intent or different, is resolved on PEX's side. |
| NLU 3 | slot-fill call in `fill_slots` (DialogueState) | fill missing slots; let the schema decide what needs filling — the entity slot is treated like any other slot |
| NLU module | `validate()` to end the thinking (nlu.py:209) | validation includes rules-based slot repair, writing the predicted belief to the state. If NLU detected the same flow as PEX, the fill already landed on that existing flow (the fill covers the OPEN slots per 3.4.2's eligibility — a filled slot is never overwritten; `_repair_slots` polices contradictions, and PEX never writes slots); append an aligned entry to the Session Scratchpad. If NLU detected a different flow, the flow is already on the stack from `think` with its slots filled; the scratchpad entry announces it with NLU's rationale. |
| PEX module | `execute()` | on a Plan/Clarify classification, `prepare` (hook point 1) has already blocked until NLU settled, and the agent reads the stacked result. It is still too early for contemplation. PEX calls update, stackon, fallback or pop as commanded. The policy is started. `execute()` has no I/O dependency, so its code-based stackon of the mapped flow is likely already done before NLU 2's detection calls finish; any race is PEX 5's to clean up. |
| PEX 4 | policy sub-agent — `llm_execute` (policies/base.py:61) | the sub-agent executes the flow's task with its scoped tools; This is technically the sub-agent, rather than the agent running. |
| PEX module | — | After a policy run returns from its tool call (hook point 3) or after a no-tool LLM reply (hook point 5), whichever comes first, module code waits for NLU's response. A hook is a module-code read of the Session Scratchpad checking whether anything warrants notifying the PEX agent. A different-intent top needs no agent decision — the code re-routes and the new top runs (back to PEX 4); the agent is never notified. A same-intent conflict is the one thing surfaced to the agent. |
| PEX 5 | manage_flows() | the same agent as PEX 2 decides same-intent conflicts only — given the flow_stack, the status of the Active flow, and NLU's scratchpad messages: run the new flow, or pop() it and stay; update, stackon, anything it needs. Different-intent re-routes never reach it, since code already handled them. It decides at the hook that surfaced the conflict — 3, or 5 when no tool ran — and never at hook point 6. On most turns there is no conflict and PEX 5 is skipped. |
| PEX module | `verify()` | hook point 6, the verification hook: wrap up the policy by running any verification checks; code pops Completed and Invalid flows deterministically — no agent call |
| PEX 6 | `respond` | feed popped flows to the agent to generate agent response |
| Assistant | `take_turn` (assistant.py:84-86) | send agent response + artifact blocks to frontend, save the agent utterance as a turn within MEM, if flow_stack still has pending flows go back to PEX 2 to loop, otherwise hand control to MEM by running recap() |
| MEM module | `start()` | add the system turn into Context Coordinator (completed flows · the active flow · the grounded post), reset is_newborn on every remaining flow, clears consumed grounding choices, bumps the turn count |
| MEM 7 | `_compaction` + `_promote` (mem.py:80) | when prompt-token usage crosses the threshold, summarize the message middle; decide if any content from Scratchpad is promoted as a record into User Preferences or as a document into Business Knowledge |
| MEM module | `finish()` | save a snapshot into state.json, check turn-end shape, compaction trigger read |

---

## Scenario walkthroughs

Eleven single-turn traces, each expanded over the Canonical Turn's phase rows — same rows, same
order. A row reading "same" matches the standard turn exactly; the spelled-out rows are what
make the scenario unique. S3-S6, S9, and S11 exercise this round's contracts; S7 (Plan) and S8
(Clarify) live in round_3.5_spec.md with the rest of the plan/clarify work, keeping the shared
S numbering.

### S1 — Fresh task, clean run

"Put together an outline for a post on container gardening." Empty stack.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | empty stack; op=think; route to PEX module first |
| NLU 1 | `classify_intent` | intent: Draft — clear |
| PEX module | `prepare` | same |
| Assistant | run NLU | starts NLU's thinking |
| NLU module | `check` | picks the Draft detection snippet (basic flow outline {002}), starts thinking |
| PEX module | - | clear domain intent → map Draft intent to outline {002} flow |
| PEX 2 | - | skipped, stack is empty so no model call needed to manage workflow |
| NLU 2 | `detect_flows` | full-ontology candidates; the vote converges on `outline` |
| NLU module | `think` | since detected flow matches PEX, go straight to validate() |
| NLU 3 | N/A | skipped, since detected flow matches PEX |
| NLU module | `validate()` | add aligned entry into Session Scratchpad |
| PEX module | `execute` | `stackon('outline')` → policy starts → policy will run `fill_slots_by_label` |
| PEX 4 | policy sub-agent | the outline sub-agent drafts and saves |
| PEX module | — | the hook-3 read shows the aligned entry → proceed |
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
| NLU 1 | `classify_intent` | intent: Continue |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | picks the Continue detection snippet — the Active `release` is the strong prior |
| PEX module | — | Continue is clear → proceed |
| PEX 2 | - | skipped, Continue doesn't need a new flow |
| NLU 2 | `detect_flows` | suppose the vote lands on `release` |
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
| NLU 1 | `classify_intent` | intent: Continue |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | same |
| PEX module | — | Continue is clear → proceed |
| PEX 2 | - | skipped, Continue doesn't need a new flow, PEX doesn't know about disagreement yet |
| NLU 2 | `detect_flows` | vote lands on `write` because the scope has narrowed to a snippet, now there is contention |
| NLU module | `think` | create a `write` {003} flow and stack it on directly |
| NLU 3 | `fill_slots` | slot-filling stores `post=A, sec=intro, snip=[2, 5]` using `fill_slot_values()` **follow 3.4.2**  |
| NLU module | `validate()` | rules-based slot repair verifies the post/sec identity and validates the slice; entry added to Scratchpad notifying a new flow was added |
| PEX module | `execute` | no wait, since the classified intent was Continue → policy starts; no slot-filling occurs because rework only need `sec` to proceed |
| PEX 4 | policy sub-agent | operates on the narrowed span to apply the fix |
| PEX module | — | hits hook point 3, mis-alignment finally discovered |
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
| NLU 1 | `classify_intent` | intent: Continue |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | same |
| PEX module | — | Continue is clear → proceed |
| PEX 2 | - | skipped, Continue doesn't need a new flow |
| NLU 2 | `detect_flows` | a vague description is not a snippet-narrowing signal — the vote stays on `rework` |
| NLU module | `think` | same flow → go straight to validate() |
| NLU 3 | `fill_slots` | runs as always; rework's `source` is filled (its entity part `sec` is grounded), so the schema leaves it out — and a descriptive phrase is not a `snip` id anyway |
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
| NLU 1 | `classify_intent` | intent: Continue |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | same |
| PEX module | — | Continue is clear → proceed |
| PEX 2 | - | skipped, Continue doesn't need a new flow, PEX doesn't know about disagreement yet |
| NLU 2 | `detect_flows` | vote lands on `compose` because NLU thought the user wanted to convert outline to prose |
| NLU module | `think` | create a `compose` {3AD} flow and stack it on directly |
| NLU 3 | `fill_slots` | slot-filling stores the post using `fill_slot_values()` (compose's `source` is post-level) |
| NLU module | `validate()` | entry added to Scratchpad notifying a new flow was added |
| PEX module | `execute` | no wait; since the classified intent was Continue → policy starts |
| PEX 4 | policy sub-agent | `refine` keeps polishing the paragraph, unaware the user asked to convert the outline to prose |
| PEX module | — | hits hook point 3, mis-alignment finally discovered |
| PEX 5 | manage_flows() | Since this is same intent, PEX agent gets to decide what to do. It can pop {3AD} from the stack and proceed with just refine {02B}; Or it can `update_flow(flow_name='refine', status='invalid')` and proceed with compose {3AD}. |
| PEX module | `execute` | In this case, PEX agent decides to accept NLU's suggestion. Thus, PEX now executes the 'compose' policy by going back to PEX 4 step. Eventually, it pops both {3AD} because it is completed and {02B} because it is invalid |
| PEX 6 | `respond` | same |
| Assistant | `take_turn` | no Pending flows remain → hand control to MEM |
| MEM module | `start()` | system turn added: completed: compose · active: none (the checkpoint lists completed/active only — pop discards Invalid flows silently) |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

### S6 — NLU picks different-intent flow from PEX

`refine` Active; "ha, fair point!"

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | `refine` is Active |
| NLU 1 | `classify_intent` | reads the turn as approval of the task in progress — Continue |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | same |
| PEX module | — | proceed — the sense is Continue, not Converse |
| PEX 2 | - | skipped, Continue doesn't need a new flow |
| NLU 2 | `detect_flows` | the vote lands on `chat` (Converse) |
| NLU module | `think` | create a `chat` {000} flow, marks the underlying 'refine' {02B} flow as Pending, automatically push the new flow on top of the stack |
| NLU 3 | `fill_slots` | this is a no-op though because `chat` has no slots |
| NLU module | `validate()` | entry added to Scratchpad notifying a new flow was added |
| PEX module | `execute` | no wait; since the classified intent was Continue → execute `refine` policy |
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

### S7 and S8 — Plan and Clarify (moved to round 3.5)

The Plan and Clarify walkthroughs live in round_3.5_spec.md with the rest of the
plan/clarify work (the decomposition, the missing detection prompts, and the two
items T21 carried over). The S numbering is shared across both files.

### S9 — Differing Intent: NLU dominates and re-routes

Currently iterating on an outline. Empty stack to start
User Utterance: "The second section needs to go deeper into the trade-offs between scalability and persistence since more nodes is harder to reconcile."
classify_intent predicts Revise, but NLU's detection disagrees completely. 

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | empty stack |
| NLU 1 | `classify_intent` | intent: Revise — clear |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | picks the Revise detection snippet (basic flow write {003}) |
| PEX module | — | clear domain intent → map Revise intent to {003} |
| PEX 2 | - | skipped, stack is empty when PEX agent tries to run |
| NLU 2 | `detect_flows` | the ensemble detects `refine` {02B} |
| NLU module | `think` | NLU runs `stackon(refine)` over the stacked 'write' flow (from the classified Revise) — write reverts to Pending beneath it; after refine completes, write surfaces as `next_flow` and the agent declines it (Invalid + pop) |
| NLU 3 | fill_slots() | NLU predicts slots for 'refine' and runs `fill_slot_values()` |
| NLU module | `validate()` | makes sure slot-values are valid, notifies that a new flow has replaced PEX's detected flow as a scratchpad entry |
| PEX module | `execute` | prepare (hook point 1) doesn't block on a clear Revise — PEX is unaware of the issue yet, so stackon('write') → runs the `write` policy |
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
NLU 2's three detection calls finish — that is how `think` finds a write flow to stack over.
Any remaining race is PEX 5's to clean up.

### S10 — Pure click

The frontend sends dax + payload, no text. Suppose the flow is audit {13A}

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | dax present, no text → op=react |
| NLU 1 | `classify_intent` | skipped — the dax names the flow, nothing to classify |
| PEX module | `prepare` | the `_execute_click` path (pex.py:317) — no agent loop this turn |
| Assistant | run NLU | op=react goes straight to NLU |
| NLU module | `check` | skipped — the react path needs no detection setup |
| PEX module | — | skipped |
| PEX 2 | - | skipped |
| NLU 2 | `detect_flows` | skipped — the dax names the flow, no detection needed |
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
conclusions this tight." classify_intent reads the turn as banter, so its prediction differs
from the Active flow's intent — the one case where PEX 2 is not skipped.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | `summarize` is Active |
| NLU 1 | `classify_intent` | intent: Converse — banter, not task content |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | picks the Converse detection snippet |
| PEX module | — | clear intent → map Converse to chat {000} and proceed |
| PEX 2 | manage_flows() | fires: the stack has an Active `summarize` and classify_intent predicted a different intent. With the Workflow Planner skill it makes the final call — here it accepts the sense and runs `stackon('chat')`. It could equally have judged the remark mid-task noise and continued `summarize`. |
| NLU 2 | `detect_flows` | ∥ the vote lands on `chat` too |
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

## Threaded Turn

`take_turn` runs the two lanes for real — NLU on a worker thread, PEX on the main thread. No
stack lock: whichever module reaches the stack first, the other converges. Settled decisions:
threads now, not later; the wait primitive is `world.nlu_done = threading.Event()`, with a TODO
in the code listing the polling alternative so the decision is revisited once the loop works;
no wait inside NLU's `check()` — a slow check writing a false announcement is harmless, since
the hook read keys on the flow it just ran; an NLU crash on the worker thread is stored and
re-raised at the `join`, landing in `take_turn`'s existing safety net; a hook wait that expires
(30 s) fails the turn loudly — `wait()` returning False raises, landing in the same safety net.

**assistant.py — `take_turn` replaces the sequential block at :70-81.** The click path stays
synchronous (S10: `_execute_click` activates the flow react stacked, so react must finish
first).

```python
if dax:                                   # click: react is synchronous, belief lands before PEX
    self.nlu.react(dax=dax, payload=payload)
    self.world.nlu_done.set()
else:
    self.nlu.dialogue_state.classify_intent(text)        # NLU 1: TypeSafe System-1 — fast, synchronous,
                                          # writes state.pred_intent for both lanes
    self.world.nlu_done.clear()           # no hint is computed or passed here: everything
                                          # belief-related is read inside NLU (pred_intent)
    def run_nlu():
        try:
            self.nlu.think(user_text=text, payload=payload)
        finally:
            self.world.nlu_done.set()     # PEX's waits always wake, even on an NLU crash
    nlu_thread = threading.Thread(target=run_nlu, daemon=True)
    nlu_thread.start()
utterance = self.pex.execute(self.system_prompt, dax=dax, payload=payload, text=text)
if not dax:
    nlu_thread.join()                     # a turn never ends with NLU mid-write
```

The race, accepted: PEX's first stackon and NLU's can land in either order, and both orders
converge. If PEX stacks `outline` first, `think` finds it Active and fills it in place
(aligned). If NLU wins, PEX's later `stackon('outline')` hits the same-type dedupe
(stack.py:32-38) and returns NLU's flow, which already carries the slots NLU filled — no
code-side folding step. The remaining case — a divergent NLU stackon landing mid-policy — is
exactly what the hook read (3.4.6) resolves.

---

## Major Themes

### 3.4.1 — Flow handoff: message passing between NLU and PEX

#### Problem

Evidence from the round-2.12 evaluation: `B02.C15` ended with a five-deep Pending tower
(`rework, audit, audit, write, release`). NLU places every detection on the stack through
`_stack_detected_flow`, but PEX does not necessarily accept and run every prediction NLU places.
When PEX asks for grounding or otherwise responds without running the proposal, the Pending flow is
left on the shared stack. Repeated turns accumulate more proposals; the turn-end invariant warning
fired 13 times in the cited run.

A Pending top is not harmless residue. The permanent planner contract requires each turn to end
with either an empty stack or an incomplete Active top, with intentional Pending work only beneath
it. NLU uses that shape on the next turn to decide whether to fill an existing flow or place a new
one. PEX reads the top of the same stack to decide what to execute, and FlowStack uses it for transfer and dedupe.
A stale proposal can therefore receive a later answer, transfer slots into an unrelated task,
suppress a legitimate push, or eventually run despite never being accepted.

#### Root Cause

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

#### Solution Contract

NLU stops leaving unresolved proposals. No new field, no new stack operation, no turn-end
cleanup — existing primitives only. NLU's flow detection (within `think()`) ends with exactly one of two outcomes:

1. **Same flow** as the one on the stack → fill that existing flow's OPEN slots (3.4.2's
  eligibility: a filled slot leaves the fill schema and is never overwritten; `_repair_slots`
  polices contradictions with the grounded entity, and PEX never writes slots) and append an
  aligned entry to the Session Scratchpad. No stack change.
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

Plan turns have some additional work, but are not an exception (S7):
  * `think` will stackon multiple flows at once
  * `think` will _additionally_ set `state.has_plan = True`
  * `validate` writes an entry as it always does, but it shares that multiple flows have been added
  * PEX's blocking read at hook point 1 reads all the detected flows from the stack to get the update.

Under this contract the `B02.C15` tower cannot form: every flow NLU stacks is resolved in the
same turn — run or popped — and the resolution point is deterministic module code (the hook
1, 3, or 5 read, with hook point 6 — as the last stop), not agent goodwill. Specifically, hook
point 6 ensures the stack is either empty or has an Active flow on top: after the pop,
`activate_flow` checks the surfaced top and returns an `invalid_stack` corrective error the
agent must handle when a non-Active flow sits there (landed 2026-07-17).
Plan steps queued with `stackon(active=false)` are NLU-owned work, but PEX always get a chance to review. 
MEM's turn-end shape check (mem.py:54) remains the log-only guard for the crash window
between a stackon and its resolution.

#### Design for message passing

There is no boolean called 'proposal'. No new concepts. Instead we use existing concepts:

**PEX -> NLU**
NLU already owns the working intent (`classify_intent` predicted it). PEX talks to NLU when it calls the `understand()` tool or by appending entries to the scratchpad.

**NLU -> PEX**
   - If NLU predicted the same flow as PEX, just place a basic message in Session Scratchpad that everything is aligned.
   - If NLU predicted a different flow — same intent, different intent, or Converse — then NLU has already stacked it, so PEX can just read the top flow from the stack; the Session Scratchpad entry carries NLU's rationale. The hook code reads this message at hook point 3 (post-tool-call) or 5 (post-LLM hook). A different intent re-routes in code without notifying the agent; a same-intent conflict goes to PEX 5 — run the new flow, or pop it and stay.
In most cases, the entry is at hook point 3, but occasionally, a sub-agent might complete without calling any tools in which case we will definitely intervene by hook point 5.

#### Implementation

- `backend/modules/nlu.py` — `check` opens `think`: it clears prior ambiguity (round 3.4:
  always) and picks the detection-prompt snippet for the classified intent (already on the
  state from `classify_intent`); `think` stacks a divergent detection directly with
  `world.flows.stackon()` (a Plan detection stackons every step); `validate` writes the
  aligned, announcement, or plan entry. `_stack_detected_flow` is deleted — stacking already
  has its primitive, and every stacked flow is a detected flow, so the wrapper adds nothing.
- Session Scratchpad — carries the aligned / announcement entries through the existing
  `append_entry`; no new entry fields (the `think` divergence note at nlu.py:122-128 is the seed
  of the announcement entry).
- `backend/modules/pex.py` — the hook point 3/5 scratchpad reads (landed in `_top_policy` and
  `_run_loop`, not policies/base.py — base.py's hook framework was deleted by T12); a
  different-intent top stops the displaced policy right there in code, without notifying the
  agent. A same-intent conflict is the only thing surfaced to the agent — that resolution
  belongs to PEX 5.
- `backend/modules/pex.py` — the PEX 2 gate and the PEX 5 resolution are prompt-only changes to
  the same agent (through the Workflow Planner skill), no new code; `inject_belief_state`
  retires with its dead forced-fallback branch; `_record_checkpoint` is deleted.
- `backend/modules/mem.py` — `store_turn` becomes the wrapper: `start()` (the checkpoint as the
  System turn through `context.add_turn()`, reset `is_newborn`), then compaction and L2/L3
  promotion, then `finish()` (save the state snapshot, check the turn-end shape). Landed —
  see 3.4.4.
- Workflow Planner and Dialogue State permanent specs — document the two `validate` outcomes
  and the hook-point reads. `modules/pex.md` is already updated (2026-07-14): the loop entry,
  Who-waits-on-NLU, and signal blocks now match this round, and the belief-injection block is
  replaced by the scratchpad message.

### 3.4.2 — Whole-entity slot-fill after partial grounding

#### Problem

NLU's grounding doctrine is one complete entity object: `{post, sec, snip, chl}`. On an answer turn,
NLU should preserve the established `post`, add narrower grounding only when supported,
and return the whole entity rather than a disconnected part. In particular, `snip` is a sentence
index or end-exclusive `[start, end]` slice from `schemas/tools.yaml`; descriptive prose such as
“the rambling paragraph” is not a snippet id.

The current generic fill schema excludes every slot whose `filled` flag is true. A SourceSlot may
satisfy its minimum requirement with only `post` or `post + sec`. Once it does, the entire source
slot disappears from the Active flow's slot-fill schema. NLU cannot return the same entity with a newly
available snippet id even though the flow is still incomplete at the requested granularity.

This pressures prompts and policies into unsafe workarounds: emit only `snip`, store descriptive
text where an id belongs, ask the user again, or let the policy guess. Grounding is the safety
boundary for writes, so silently changing a post/section or inventing a snippet is worse than
declaring uncertainty.

#### Root Cause

The implementation conflates two meanings of “filled”:

1. sufficient to satisfy the flow's minimum slot requirement;
2. complete and therefore ineligible for any additional grounding.

Those meanings are not equivalent for a composite SourceSlot. `_fill_slots_schema` uses the first
meaning to enforce the second, making partial composite grounding impossible to refine.

Prompt corrections alone cannot solve this because the model cannot return a field excluded by the
JSON schema. Conversely, merely including the slot is unsafe unless code preserves stable identity
and validates snippet ids.

#### Solution Contract

Eligibility keys on the slot's declared `entity_part`: `SourceSlot.check_if_filled`
(slots.py:141-147) counts an entity only when `post` and the `entity_part` are both present, so
a `write` source (`entity_part='snip'`, flows.py:246) stays in the fill schema until a snippet
id lands, while a `rework` source (`'sec'`) stops asking once a section is grounded. Render the
current normalized entity and require a whole entity shape whenever new grounding is supplied.

Slot repair in deterministic code (`validate` — rules only; there is no 'entity repair'
concept, and `fill_slots` treats the entity slot like any other slot):

- preserve existing non-empty `post` and `sec`;
- never silently accept a different post or section on the matching Active-flow answer path;
- accept `snip` only as a valid sentence index or two-item end-exclusive slice;
- leave `snip` empty when context contains only a description;
- preserve `chl` unless the user supplies a valid channel change;
- never ask NLU to predict `ver`.

A conflicting post/section indicates that the matching-flow assumption or entity resolution needs
confirmation; it must not overwrite the live target.

#### Design: check the slot's entity part

1. As long as the slot's entity part is not filled, then include the slot as a candidate for
   filling — this is exactly what `SourceSlot.check_if_filled` already computes
   (slots.py:141-147), so eligibility is simply `not slot.filled`.
2. Do not invent new `refill_entity` parameter or other concepts. Reuse what already exists.
3. Merge _fill_slots and _fill_active_flow since these are actually the same function with the same responsibility.

#### Implementation

- `backend/modules/nlu.py::_fill_slots_schema` — eligibility is `not slot.filled`; no override
  parameter, since `SourceSlot.check_if_filled` already keys on the declared `entity_part`.
- `DialogueState.fill_slots` — absorbs `_fill_active_flow` (one function, one responsibility);
  renders the current entity in the prompt and fills every open slot alike.
- `validate` — repairs incorrect slot values by rule after the fill (`_repair_slots` +
  `_valid_snip` in 3.4.5).
- `backend/prompts/for_nlu.py` and NLU slot exemplars — show full-entity preservation and correct
  snippet-id behavior.
- `prompts/nlu/revise_slots.py` — remove any remaining snip-only or descriptive-snip examples.
- Dialogue State permanent spec — distinguish minimum flow readiness from refinable composite
  grounding.

### 3.4.3 — Belief and state substrate (landed 2026-07-15)

#### Problem

The belief slim-down (commit 77ceb5f) retired `write_state` and `pred_slots`, but pex.py and
policies/base.py still called them, `DialogueState.flow_name` crashed on a length check, and
the state kept a mirror copy of the flow stack that went stale between refreshes. `_tool`'s
except-all masked every one of these as `server_error` tool results.

#### Root Cause

The component was rewritten without updating its callers, and flow state had two owners: the
FlowStack and the state's saved copy.

#### Solution Contract

The DialogueState carries beliefs only, in one format, and the FlowStack is the single owner of
flow state:

- Each `pred_flows` entry is `{'name': str, 'dax': 3-digit str, 'confidence': 0.0-1.0,
  'rationale' (optional): str}`; `_write_belief` and every literal site write it, and
  `flow_name()` reads it. `_tally_votes` keeps one majority voter's reasoning — one line into
  `pred_flows[0]['rationale']`.
- Slot predictions live on the flow itself: NLU fills the flow it stacks, and
  `fill_slot_values` / `fill_slots_by_label` parse raw model output per flow (each flow has its
  own slot-filling prompt, so no guardrail checks). `_apply_belief_slots` is deleted;
  `_execute_click` activates the react-stacked flow instead of re-filling from belief.
- `_manage_flows` calls the FlowStack ops directly (stackon / fallback / update_flow / pop,
  plus an unknown-op raise); `complete_flow` sets `flow.status = 'Completed'` directly; per-op
  state.json writes are gone — MEM's `finish()` saves once at turn end.
- **Single flow stack (Derek, mid-review).** No `flow_stack` copy on the DialogueState — the
  one stack is `pex.flow_stack`. PEX attaches `to_list()` to the tool document at read time;
  MEM's shape check reads the live stack.

#### Implementation

`dialogue_state.py`, `nlu.py`, `pex.py`, `policies/base.py`, `trace_writer.py` — all landed.

```python
# pex.py _manage_flows, before the stack op — status case ('invalid' → 'Invalid')
if 'status' in kwargs:
    kwargs['status'] = kwargs['status'].capitalize()

# pex.py read_state / _manage_flows / _top_policy — the stack rides the tool document only
document = self.world.state.read_state()
document['flow_stack'] = self.flow_stack.to_list()
```

### 3.4.4 — MEM `start()` / `finish()` (landed 2026-07-15)

#### Problem

PEX owned the end-of-turn checkpoint (`_record_checkpoint`) while MEM had only `store_turn`,
which neither added the System turn nor reset `is_newborn` — the Canonical Turn names those MEM
module verbs.

#### Root Cause

The wrap-up grew inside PEX before MEM existed as the Head; deleting `_record_checkpoint`
without a MEM home would silently drop both behaviors.

#### Solution Contract

The turn wrap-up belongs to MEM: `store_turn` = agent turn → `start` → compaction → `finish`
(renamed `recap` by T20, matching the module surface table).

- `start(completed)` — the backward-looking System checkpoint turn (completed flows · the
  active flow · the grounded post), the `is_newborn` reset, the consumed-choices clear, and the
  turn count.
- `finish()` — the turn-end shape check on the live stack, then the state.json save.

#### Implementation

`mem.py`, `pex.py` — landed; `_record_checkpoint` deleted in the same change.

### 3.4.5 — NLU thinking becomes one path

#### Problem

One responsibility is split across ~70 lines and three functions (`think`, `_fill_active_flow`,
`_stack_detected_flow`) with a transient flow and a copy step in between, and the scratchpad
entry write sits in the middle of `think` instead of at NLU's exit.

#### Root Cause

Detection historically produced a transient flow; stacking and filling were bolted on
separately, and the fill-active path forked from the new-flow path.

#### Solution Contract

`think` is the one path: check → detect_flows → fill_slots → validate. It opens with `check`,
runs detection, stacks and fills the LIVE flow (no transient, no copy), and ends with
`validate` writing the scratchpad entry. `check` is the preliminary work now that NLU owns
`classify_intent`: resolve prior ambiguity (round 3.4: ALWAYS cleared — the dynamic,
situation-dependent version comes in a later round) and pick the extra detection-prompt
snippet for the classified intent — Continue renders a very different template than Plan or
Clarify. No hint parameter travels anywhere: the working intent IS `dialogue_state.pred_intent`,
read directly by check and by `detect_flows` (the consumer is the same component that holds
the belief), and a Continue reading names its flow via the belief's own `flow_name()`. This is
one of the wins of keeping everything belief-related in NLU — the Assistant and PEX compute
nothing for detection. Deletions paying for it: `_fill_active_flow` (nlu.py:141-153), `_stack_detected_flow`
(nlu.py:209-227), and the `incomplete` parameter on `fill_slots` (derived from
`ambiguity_handler.is_present`). Facts that stand: `_fill_slots_schema` already keys on
`not slot.filled` (zero lines change for 3.4.2's eligibility rule); `snip` stays a string in
`_ENTITY_SCHEMA` and the repair parses it.

#### Implementation

`nlu.py`, `assistant.py` (`take_turn` calls `think`/`react` directly and passes nothing but
the user turn — see the Threaded Turn sketch).

**`check()` opens `think`** — the Assistant calls `think`/`react` directly (the Threaded Turn
sketch; `understand` retires as the module entry and survives only as the name of PEX's tool).
React and Contemplate end in `validate` too — the click entry and the retry entry all have the same exit:

```python
def check(self) -> str:
    """Preliminary work for detection. Round 3.4: prior ambiguity is ALWAYS cleared here —
    the dynamic, situation-dependent resolve comes in a later round. Nothing is passed in:
    the working intent is read straight off the belief (dialogue_state.pred_intent).
    'Continue' itself is never stored — classify_intent maps it to the Active flow's intent —
    so a Continue reading is pred_intent matching the belief flow's own intent, and the flow
    name comes from flow_name(). The stack and the belief agree by design, and the Assistant
    computes nothing for NLU."""
    if self.ambiguity_handler.is_present:
        self.ambiguity_handler.resolve(explanation='superseded by the new turn')
    state = self.dialogue_state
    flow = state.flow_name(string=True)
    working = flow if (flow and intent2flow(state.pred_intent)  # only domain intents continue
                      and state.pred_intent == FLOW_ONTOLOGY[flow]['intent']) else ''
    return detection_snippet(state.pred_intent, working)   # Continue renders a very
                                          # different template than Plan or Clarify
```

**`think()` becomes one path** — check → detect_flows → fill_slots → validate;
`_fill_active_flow` and `_stack_detected_flow` are replaced:

```python
def think(self, user_text:str, payload:dict={}):
    snippet = self.check()                # ambiguity cleared; snippet keyed on pred_intent
    state, context = self.world.state, self.world.context
    detection = state.detect_flows(self.engineer, context, user_text, snippet)
    if self._intent_split(detection):     # low-confidence cross-intent split → re-classify once
        state.classify_intent(self.engineer, context, user_text)
        if intent2flow(state.pred_intent):  # domain intents only — Plan/Clarify add no narrowing
            detection = state.detect_flows(self.engineer, context, user_text,
                                           detection_snippet(state.pred_intent))
    flow_name = detection['flow_name']
    predicted = detection.get('pred_flows', [])
    if flow_name not in flow_classes:
        prev = ''
        state = self._write_non_policy_belief(flow_name, detection['confidence'], predicted)
    else:
        top = self.world.flows.get_flow()
        # An in-flight top counts whether Active or Pending — a plan step stacked with
        # active=False waits as Pending and is still the flow PEX runs next
        # (T21 fix: an Active-only check wrote a false announcement on every fresh turn).
        in_flight = bool(top) and top.status in ('Active', 'Pending')
        prev = top.name() if in_flight else ''
        if not (in_flight and top.name() == flow_name):
            top = self.world.flows.stackon(flow_name,
                                           transfer=not self.ambiguity_handler.is_present)
        state.fill_slots(self.engineer, context, top, payload, self.ambiguity_handler)
        state = self._write_belief(flow_name, detection['confidence'], predicted, top)
        if self.ambiguity_handler.needs_clarification(state.confidence):
            self.ambiguity_handler.recognize('general', ...)      # unchanged
    self.review_scratchpad()
    return self.validate(state, 'think', prev)
```

Collaborators are passed per call — `detect_flows(engineer, context, user_text, snippet)`,
`classify_intent(engineer, context, user_text)`, `fill_slots(engineer, context, flow,
payload, ambiguity)` — never stored on the DialogueState. The tie-break guard keeps the
narrowed re-detect to domain intents: a mid-turn Plan/Clarify from the nouls stores the
intent but skips the re-detect (Plan/Clarify add no candidate narrowing, and their detection
prompts are round 3.5's).

`prev` is not the retired hint: it is a fact think reads off the live stack at its own stackon
decision point — the flow PEX is running at that instant — kept only so validate can label the
entry aligned vs announcement and fill `prev_flow`. Nothing is threaded in from the Assistant,
and detection's narrowing/seeding reads `pred_intent` (and, on Continue, the belief's
`flow_name()`) directly inside the DialogueState.

~20 lines replacing what is ~70 today. Filling the live flow also means `stackon`'s transfer
has already put the current entity on it, so the fill prompt (which renders `slot.values`,
for_nlu.py:239-240) finally shows `sec` on the new-flow path too.

**`validate()` gains the ability to write an entry to the scratchpad.** Everything above the entry block is today's validate,
unchanged. Aligned means the detection equals what `check` saw. Every entry kind is written —
aligned, announcement, click with its `gold_dax`, and the plan entry (summary only, listing
the steps `think` stacked; it carries no `new_flow` key, so the hook 3/5 read never mistakes
it for a conflict — hook 1 reads the stacked plan off the flow stack itself). PEX filters by
keys (`new_flow` marks the one kind it acts on). The announcement carries NLU's rationale (one
majority voter's reasoning, from `pred_flows[0]`) and `is_newborn: true` as the consumed
marker:

```python
def validate(self, state, op='think', prev=''):
    ...                                   # ontology fallback + intent correction, unchanged
    self._repair_slots(self.world.flows.get_flow())   # rules-based slot repair (3.4.2)
    detected = state.flow_name(string=True)
    entry = {'version': 1, 'turn_number': self.world.context.turn_id, 'used_count': 0}
    if op == 'react':
        entry.update(gold_dax=state.pred_flow, summary=f'click resolved {detected} from its dax')
    elif state.has_plan:                  # plan: think stacked every step; hook 1 reads the stack
        steps = [flow.name() for flow in self.world.flows._stack]
        entry['summary'] = f"plan: stacked {' → '.join(steps)}"
    elif detected == prev:
        entry['summary'] = f'aligned on {detected}'
    elif flow is None:      # non-policy detection (clarify) — nothing stacked to announce
        entry['summary'] = f'detected {detected}; nothing stacked'
    else:
        entry.update(prev_flow=prev, new_flow=detected, is_newborn=True,
                     rationale=state.pred_flows[0].get('rationale', ''),
                     summary=f'added {detected} to the stack before completing {prev}',
                     question=self.ambiguity_handler.observation)
    self.world.scratchpad.append_entry('nlu', entry)
    return state
```

The non-policy branch matters: without it a `clarify` detection would fall into the
announcement branch and the hook read would tell the agent to run a flow that has no class.

**`fill_slots` moves onto the DialogueState** (beside `classify_intent` and `detect_flows`).
The `incomplete` parameter goes away; the handler already knows. It treats the entity slot
like any other slot — no special casing, no repair inside the fill. One behavior change to
bless: the pending-question block used to ride only the fill-active path — derived from
`is_present` it also rides a new-flow fill while an ambiguity is open, which is when its
conservative-fill guidance is wanted anyway.

```python
def fill_slots(self, flow, payload:dict={}):          # DialogueState method
    ...
        if ambiguity.is_present:                      # was: if incomplete (param deleted)
            prompt += '\n\n' + build_pending_question(ambiguity.observation,
                                                      self.grounding['choices'])
    ...
    cleaned = engineer._strip_nulls(pred_slots['slots'])
    flow.fill_slot_values(cleaned)                    # entity slot filled like any other slot
```

**There is no 'entity repair' concept.** 3.4.2's rules land as validate's slot repair: after
`fill_slots` has written the values, `validate` repairs incorrect ones by rule (no LLM). The
established entity — the live slot value before this turn's fill — is the baseline:

```python
def _repair_slots(self, flow):
    """validate's rule pass over the entity-bearing slots (every flow has an entity slot)."""
    for name, slot in flow.slots.items():
        if slot.slot_type not in ('source', 'target', 'removal') or not slot.values:
            continue
        cur, pred = ...                   # established entity vs this turn's fill — confirm the
        for part in ('post', 'sec'):      # value shape at implementation (T8)
            if cur.get(part) and pred.get(part) and pred[part] != cur[part]:
                question = f'switch {name} from {cur[part]} to {pred[part]}?'
                self.ambiguity_handler.recognize('confirmation', metadata={'question': question})
                self.world.scratchpad.append_entry('nlu', {'version': 1,
                    'turn_number': self.world.context.turn_id, 'used_count': 0,
                    'summary': f'{name} conflict on {part}: kept {cur[part]}'})
            pred[part] = cur.get(part) or pred.get(part, '')    # the live target wins
        pred['snip'] = pred['snip'] if self._valid_snip(pred.get('snip')) else cur.get('snip', '')
        pred['chl'] = pred.get('chl') or cur.get('chl', '')
        pred['ver'] = cur.get('ver', False)                     # never predicted

def _valid_snip(self, snip) -> bool:
    """Shape check only: an int index, or a two-item non-negative ascending slice, parsed from
    the string the schema emits. Range-vs-sentence-count stays execution-time."""
```

### 3.4.6 — PEX as orchestrator: decide the next action

#### Problem

PEX's responsibilities have crept. The orchestrator prompt assigns it a System-1 intent
classification as its first move, slot handover through `manage_flows` op='update', the
ask-vs-proceed recovery decision, and the `[belief]` note protocol — on top of its actual job.
`inject_belief_state` pushes a `[belief]` context note every turn whether anything diverged or
not, its forced intent fallback is unreachable (whenever NLU detects a different flow it has
already stacked it, so no different-intent flow is still Active at the read), and after a
mid-turn stack change nothing re-runs the new top — resolution rests on agent goodwill, which
is how the `B02.C15` Pending tower formed.

#### Root Cause

Belief rides the message list instead of the scratchpad contract, and policy completion has no
deterministic close (the pop waits for the agent).

#### Solution Contract

**PEX has one job: decide the next action.** Each round the agent takes exactly one stack
action (`manage_flows` — stackon, fallback, update, pop), or generates the response that ends
the turn. Generating a response IS a stack decision: it says the stack needs nothing more this
round. Relaying a clarification question is reply composition, so `ask_clarification_question`
stays in the toolset. Converse gets no carve-out (3.4.1's clause stands): a Converse intent
maps to `chat` {000} and PEX runs the chat policy like any other flow. The policy generates the
proposed response; PEX may adjust it so it does not sound like AI, but for the most part passes
it along as the terminal reply.

In service of that decision PEX reads freely: `understand` (state), the scratchpad, the pending
ambiguity, user preferences, the context coordinator, and the read-only domain tools
(`find_posts`, `read_metadata`, `read_section`, `search_notes`, `list_channels`,
`channel_status`). The old "only when belief lacks an entity" justification is dead — PEX gets
full read power to do its job. Whether all six domain tools earn their spot is a usage
question: audit from traces and remove the ones that go unused. Two optional writes:
`append_to_scratchpad` and `store_preference`.

What PEX does NOT do:

- **Slot-filling.** Broad slot-filling is NLU's job (it fills the flow it stacks); specific
  slot-filling is each flow's policy. `manage_flows` op='update' loses its `slots` field and
  the unknown-slot check — Continue becomes a pure status write.
- **Recovery.** `recover_from_ambiguity` leaves the toolset; recovery is decided by NLU or the
  individual sub-agents (re-homing it is out of scope — see Out of Scope, the MEM coupling).
- **Intent classification.** The System-1 first pass moves out of the loop prompt into
  `classify_intent` on the DialogueState component (`nlu.dialogue_state.classify_intent`), a
  fast TypeSafe model the Assistant calls before PEX runs. PEX reads
  the result; it never asserts an intent. Belief arbitration survives only in service of stack
  management — deciding to `contemplate` (a re-route request answered by NLU) is the canonical
  example and stays with PEX.

The hook reads below are the mechanics of that arbitration: one hook read per policy run, in
module code. Hook 3 fires after a tool call completes (never
mid-call) — the read sits right after `activate_flow` runs the policy; hook 5 is the same read
on `_run_loop`'s text-only branch. Together they replace `inject_belief_state`'s two call sites
(pex.py:358, 397), and the function retires with its dead fallback branch and the `_injected`
sites. The consumed marker lives on the entry itself (`is_newborn`, flipped at the consuming
read). Every policy run ends with `verify()` (today's `_verify_artifact`, renamed), then PEX
code calls `self.flow_stack.pop()` — Completed and Invalid flows leave together; the pop
belongs to PEX, never the policy. `_top_policy`'s top-activation stands (the old "Pending
detection runs instead of the named flow" concern is superseded: every flow NLU stacks is
resolved the same turn). `run_hook` / `HookDecision` / `HOOK_POINTS` in policies/base.py are
deleted — both call sites discard the result today.

#### Implementation

`pex.py` (hook reads, the toolset deltas: `slots` out of `_manage_flows`, `_recover_ambiguity`
deleted), `session_scratchpad.py` (`read()` flips `is_newborn` on the entries it returns),
`policies/base.py` (the `run_hook` deletion), `nlu.py` + `assistant.py` (`classify_intent`),
`for_orchestrator.py` (the prompt rewrite, tracked in T15).

**`_top_policy` grows the run-the-top loop**: hook 3 and the different-intent re-route are
this one loop. There is no `ran` ledger — re-running a flow within a turn is legal, and the
loop stops when the top stops changing (Unresolved 1b, 2026-07-17). A completion always ends
the pass: activate_flow's pop clears every Completed and Invalid flow in a row, and its
result carries `popped` (what left) plus `next_flow` (the surfaced top) — the agent judges
what runs next: usually `manage_flows` op='update' status='Active' to run it, or Invalid +
pop to toss it, or a fresh stackon (Unresolved 1a, 2026-07-17). That is how S6's `refine`
reactivates and re-runs — through the agent's activation, never a code chain.

```python
def _top_policy(self, state, document:dict|None=None) -> dict:
    result = None
    top = self.flow_stack.get_flow()
    while top and top.status in ('Pending', 'Active'):
        result = self.activate_flow({'flow_name': top.name()})  # verify + pop happen inside
        if not self.world.nlu_done.wait(timeout=30):            # hook 3: the post-tool read
            raise TimeoutError('NLU still thinking after 30s')  # fail the turn loudly (OQ1)
        if top.status == 'Completed':
            break   # popped in code; the agent judges what runs next (Unresolved 1a)
        new_top = self.flow_stack.get_flow()
        if not new_top or new_top.flow_id == top.flow_id:
            break   # nothing changed — the stall stands; return it to the agent
        if new_top.intent == top.intent:
            note = self._read_nlu_entry()                       # same intent → PEX 5 decides
            if note:
                result['nlu_update'] = note
            break
        top = new_top   # different intent → code re-routes (3.4.1)
    if result is not None:
        return result
    document = document or state.read_state()
    document.setdefault('flow_stack', self.flow_stack.to_list())
    return {'_success': True, 'state': document}
```

**`_read_nlu_entry` replaces `inject_belief_state`** — the flip is the scratchpad's job, not
PEX's: `SessionScratchpad.read()` flips `is_newborn` to False on every entry it returns and
persists the flip, whoever the caller is (NLU, PEX, or MEM — reading IS consuming; Derek,
2026-07-16). The returned dict carries the pre-flip value, so the filter below still works, and
PEX itself only ever calls `append_entry` and `read`:

```python
def _read_nlu_entry(self) -> str|None:
    entries = self.session_scratchpad.read(origin='nlu', keys=['new_flow'])  # read() flips is_newborn
    entry = next((e for e in reversed(entries) if e.get('is_newborn')
                  and e['turn_number'] >= self._turn_start), None)
    if entry is None:
        return None
    return (f"[nlu] {entry['summary']} — decide with manage_flows: run {entry['new_flow']}, "
            f"or decline it (op='update' with status='Invalid', then op='pop') to stay on "
            f"{entry['prev_flow']}.")
```

Declining is Invalid-then-pop, never a bare pop: `pop` removes Completed and Invalid entries
only, so popping NLU's still-Active flow is a no-op — S3 shows the correct decline.

The filter is `>=` against `self._turn_start` (captured in `prepare()` as `context.turn_id`),
never equality against the live `context.turn_id`: turn_id counts utterances, and PEX's own
tool-log turns advance it mid-loop, so an entry NLU wrote earlier in the turn would never match
an equality check.

**`_run_loop`'s text-only branch is hook 5** (replacing pex.py:358-362):

```python
if not tool_uses:
    if text:
        if not self.world.nlu_done.wait(timeout=30):  # hook 5: post-LLM, no tools ran
            raise TimeoutError('NLU still thinking after 30s')
        note = self._read_nlu_entry()
        if note:
            context.append_message({'role': 'assistant', 'content': text})
            context.append_message({'role': 'user', 'content': note})
            continue                                  # PEX 5: one more round to decide
        return text   # terminal — the Assistant appends the reply (Unresolved 3)
```

**`activate_flow`'s post-flow block gains the pop** (`verify` is `_verify_artifact` renamed;
the error/incomplete returns are unchanged):

```python
check = self.verify(artifact, flow)
...
self.completed_this_turn.append(flow)
...                                       # the completion entry, unchanged
self.flow_stack.pop()                     # hook 6: Completed and Invalid leave together, in code
return {'_success': True, 'status': flow.status, 'completion': entry, 'blocks': blocks}
```

### 3.4.7 — Contemplate via the Assistant

#### Problem

The PEX Agent prompt (for_orchestrator.py:146-151) instructs calling `understand` with
op="contemplate" after a partial stall, but the tool schema only allows `op: 'read'`
(pex.py:1042-1046) and `_understand_user` ignores `op` — the model silently gets the wrong
data.

#### Root Cause

The re-route logic lives in the NLU module (`nlu.contemplate`), and a PEX tool cannot call
another module — the request has to travel up to the Assistant, and that path was never
built; the tool schema and `_understand_user` predate it.

#### Solution Contract

`contemplate` stays a main NLU method (react / think / contemplate — the module surface
table). Modules are not attached to the World (that would make `nlu.world.nlu` legal),
so PEX has no direct path to the method. Instead `_understand_user` communicates back up to
the Assistant: on op='contemplate' it queues the request as a scratchpad entry — the
scratchpad is already PEX's write channel toward NLU (3.4.1's message-passing design) — and
tells the agent to end its pass. The Assistant reads the request after `execute` returns,
calls `nlu.contemplate()` (which re-detects over the failed flow and stacks the re-route),
and re-enters PEX through the existing back-to-PEX-2 loop. The re-route drops the LLM slot
fill — `stackon`'s transfer carries the failed flow's slots and the policy's
`fill_slots_by_label` covers gaps; the `_check_routing` + `_get_contemplate_candidates` +
`_contemplate_prompt` helpers (~60 lines) fold into `contemplate` itself. Both understand ops
wait on NLU settling (the same wait `prepare` performs at hook point 1); contemplation is a
recovery move, never a planning one — it never runs before the policy has.

#### Implementation

`nlu.py`, `pex.py`, `assistant.py`.

```python
def _understand_user(self, params:dict) -> dict:
    if not self.world.nlu_done.wait(timeout=30):      # the same wait prepare owns at hook 1
        raise TimeoutError('NLU still thinking after 30s')
    if params.get('op') == 'contemplate':             # queue for the Assistant — never call NLU
        self.session_scratchpad.append_entry('orchestrator', {'version': 1,
            'turn_number': self.world.context.turn_id, 'used_count': 0,
            'request': 'contemplate', 'summary': 'policy stalled — asking NLU to re-route'})
        return {'_success': True, '_message': 'Re-route queued. End your reply this round; '
                                              'the re-detected flow runs on the next pass.'}
    return self.read_state(params)
# tool schema pex.py:1044 — 'enum': ['read', 'contemplate']
```

```python
# assistant.py take_turn, after pex.execute returns — the same spot that loops back to PEX 2.
# turn_start is context.turn_id captured before pex.execute (same >= rule as _read_nlu_entry:
# tool-log turns advance turn_id mid-loop, so equality would never match).
requests = self.world.scratchpad.read(origin='orchestrator', keys=['request'])
if any(entry['request'] == 'contemplate' for entry in requests
       if entry['turn_number'] >= turn_start):
    self.nlu.contemplate()                # re-detect over the failed flow; stack the re-route
    ...                                   # re-enter pex.execute — the back-to-PEX-2 loop
```

### 3.4.8 — Prompts and cite

#### Problem

cite's target leaves the slot-fill schema before a snippet id lands, its exemplars teach
descriptive snips, and for_orchestrator.py still points the agent at the retired `pred_slots`
(:35, :63, :122, :129).

#### Root Cause

`TargetSlot.check_if_filled` (slots.py:189-193) ignores `entity_part`, the exemplars predate
the snip-id doctrine, and the orchestrator prompt was written against the retired belief shape.

#### Solution Contract

Align `TargetSlot.check_if_filled` with SourceSlot's entity-part rule (Q6a). Convert cite's
descriptive-snip exemplars to ids; sentence/line counts come from code-side splitting of the
section text the sub-agent already reads — no new tool (Q6b, settled 2026-07-16; reuse an
existing helper if one exists, flag to Derek if none). Add one user-supplied-range exemplar
(S3's `[2, 5]` shape) to revise_slots.py (Q6c, settled 2026-07-16). Rewrite the orchestrator
prompt's belief references to the flow's slots in
the state document, and land the PEX 2 gate / PEX 5 resolution prompt text (prompt-only — PEX 2
and PEX 5 are the same agent, no new code).

#### Implementation

`slots.py`, `draft_slots.py`, `revise_slots.py`, `for_orchestrator.py`, cite's tool menu.

### 3.4.9 - Classifying Intent with Typesafe

The exp3 report (`handling_ambiguity/results/reports/exp3_report.html`) is the evidence base: on the hugo
dataset TypeSafe beats every LLM on intent accuracy (0.824 vs 0.775 best) at ~140 ms median
vs ~2.5 s, but ambiguity read off a Choice's confidence loses to the LLMs at every
threshold — which is exactly why planning and ambiguity get their own noul questions
instead of riding the Choice's confidence.

**The call — ONE request, three questions fanned out (Derek, 2026-07-17):**
1. `intent` — a Choice across the six labels Converse / Research / Draft / Revise /
    Publish / Continue. The five domain rubrics are fixed criteria; the Continue rubric is
    built at call time naming the working flow ("The turn advances `audit`, the task already
    in progress — an answer, a detail, an approval") and is offered only when a continuable
    flow is grounded (T16's derivation: the belief flow whose intent has a basic flow).
2. `has_plan` — a noul: "Is this a multi-step plan?" (true = two or more distinct
    operations in one message, no single action covers the request; false = one covers it).
3. `needs_clarify` — a noul: "Is there uncertainty that we need to clarify?" (true = too
    vague or underspecified to act without asking; false = clear enough to act).

**Composition, in code:** if either noul ≥ 0.8 (`NOUL_THRESHOLD`), that IS the intent —
'Plan' or 'Clarify', the higher of the two when both cross. Otherwise the Choice's pick
stands, with 'Continue' mapped to the working flow's intent before the store (T16's rule,
unchanged). Failure (missing key, network, HTTP) logs and stores '' — the same fallback as
the interim LLM call; debug re-raises.

**exp3 lessons baked into the design:** the document stays lean —
`{'history': convo_history, 'utterance': user_text}` only. The v2 experiment that added
grounding context (post title, platform) cost 6.7 points of flow accuracy, so no
active_post and no exemplars ride the document. Question text stays short and fixed (the
frozen-v1 style; both the jargon-free and the latest-turn-scoped rewrites lost). Question
strings and the 0.8 gate live as named constants in `for_experts.py` — the audit surface —
so tuning is a reviewed constant edit, never a reworded string at a call site.

**Implementation stubs (drafted and rolled back 2026-07-17 — restore these):**
```python
# prompt_engineer.py — import requests; module constants beside FAMILY_TIERS
_TYPESAFE_ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
_TYPESAFE_MODEL = 'speed_latest'

def typesafe(self, document:dict, questions:dict) -> dict:
    """One TypeSafe System-1 call — typed questions evaluated against a document, typed
    answers back. Returns the `answers` dict; raises on a missing key or a failed
    request — the caller owns the fallback."""
    key = os.getenv('TYPESAFE_API_KEY')
    if not key:
        raise RuntimeError('TYPESAFE_API_KEY not set. Add it to .env or environment.')
    payload = {'document': document, 'model': _TYPESAFE_MODEL, 'questions': questions}
    headers = {'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'}
    resp = requests.post(_TYPESAFE_ENDPOINT, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()['answers']
```
```python
# for_experts.py — the audit surface (replaces ROLE_INTENT / INTENT_INSTRUCTIONS /
# INTENT_RULES / build_intent_prompt; INTENT_EXAMPLES retires with the prompt — the
# taxonomy content maps into the criteria rubrics)
INTENT_CRITERIA = {  # the five domain rubrics, from the taxonomy bullets
    'Research': 'Find posts and notes, inspect metrics and metadata, summarize drafts, '
                'compare posts.',
    'Draft': 'Brainstorm ideas, generate outlines, compose prose from an outline, refine '
              'sections.',
    'Revise': 'Restructure and rework drafts, edit sentences and phrasing, audit voice '
              'and consistency, propose alternatives for placeholder gaps.',
    'Publish': 'Publish to the blog, cross-post to channels, schedule, add citations.',
    'Converse': 'Greetings, open-ended questions about writing, general discussion, '
                'setting a preference.',
}
INTENT_QUESTION = 'Which intent is the user requesting?'
NOUL_THRESHOLD = 0.8
PLAN_NOUL = {'type': 'noul', 'instructions': 'Is this a multi-step plan?', 'criteria': {
    'true': 'The user is asking for two or more distinct operations in one message — no '
            'single action covers the whole request on its own',
    'false': 'A single operation covers the whole request'}}
CLARIFY_NOUL = {'type': 'noul',
                'instructions': 'Is there uncertainty that we need to clarify?',
                'criteria': {
    'true': 'The request is too vague or underspecified to act on without asking the '
            'user a question first',
    'false': 'The request is clear enough to act on'}}
```
```python
# dialogue_state.classify_intent — the body swap (the Continue derivation and the
# mapped store are T16's, unchanged); _intent_schema deletes with the LLM call
criteria = dict(INTENT_CRITERIA)
if working:
    criteria['Continue'] = (f'The turn advances `{working}`, the task already in '
                            f'progress — an answer, a detail, an approval, or "keep going".')
document = {'history': context.compile_history(), 'utterance': user_text}
answers = engineer.typesafe(document, {
    'intent': {'type': 'choice', 'instructions': INTENT_QUESTION, 'criteria': criteria},
    'has_plan': PLAN_NOUL, 'needs_clarify': CLARIFY_NOUL})
plan, clarify = answers['has_plan']['noul'], answers['needs_clarify']['noul']
if plan >= NOUL_THRESHOLD or clarify >= NOUL_THRESHOLD:
    intent = 'Plan' if plan >= clarify else 'Clarify'
else:
    intent = answers['intent']['choice']
```
**Tests:** the fixtures already stub `classify_intent`, so no live calls;
`test_classify_intent_still_callable` retargets its mock to `engineer.typesafe` returning
the three answers; the schema lint drops `_intent_schema`. **Verify:** suites green; one
live smoke turn confirming NLU 1 latency near the exp3 ~140 ms; the eval intent-accuracy
dimension after. Changes: `prompt_engineer.py`, `for_experts.py`, `dialogue_state.py`,
`nlu_unit_tests.py`.

---

## Unresolved Issues

None open. The four 2026-07-17 review items were answered by Derek and folded back the same
day (implemented in code where they touched landed behavior):

1. Run-the-top loop → after a completion the module pops every Completed/Invalid flow in a
   row and passes `popped` plus the surfaced `next_flow` to the agent, which judges what runs
   next — usually `manage_flows` op='update' status='Active', else Invalid + pop, else a new
   stackon. The `ran` set is dropped from code and spec: re-running a flow within a turn is
   legal, and the loop stops when the top stops changing (3.4.6, T10).
2. All-hook scratchpad reads → the hook loop matches entry metadata (origin, turn_number,
   used_count) WITHOUT calling `read()` — reading is consuming, so only a matched entry is
   read (Canonical Turn touch point 2).
3. Message-list ownership → the Assistant is a thin wrapper: it hands the raw turn to the
   Context Coordinator's `append_user_message(text, dax, payload)`, and the coordinator —
   MEM's component — builds the message, [click]/[action] decoration included; the Assistant
   appends the agent's reply the same way after `execute` returns. PEX appends only its
   working transcript — tool blocks, tool results, nudges, and the hook-5 notes (take_turn,
   context_coordinator.py, execute, _run_loop, _execute_click, _final_emit).
4. Continue staleness after a completion → dismissed; the concept is deleted.

Resolved — all six cleared 2026-07-16 and folded back into the doc:

1. Queued-step vs displaced-flow discriminator → none needed; a surfaced plan step runs under
   `state.has_plan`, anything else unclear returns to the PEX agent, which makes the stack
   call itself (3.4.6, T10).
2. `amend_entry` relaxation → not needed; `SessionScratchpad.read()` flips `is_newborn` on
   every entry it returns, whoever the caller is — PEX only ever calls `append_entry`/`read`
   (3.4.6, T10).
3. `_repair_slots` input shape (dict vs one-item list) → confirm at implementation (T8).
4. Line counts for cite → computed code-side by splitting the section text; no new tool —
   reuse an existing helper if one exists, flag if none (3.4.8, T14).
5. Hook-wait timeout → fail the turn loudly; the raise lands in `take_turn`'s safety net
   (Threaded Turn, 3.4.6, 3.4.7, T10).
6. revise_slots.py range case → add one user-supplied-range exemplar (3.4.8, T14).


## Todo List

Each task names its theme and the files it changes. Checked = landed (T1-T6 on 2026-07-15,
T7-T20 on 2026-07-17; unit suites 230 green after — two tests left with the features T18/T19
deleted; unit tests are low-priority right now; traces and evals judge the real behavior
later).

- [x] **T1 — DialogueState substrate fix (3.4.3).** `flow_name()` length bug; belief format
  `{name, dax, confidence, rationale?}` written by `_write_belief` and every literal
  `pred_flows` site; dead `config['entity_parts']` line removed; `turn_count` (and the
  `pred_flow`/`confidence` summary fields) initialized in `reset()`; `load()` reads `convo_id`.
  Changes: `dialogue_state.py`, `nlu.py`.
- [x] **T2 — retire `pred_slots` (3.4.3).** Predictions live on the flow itself: NLU fills the
  flow it stacks; `_execute_click` activates the react-stacked flow instead of re-filling from
  belief; `_apply_belief_slots` deleted. Changes: `nlu.py`, `pex.py`, `trace_writer.py`.
- [x] **T3 — remove the `write_state` call sites (3.4.3).** `_manage_flows` calls the FlowStack
  ops directly (plus the status-capitalize fix and an unknown-op raise); `complete_flow` sets
  `flow.status = 'Completed'` directly; per-op state.json writes dropped (MEM saves at turn
  end); the policies' `state_file` component removed. Changes: `pex.py`, `policies/base.py`.
- [x] **T4 — MEM `start()`/`finish()` (3.4.4).** `_record_checkpoint` deleted from PEX;
  `start()` = System checkpoint turn + is_newborn reset + consumed-choices clear + turn count;
  `finish()` = turn-end shape check + state.json save; `store_turn` = agent turn → start →
  compaction → finish. Changes: `mem.py`, `pex.py`.
- [x] **T5 — single flow stack (3.4.3).** No `flow_stack` copy on DialogueState:
  `pex.flow_stack` is the one stack; PEX attaches `to_list()` to the tool document at read time
  (`read_state` / `_manage_flows` / `_top_policy`); NLU/MEM mirror assignments removed.
  Changes: `dialogue_state.py`, `pex.py`, `nlu.py`, `mem.py`.
- [x] **T6 — announcement rationale (3.4.3).** `_tally_votes` keeps one majority voter's
  reasoning in `pred_flows[0]['rationale']`; the announcement entry carries it as a `rationale`
  line. Changes: `nlu.py`.
- [x] **T7 — the threaded turn (Threaded Turn).** `take_turn` runs NLU on a worker thread, PEX
  on main; `world.nlu_done = threading.Event()` (with the revisit-TODO listing the polling
  alternative); crash stored and re-raised at the join. Changes: `assistant.py`, `world.py`.
- [x] **T8 — the NLU merge (3.4.5).** `think` = check → detect_flows → fill_slots → validate,
  called directly by the Assistant (`understand` retires as the module entry — the name
  survives only on PEX's tool); `check` clears prior ambiguity (round 3.4: always) and picks
  the intent-keyed detection-prompt snippet (Continue renders a very different template than
  Plan or Clarify); a Plan detection stackons every step in reverse execution order; merged
  think absorbs `_fill_active_flow` + `_stack_detected_flow`; `fill_slots` moves onto the
  DialogueState (beside `classify_intent`/`detect_flows`), drops the `incomplete` param (gate
  on `ambiguity_handler.is_present`), and treats the entity slot like any other slot; validate
  gains `_repair_slots` + `_valid_snip` (rules-based slot repair — there is no 'entity repair'
  concept) — confirm the established-vs-fresh value shape there (one entity dict vs a one-item
  list from `SourceSlot.json_schema`). Changes: `dialogue_state.py`, `nlu.py`, `assistant.py`.
- [x] **T9 — validate writes every entry (3.4.5).** Aligned, announcement, click, and plan
  entries (click carries `gold_dax`; the plan entry is summary-only — it lists the stacked
  steps and carries no `new_flow` key, so hooks 3/5 skip it); announcements carry
  `is_newborn: true` as the consumed marker plus the rationale. Changes: `nlu.py`.
- [x] **T10 — the PEX hook reads (3.4.6).** `prepare()` opens `execute` as hook point 1 —
  on a Plan/Clarify classification it blocks on `nlu_done` before the loop; `_top_policy`
  run-the-top loop (revised under Unresolved 1a/1b, 2026-07-17: no `ran` ledger, a
  completion always returns to the agent with `popped` + `next_flow`, the loop stops when
  the top stops changing); `SessionScratchpad.read()` flips `is_newborn` on the entries it returns and
  `_read_nlu_entry` filters on it — PEX only ever calls `append_entry`/`read`; hook 5 on
  `_run_loop`'s text-only branch; every hook wait raises on expiry (fail the turn loudly);
  then delete `inject_belief_state` + `_injected`. Changes: `pex.py`, `session_scratchpad.py`.
- [x] **T11 — the hint removal (3.4.5).** Nothing belief-related is passed as a parameter:
  take_turn computes no hint, `check()` takes no arguments, `detect_flows` reads
  `self.pred_intent` directly (a Continue reading — pred_intent matching the belief flow's
  intent, since 'Continue' is never stored — names the flow via `flow_name()`; the narrowing
  and the seeded vote stay dormant until T16 writes pred_intent); the
  tie-break writes `state.pred_intent` instead of passing an intent; validate's `prev` is a
  stack fact think reads at its stackon decision point, kept only for the aligned-vs-
  announcement label. Changes: `assistant.py`, `nlu.py`, `dialogue_state.py`.
- [x] **T12 — verify + pop (3.4.6).** `_verify_artifact` → `verify`; PEX calls
  `self.flow_stack.pop()` after the completion entry in `activate_flow`; delete base.py's
  `run_hook`/`HookDecision`/`HOOK_POINTS`. Changes: `pex.py`, `policies/base.py`.
- [x] **T13 — contemplate via the Assistant (3.4.7).** `contemplate` stays a main NLU method
  (react / think / contemplate); `_understand_user` honors `op='contemplate'` by queuing a
  scratchpad request and ending the pass — the Assistant reads it after `execute` returns,
  calls `nlu.contemplate()`, and re-enters PEX (modules are never attached to the World); tool
  schema enum gains `'contemplate'`; fold `_check_routing`/`_get_contemplate_candidates`/
  `_contemplate_prompt` into it and drop its LLM slot fill. Changes: `nlu.py`, `pex.py`,
  `assistant.py`.
- [x] **T14 — cite (3.4.8).** Align `TargetSlot.check_if_filled` with SourceSlot's entity-part
  rule; convert descriptive-snip exemplars to ids — sentence/line counts computed code-side by
  splitting the section text (reuse an existing helper if one exists; flag to Derek if none);
  add one user-supplied-range exemplar (S3's `[2, 5]` shape) to revise_slots.py. The snip-id
  doctrine covers the LLM path only: click payloads carry descriptive text snips (the
  frontend's trusted internal contract, e.g. 'matrix mult'), which is why `_repair_slots`
  polices `op == 'think'` and the exemplar conversion touches no react/payload path. Changes:
  `slots.py`, `draft_slots.py`, `revise_slots.py`, cite's tool menu.
- [x] **T15 — the orchestrator prompt rewrite (3.4.6, 3.4.8).** for_orchestrator.py restated
  around the one job (each round: one stack action, or the terminal response). The `pred_slots`
  references rewritten to the flow's slots in the document; the "Belief notes" paragraph
  replaced by the announcement model (the stack may change mid-turn; the scratchpad entry says
  why; act on the stack as it stands); the S1-first-move paragraph removed (T16 owns
  classification); "Ask vs. proceed" shrinks to "a stalled flow returns a question — relay it";
  the read-only tools re-justified as full read power (drop the one-lookup entity rule);
  Converse routed through the chat flow like any other intent (run the policy, pass its
  proposed response along, lightly de-AI it at most); the contemplate paragraph rewritten to
  the queued re-route (end the pass — the re-detected flow runs on the next pass); the PEX 2
  gate and PEX 5 resolution text. Changes: `for_orchestrator.py`.
- [x] **T16 — `classify_intent` (3.4.6).** The fast TypeSafe S1 intent model, called
  synchronously by the Assistant before either lane runs (`nlu.dialogue_state.classify_intent`
  per the Threaded Turn sketch — the method sits on the DialogueState component, matching
  contemplate's pattern); writes `state.pred_intent` for both lanes to read. Base it on the
  existing `_classify_intent` tie-break in nlu.py (promote, don't duplicate — the
  low-confidence re-detect in `think` then reuses the same call). Details settled 2026-07-17:
  (a) with an Active top the S1 call offers Continue, but 'Continue' is never stored — the
  classifier writes the Active flow's intent (audit + Continue → 'Revise'); the tie-break call
  keeps the six-domain-intent schema. (b) On a clear domain intent with no Active top,
  `execute` code stackons the intent's basic flow via `intent2flow` (utils/helper.py, landed) —
  with an Active top of the same intent it runs the top, and a different intent goes to the
  PEX 2 gate. (c) `state.has_plan` resets when the plan's stacked steps have all left the
  stack — clear it at the pop site when no live flow remains. (d) Ordering: round 3.5's
  `plan_flows.py`/`clarify_flows.py` registry entries must land before or with this task —
  `get_prompt('Plan'/'Clarify')` raises KeyError the moment pred_intent holds those values.
  Landed 2026-07-17 except (d): the classifier is live, so a Plan/Clarify classification
  crashes the think lane until round 3.5's prompts land (accepted — "we will deal with it soon
  in round 3.5"); a failed classify stores '' so detection falls back to the full ontology.
  The model itself is interim — an LLM call, not TypeSafe; the swap is T17.
  Changes: `dialogue_state.py`, `nlu.py`, `assistant.py`, `pex.py`, `for_experts.py`.
- [x] **T17 — `classify_intent` moves onto TypeSafe (design settled 2026-07-17).** T16 landed
  NLU 1 as an interim LLM call; this task swaps the model. TypeSafe (`speed_latest`,
  `POST https://api.typesafe.ai/v1/systemone`, key `TYPESAFE_API_KEY`; skill doc at
  `handling_ambiguity/typesafe/SKILL.md`) is the non-LLM System-1 decision model — typed
  questions over a document, typed answers back. Landed 2026-07-17: `engineer.typesafe` +
  the audit-surface constants in for_experts.py + the classify_intent body swap; the LLM
  intent prompt (builder, role, instructions, exemplars, schema, task suffix) is deleted.
- [x] **T18 — `manage_flows` drops slot writes (3.4.6).** Remove `fields.slots` handling and
  the unknown-slot check from `_manage_flows`; the tool description loses its slot language
  (prompt side in T15). Continue is a pure status write — NLU has already filled the slots.
  Changes: `pex.py`.
- [x] **T19 — `recover_from_ambiguity` leaves the orchestrator toolset (3.4.6).** Delete
  `_recover_ambiguity` and its toolset/definition entries; recovery is NLU's or the
  sub-agents' call (re-homing out of scope). `ask_clarification_question` stays — it is reply
  composition. Changes: `pex.py`.
- [x] **T20 — module surface renames (Canonical Turn table).** MEM: `store_turn` → `recap`
  (start → compaction/promote → finish, unchanged inside; `remember(op=x)` reserved as MEM's
  tool-call name, with recall/recap/retrieve as the L1/L2/L3 methods); the Assistant wrap-up
  calls `recap()`. Changes: `mem.py`, `assistant.py`.
- [x] **T21 — verification pass (runs last).** The checks in Other ·
  Verification below. Offline half done 2026-07-17: imports clean; suites green; no
  `inject_belief_state`/`_injected`/`_apply_belief_slots`/`_record_checkpoint` references and
  no `pred_slots` belief field left in backend; banned-word sweep clean.
  Expanded scope run 2026-07-17 with two sub-agents (Derek): one verified every checkable
  claim in the Major Themes + Canonical Turn against code; one statically traced S1-S11
  through the turn path. Verdict: 3.4.3/3.4.5/3.4.7/3.4.8 clean; S2/S4/S6/S10/S11 hold;
  S7/S8 hold modulo the accepted round 3.5 gaps. **Fixes landed (suites 230 green after):**
  (1) think's same-flow check accepts an in-flight (Active or Pending) top — the Active-only
  check wrote a false announcement on every fresh turn while the code-stacked basic flow
  waited as Pending. Superseded rulings the same day: `stackon` now sets the new flow Active
  by default (active=False stacks a Pending plan step), and `pop` is a while loop from the
  top of the stack down to the first Pending/Active flow — a buried terminal flow waits for
  the flows above it to resolve (nlu.py, stack.py); (2) `complete_flow` no longer
  requires being top of stack — NLU stacking mid-run made every such completion crash into a
  corrective server_error (policies/base.py); (3) the missing `chl` preservation rule landed
  in `_repair_slots` (the one 3.4.2 contract line with no code counterpart); (4) the
  tie-break re-classify only re-detects on a domain intent — a mid-think noul writing
  Plan/Clarify no longer widens the accepted detection crash to low-confidence split turns.
  Spec prose reconciled to the rulings in seven places (diagram, touch point 2, 3.4.1's
  overwrite clause, S5/S9 rows, the 3.4.5 sketches). **Deferred to future rounds:** the
  back-to-PEX-2 loop and validate's mid-plan announcement swallowing (recorded in round
  3.5's spec — they bite only once plans stack steps); a staleness rule for an announcement
  that reaches hook 5 after its flow already ran (S8 — one extra agent round with a stale
  note today); the non-consuming scratchpad scan from Unresolved 2 (`_read_nlu_entry` and
  `review_scratchpad` still consume entries their filters reject — needs the entry-level
  read surface); and S9's leftover basic flow after a different-intent re-route — the
  code-stacked flow surfaces as `next_flow` for the agent to decline, and telling it apart
  from real prior work (S6's refine) needs a rule, `is_newborn` being the plausible key.
  The live replay/eval checks (B02.C15, the round-3.3 traces) remain available as a
  follow-up run.


---

## Other

### Out of Scope

- Continue-intent coordination and voter composition.
- Same-type entity dedupe, which remains a FlowStack/PEX task in Round 2.13.
- Policy-side snippet discovery after NLU correctly leaves a descriptive `snip` empty.
- Dealing with retries with contemplate when the sub-agent hits an issue
- Handling routing and recovery due to ambiguity. This requires working much more closely with MEM.

### Verification

Flow handoff (3.4.1):

- A same-flow detection fills the existing flow; the stack gains nothing.
- A same-intent different-flow detection is stacked by NLU and resolved in the same turn — the
  agent runs it or pops it; the entry surfaces at hook point 3, or 5 when the sub-agent called
  no tools.
- A different-intent detection runs in the same turn — the top of the stack is what executes;
  the displaced policy stops cleanly at its hook point.
- An acknowledgment turn stacks `chat`, which runs (the streamed reply is its execution) and
  pops; the flow beneath reactivates.
- `active=false` plan steps still run on later turns, empty `turn_ids` and all.
- Replay `B02.C15`: no Pending accumulation and no turn-end invariant warnings; also replay the
  round-3.3 active-answer trace cases.
- Read-only tool audit (3.4.6): count per-tool orchestrator calls across the trace runs; a
  domain tool with zero useful calls leaves the toolset.

Grounding slot-fill (3.4.2):

- `{post=A, sec=intro}` + valid `[2, 5]` → `{post=A, sec=intro, snip=[2, 5]}`.
- `{post=A, sec=intro}` + "the rambling paragraph" → same post/sec and empty snip.
- Proposed post B or another section does not silently replace established grounding.
- The whole entity reaches the live flow's slots and the policy input unchanged.

Suites:

- The two `validate` outcomes (aligned fill; stacked divergence resolved by PEX) across
  same-intent, different-intent, and Converse detections are judged from traces and evals —
  no new unit tests (the moratorium stands; update or delete existing ones only).
- `run_suite.py --tests` remains green.
