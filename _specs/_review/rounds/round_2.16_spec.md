# Round 2.16 — The Two-Loop PEX: orchestrate() / execute() Split

Maps to **Master Plan · Round 2 (PEX correctness)**. Design spec — evidence is the 2026-07-19
design discussion in [pex.md § One turn through PEX](../../modules/pex.md); its pseudo-code is
copied into 2.16.3 below (with the corrections flagged under Conflicts) so a sub-agent can build
this round from this file alone. Today `PEX.execute()` (pex.py:277) is one method holding the
whole agent loop, `assistant.py` already calls methods that don't exist (`keep_going()`,
`orchestrate()`, `final_response`, `recently_finished` — every live text turn currently dies in
the take_turn safety net), and the flow-running path is split across `_top_policy` +
`activate_flow`. This round lands the two-loop shape: the **PEX Agent** (one round per
`orchestrate()` call, while-loop at the Assistant level) and the **policy sub-agent** (run by
`execute()`, called only from inside `manage_flows`).

Rulings recorded up front (2026-07-19):

- **Option (b) chosen for the fast path**: the agent explicitly chooses to run the stacked flow —
  no code-side policy run before the first agent round, no synthesized kind-4 turns. The cost is
  a two-round floor per flow turn (choose round + wording round around the sub-agent run).
- **prepare() hands round 1 the prediction via a kind-5 system note.** PEX reads
  `state.pred_intent` / `state.pred_flows` directly; the note is how the prediction reaches the message stream (the
  system prompt is frozen). Golden dax turns get mandatory wording — "you MUST run X" — because a
  click is the user naming the flow, not a prediction.
- **The reply is PEX's return value.** Not a `final_response` attribute, not a field on the
  TaskArtifact: `orchestrate()` returns `''` on mid-turn rounds and the utterance on the terminal
  round; `take_turn` passes it to `mem.recap`.
- **`state.keep_going` is the one loop flag**, redefined as "this turn still has PEX work":
  `prepare()` sets True, the terminal emit sets False. No `pex.keep_going`. The old "chain the
  next Plan step" meaning becomes prompt guidance, not this flag.
- **`recently_finished` replaces `completed_this_turn`**: every flow popped this turn, Completed
  OR Invalid (hence not "completed_flows"). MEM stores only the Completed members; the agent
  learns of Invalid pops from the `popped` list in manage_flows results — no new channel.
- **`verify()` keeps one call site**, immediately after `call_policy(flow)` inside `execute()` —
  the last step of every sub-agent run without pasting it into ~16 policy methods.
- **Call verbs**: `call_tool()`, `call_policy()`, `call_mcp()` — tools, policies, and MCP servers
  are all *called*. `call_mcp` is designed-not-built (no MCP server is wired yet).
- **Standardization**: every predictor — golden dax, TypeSafe, NLU ensemble — writes the same
  belief: `state.pred_intent` and `state.pred_flows`, mapped to flows at prediction time.
  `prepare()` looks nothing up and stacks nothing; the agent stays the main driver — every
  sub-agent run is triggered through `manage_flows`.

---

## Major Themes

### 2.16.1 — Method mapping (old → new)

| Today | Becomes | Notes |
|---|---|---|
| `PEX.execute(system_prompt)` loop (pex.py:277-349) | `orchestrate(system_prompt)` — ONE round | while-loop moves to `take_turn` |
| loop locals `round_idx/nudged/errors/last_call/finished` (pex.py:291-295) | `self.rounds/self.nudged/self.errors/self.last_call/self.finished` | reset in `prepare()` — the loop boundary crosses calls now |
| the two lines that stack the predicted flow (pex.py:283-285) | deleted | `prepare()` stacks nothing — the agent stacks via `manage_flows` |
| `_top_policy` (pex.py:601-647) | `execute(start=None)` | same body; called from `_manage_flows` only |
| `activate_flow` (pex.py:671-741) | inlined as `execute()`'s per-flow body | ground → security → `call_policy` → `verify` → completion |
| `self._policies[flow.intent]` dispatch (pex.py:692-693) | `call_policy(flow)` | lookup + run + `pop_completion` |
| `_tool` (pex.py:426-463) | `call_tool` | `_guarded_call` (pex.py:381) keeps the orchestrator guards and calls it |
| `completed_this_turn` (pex.py:147) | `recently_finished` | appended at every pop site |
| `_execute_click` stub (pex.py:364-367) | deleted | clicks ride the standard path with the MUST note |

The round-budget reset (pex.py:343-345) keeps its meaning — a **completion** resets the budget —
so it counts the Completed members of `recently_finished`, not the list length.

### 2.16.2 — The two system notes (exact strings)

`prepare()` appends one kind-5 turn; the flow name comes straight from `state.pred_flows` (the
intent→flow mapping happened at prediction time — `prepare()` looks nothing up and stacks
nothing). The branch is the last user turn's `turn_type` (payload contract: dax present ⇒
action turn). Plan and Clarify turns already waited on NLU at hook point ① by note time, so the
settled belief fills the same [typesafe] template (C3). Converse turns get the same template —
whether to stack `chat` or reply directly is the agent's choice, steered by the system prompt,
never by code (C4).

- action turn (react already stacked the flow): `[click] The user selected '{pred_flow}'
  directly. You MUST run it as your next step with manage_flows (update status='Active').`
- utterance turn (nothing stacked yet): `[typesafe] intent={pred_intent} — the predicted flow
  is '{pred_flow}'. Stack and run it with manage_flows (op='stackon'), pick a different flow,
  or reply directly.`

### 2.16.3 — Binding pseudo-code (self-contained)

Copied from pex.md; every C-item below is ruled and pex.md is synced — the two files agree.

**The Assistant drives the turn** (assistant.py `take_turn`):

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
        reply = pex.orchestrate(system_prompt)     # one PEX-Agent round; '' until the terminal round
    mem.recap(reply, pex.last_prompt_tokens, pex.recently_finished)   # records the kind-3 reply;
                                                   #   MEM stores Completed flows only (T7)
```

**prepare() — PEX's first step (hook point ①)**:

```python
def prepare():
    recently_finished, reads = [], 0               # every flow popped this turn — Completed or Invalid
    turn_start = context.num_utterances
    state.keep_going, rounds = True, 0             # also reset: nudged, errors, last_call, finished
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

**orchestrate() — one PEX-Agent round** (the while-loop lives in take_turn):

```python
def orchestrate(system_prompt):                    # returns the reply text, or '' mid-turn
    rounds += 1
    response = engineer(system_prompt, context.compile_messages(), family='claude',
                        tier='high', tools=catalog, max_tokens=4096)
    track_usage(response)                          # last_prompt_tokens — MEM's compaction read
    text, tool_uses = split(response)

    if not tool_uses:
        if text:
            wait(nlu_done, timeout=30)             # hook point 5 — post-LLM, no tools ran
            if unconsumed_nlu_announcement():      # _read_nlu_entry(), unchanged
                record text as a kind-4 turn; append the note as a kind-5 system turn
                return ''                          # PEX 5 — one more round to decide
            state.keep_going = False               # terminal round — the turn is worded
            return text                            # the reply is PEX's final result
        if nudged:                                 # thinking-only twice → forced wrap-up (T14)
            state.keep_going = False
            return _final_emit()
        nudged = True; append _NUDGE_MESSAGE as a kind-5 system turn
        return ''

    results = [guarded call_tool(tu) for tu in tool_uses]   # _guarded_call keeps the orchestrator
                                                   # guards: unknown name, duplicate, read cap
    # a manage_flows op that surfaces runnable work calls execute() inline; the policy
    # result IS the tool result — no separate recording by execute()
    context.add_turn('agent', {text, tool_uses, results}, 'action')  # one kind-4 turn per round
    if a flow completed this round: rounds = 0     # every plan step starts a fresh budget
    if rounds >= max_rounds or errors >= max_corrective:
        state.keep_going = False
        return _final_emit()                       # one no-tools wrap-up call — the reply
    return ''                                      # mid-turn round — no reply yet
```

**execute() — run policy sub-agents until the stack settles.** Called ONLY from inside a
`manage_flows` call, whenever an op surfaces runnable work — stackon (`active` ≠ false),
fallback, a pop that promotes a Pending flow, or an `update` writing `status='Active'`
(the run branch, pex.py:591-598):

```python
def execute(start=None):
    curr_flow = start or flow_stack.get_flow()
    while curr_flow and curr_flow.status in ('Pending', 'Active'):
        curr_flow.status = 'Active'
        state.ground_flow(curr_flow)               # fills only EMPTY entity slots; idempotent
        if security_check(curr_flow):              # lethal-trifecta gate → confirmation block
            return approval_result                 # no sub-agent run
        artifact = call_policy(curr_flow)          # ← the policy sub-agent runs inside
        check = verify(artifact, curr_flow)        # last step — hook point 6, single call site
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

**call_policy() — the code wrapper around one sub-agent run**:

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

**call_tool() / call_mcp() — the uniform call surface** (rename of `_tool`, pex.py:426):

```python
def call_tool(name, args):                         # every tool call, both loops, one routing site
    if catalog[name].served_by_mcp:
        return call_mcp(catalog[name].server, name, args)   # spec-only this round
    try:
        return bound_method(**args)                # services return {_success, ...}
    except TimeoutError:
        raise                                      # hook-wait expiry fails the turn loudly
    except Exception as ecp:
        return corrective('server_error', ecp)     # corrective errors, never raises

def call_mcp(server, name, args):
    return mcp_clients[server].call(name, args)    # same {_success, ...} contract as call_tool
```

**verify() — the last step of every sub-agent run (hook point ⑥)** — body unchanged from
pex.py:225-248:

```python
def verify(artifact, flow):
    if ambiguity.is_present:            return passed             # the question IS the outcome
    if 'violation' in artifact.data:    return failed(error_path)  # already classified; no retry
    if artifact_has_no_data:            return failed('no data')
    if artifact.thoughts == last_user_utt: return failed('echo')
    if flow.name() in content_validation: run_llm_quality_check()  # stubbed today
    return passed
```

### 2.16.4 — Contracts the sub-agent builds against

- Every tool / policy / MCP call returns `{_success: bool, ...}`; failures are
  `{_success: False, _error, _message}` corrective results, never exceptions — except
  `TimeoutError` from a hook wait, which fails the whole turn loudly (take_turn's safety net).
- The orchestrator-side guards stay in `_guarded_call` (pex.py:381-413): unknown tool name,
  identical consecutive SUCCESSFUL call, read-only cap (`max_reads`), plus the live-stack key on
  manage_flows dedupe. They wrap `call_tool`; sub-agents receive plain `call_tool` as `tools`.
- One kind-4 agent action turn per orchestrator round — `{text, tool_uses, tool_results}`,
  written by `orchestrate()` only. `execute()` writes no turns; its output travels as the
  manage_flows tool result.
- `_read_nlu_entry` (pex.py:649-669) is the hook ③/⑤ read: newest unconsumed `origin='nlu'`
  entry with `turn_number >= _turn_start`; reading consumes (`is_newborn` flips).
- `state.keep_going` writers: `prepare()` (True) and `orchestrate()`'s three terminal paths
  (False). No sweep — C7 leaves any theoretical belief-side writer alone until seen in practice.
- MEM: `recap(reply, last_prompt_tokens, recently_finished)`; it stores and checkpoints only the
  `status == 'Completed'` members.
- One round primitive: every model round — the PEX agent's and every sub-agent's — is one
  `engineer(...)` call; `flow_execute` loops that same primitive internally (T13). There is
  exactly one way a model round happens, with two granularities on top.

## Conflicts — all ruled 2026-07-19

- **C1 — confirmed.** The "record the run as an agent action turn" line in execute() was a
  pre-(b) leftover; deleted from pex.md and absent in 2.16.3.
- **C2 — not a bug.** `nlu.react()` and `nlu.think()` both write `state.pred_intent` and
  `state.pred_flows` (react with *very* high confidence), so the prediction is fresh on every
  turn. `prepare()` neither looks up nor stacks anything — it reads `state.pred_flows` for the
  note, and the old stack lines (pex.py:283-285) are deleted. A click routes through
  `nlu.react()` and never `nlu.classify_intent()`, so a sibling basic flow (e.g. `release`
  under a `schedule` click) never enters the picture.
- **C3 — non-issue.** Plan and Clarify wait on NLU at hook point ① inside `prepare()`, so the
  state is settled before the note renders and the standard [typesafe] template applies.
  Vocabulary: the variables are `curr_flow` / `prev_flow` — never `top`.
- **C4 — no carve-out in code.** Converse is not special-cased anywhere. The agent chooses:
  reply directly on simple requests, or stack and run `chat` when the reply needs the FAQs —
  steered by a guidance line in the orchestrator system prompt.
- **C5 — already fixed in code.** `contemplation_requested` keeps only `is_newborn` entries, so
  each re-route request fires exactly once.
- **C6 — standard stackon.** The flow `nlu.react` stacks on a click lands Active (stackon's
  default). The [click] note's `update status='Active'` is then a same-value write, which still
  fires the run branch — pex.py:591-594 checks the written value, not a change. On utterance
  turns the agent's own `stackon` stacks and runs in one op.
- **C7 — ignored for now.** No keep_going sweep. `prepare()` and `orchestrate()`'s terminal
  paths are the writers; a belief-side writer gets dealt with if it ever shows up in practice.

## Todo list

- [x] **T1 — take_turn becomes the L1 loop** (assistant.py:59-69). Final shape:
  `pex.prepare()` → `while self.world.state.keep_going:` [contemplate check →
  `reply = self.pex.orchestrate(self.system_prompt)`] → `self.mem.recap(reply, ...)`. The
  contemplate branch calls `nlu.contemplate()` only — the agent runs the re-stacked flow on its
  next round (no `pex.execute()` from L1). Delete the stale `self.keep_going()` /
  `pex.final_response` references; `contemplation_requested` (assistant.py:74) stays — its
  `is_newborn` filter is already in (C5).
- [x] **T2 — prepare() grows** (pex.py:351-362): reset `recently_finished`, `_reads`,
  `_turn_start`, the five loop attributes from 2.16.1, and `state.keep_going = True`; keep the
  Plan/Clarify wait; delete the old stack-the-predicted-flow lines (pex.py:283-285) — prepare()
  only reads `state.pred_flows[0]` for the note; append the 2.16.2 system note (two variants).
  Add the Converse guidance line (reply directly vs stack `chat` for FAQs) to the orchestrator
  system prompt (for_orchestrator.py). Extract the two shared helpers the round's functions all
  use: `wait_for_nlu(hook)` for the wait+raise pattern (four copies today — prepare, execute,
  orchestrate, `_understand_user`), and `corrective(error, message)` for the hand-built
  `{_success: False, _error, _message}` dict (~8 copies).
- [x] **T3 — orchestrate(system_prompt)** — extract one round from the loop body
  (pex.py:296-347). The round's model call goes through the engineer's public call surface —
  `engineer(system_prompt, messages, family='claude', tier='high', tools=..., max_tokens=4096)`
  — not the private `_call_claude` with a raw model_id; the tier→model mapping lives in the
  engineer's config. Returns `''` mid-turn; on the terminal no-tool text sets
  `state.keep_going = False` and returns the text; the nudge path's second miss and the
  round/corrective caps also flip the flag and return `_FALLBACK_MESSAGE` / `_final_emit()`.
  The hook-5 `_read_nlu_entry` read (pex.py:307-314) is unchanged.
- [x] **T4 — execute(start=None)** — rename `_top_policy`, inline `activate_flow` as its per-flow
  body, and extract `call_policy(flow)` (policy lookup, run, `pop_completion`). `verify` stays on
  the line after `call_policy`. Callers: the run branch of `_manage_flows` (pex.py:591-598).
- [x] **T5 — call_tool rename** (`_tool` → `call_tool`); update `_guarded_call` (pex.py:410) and
  the policy-facing pass-through (pex.py:693). Policies keep receiving the callable as their
  `tools` param. `call_mcp` is spec-only this round.
- [x] **T6 — recently_finished**: rename + append at every pop site — the completion pop
  (pex.py:720-729, including the plan-surfacing pop) and `_manage_flows` op='pop' (pex.py:581).
  Fix the budget-reset counter per 2.16.1.
- [x] **T7 — MEM skips Invalid**: `mem.recap` filters `status == 'Completed'` from
  `recently_finished` for the store and the turn_wrap checkpoint's `completed` list; Invalid
  members are dropped there (the agent already saw them via `popped`).
- [x] **T8 — keep_going writers**: implement the two writers — `prepare()` sets True,
  `orchestrate()`'s three terminal paths set False. No repo-wide sweep (C7): leave any existing
  belief-side writer alone until it causes a problem in practice.
- [x] **T9 — delete dead surface**: `_execute_click`, the `intent2flow` import if pex.py no
  longer uses it, plus any locals/helpers orphaned by the split. Net diff for pex.py should be near zero or negative outside the note strings.
- [x] **T10 — tests**: update `pex_unit_tests.py` call sites to the new names/shape (moratorium:
  update or delete only, never add). Run the three files from the Hugo dir; all green.
- [x] **T11 — docs sync**: helper_ref.md's PEX section to the new surface;
  `architecture.md` PEX lines if they name the old loop; pex.md was updated as this round's
  pre-work (pseudo-code section + Click bullet + who-waits paragraph).
- [x] **T12 — verification**: commit the coding draft first; one live probe turn (find →
  grounded reply) confirming round 1 obeys each note variant; replay the gate canaries B03.C14
  and B01.C13 — completion no worse than 0.5 / 1.0; restore `database/content` after the runs.
- [x] **T13 — one round primitive in the engineer**: `PromptEngineer.__call__` becomes the
  single place a model round happens — system prompt + message list + family/tier + tools → one
  API response (the T3 signature). `flow_execute` is rewritten to loop over `__call__` (thread
  tool results, collect the tool_log, handle the terminal emit) and keeps returning
  `(text, tool_log)`; the private `_call_claude` route disappears behind it. Two public
  granularities remain: `engineer(...)` = one round for callers that own their loop (PEX);
  `engineer.flow_execute(...)` = one complete sub-agent run (the policies).
- [x] **T14 — one terminal path**: a second thinking-only miss routes through `_final_emit()`
  instead of returning `_FALLBACK_MESSAGE` directly; the canned string survives only as
  `_final_emit`'s own last resort. `orchestrate()` then has exactly two exits — the terminal
  reply text, or `_final_emit()`.

## Out of scope

- `call_mcp` implementation (no MCP server exists to wire).
- The Plan review pass (`_top_policy`'s TODO at pex.py:615 carries over verbatim).
- The click carve-out for code-first execution (option (a) for golden dax) — noted as a possible
  latency optimization, not built.
- `contains_keyword` (still the one flagged dead surface in the Context Coordinator).
