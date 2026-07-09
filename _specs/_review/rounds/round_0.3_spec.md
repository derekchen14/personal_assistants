# Round 0.3 — The sequential turn loop (no threads, code-only NLU/MEM)

Status: **built 2026-07-09** — Derek marked up the draft live; smoke transcript below. Follows
[[round_0.2_spec.md]] (world wiring). Goal: one user turn runs the five parts described in the
`Assistant.take_turn` docstring, end-to-end, with no Python threads, NLU and MEM as plain code,
and PEX as the only agent. Design ruling recorded during the build: PEX is a long-running agent —
its only LLM use is the loop over the persistent message list; the PromptEngineer's one-shot
calls belong to sub-agents (which build and destroy context within a turn) and MEM's summarizer.
NLU runs synchronously for now, so there is no speedup — but if NLU were async, the PEX loop
would just continue with its task, oblivious to the NLU and MEM modules.

## What gets deleted

- `Thread` in `Assistant.take_turn` and the turn-boundary `join`.
- `PolicyExecutor._nlu_thread`, `_check_nlu()`, and the `nlu_thread` parameter on `execute()`.
- The "Plan/Clarify wait at the belief read" rule — sequentially the belief is always written
  before PEX runs, so step 2b's await is satisfied by ordering, not by a wait.

## The turn: five parts

```python
def take_turn(self, text, dax=None, payload=None):
    self._ensure_session()
    self.world.context.add_turn('User', text, turn_type='action' if dax else 'utterance')

    # 0. Resolve any lingering ambiguity from last turn; an action turn reacts, then jumps to 3.
    if self.world.ambiguity.present:
        self.world.ambiguity.resolve()
    if dax:
        self.nlu.understand(op='react', dax=dax, payload=payload)
    else:
        self.nlu.understand(op='think', user_text=text, payload=payload)

    # 1-4. PEX's agent loop: System-1 intent attempt first (orchestrator prompt), then act.
    utterance = self.pex.execute(self.system_prompt, dax=dax, payload=payload, text=text)

    # 5. Store results into memory; MEM decides what to promote.
    self.mem.store_turn(utterance, self.pex.last_prompt_tokens)
    return self._build_payload(utterance, self.world.latest_artifact())
```

Notes per part:

- **0 — lingering ambiguity, and actions.** A leftover ambiguity from last turn is resolved (the
  new user turn is the answer; this turn's detection reads it in context). An action turn goes
  straight to `react`, then to step 3 — no detection.
- **1 — PEX's System-1 attempt is the first move of its agent loop.** No separate function, no
  extra call: the orchestrator prompt instructs the agent that its FIRST move on every turn is a
  fast working classification of the intent, before any tool call. It is a guess, never on the
  record — NLU owns the authoritative intent.
- **2a / 2b — the prompt's decide-by-intent rules.** Clear intent (Research/Draft/Revise/Publish)
  → PEX proceeds and dispatches the flow; the intents-match check is the intent-differs fallback
  hook (round 5.1) reading the `[belief]` note. Complex (Plan/Clarify/Converse) → the prompt
  requires `understand` op='read' before deciding. NLU's `think` runs synchronously before the
  loop (code order), so every belief read sees this turn's detection; the hint parameter on
  `think` goes unused for now.
- **3 + 4 — PEX acts.** The loop is unchanged; `execute()` loses the thread machinery plus the
  `state`/`context` parameters (PEX reads its own world references).
- **5 — MEM stores.** `mem.store_turn(utterance, prompt_tokens)` absorbs the Assistant's old
  `_epilogue`: record the agent turn, bump `turn_count`, refresh the stack copy and save
  `state.json` (the turn's snapshot — MEM's record, per the time rule), run the compression
  check (the summarizer moved along with it). `prompt_tokens` is PEX's real acting-loop usage,
  passed by the Assistant because the World holds components, not modules. Explicit saves
  already write L2 through PEX's `store_preference` tool mid-turn; the frequency and LLM-judge
  promotion criteria stay designed-not-built.

## Decision for sign-off

### D1 — `mem.store_turn` scope this round

- **D1-A (recommended)** — exactly today's epilogue moved under MEM (agent turn record, state
  snapshot, compression check) plus the explicit-save promotion path. One new module method, no
  new files on disk.
- **D1-B** — also write the end-of-turn stack snapshot as a separate MEM record (round 0.1's N1)
  and add `UserPreferences.save/load` (N2). More real memory, bigger round.

## File touch list

- `backend/assistant.py` — `take_turn` per the sketch; `_epilogue`/`_compression_check`/
  `_summarize_middle` move to MEM; `Thread` import dropped.
- `backend/modules/pex.py` — delete `_nlu_thread`/`_check_nlu`/`nlu_thread` param and the dead
  `_DOMAIN_INTENTS`; `execute()` drops the `state`/`context` parameters (the loop reads its own
  world references). PEX is a long-running agent: its only LLM use is the loop over the
  persistent message list; the PromptEngineer's one-shot calls belong to sub-agents (which build
  and destroy context within a turn), never to PEX-as-code.
- `backend/prompts/for_orchestrator.py` — INTENT_TAXONOMY opens with the System-1 rule: the
  agent's first move on every turn is a fast intent classification, before any tool call.
- `backend/modules/nlu.py` — no change (understand was already synchronous inside).
- `backend/components/memory_manager.py` — `store_turn(utterance, prompt_tokens)` per D1-A.

## Done means

A runnable smoke script (`utils/smoke_turn.py`, new file) drives one real 3-turn conversation
through `take_turn` — find a post → outline it → release it — against the live PEX agent, and
prints each turn's utterance, the belief (intent/flow/confidence), and the stack. That script is
the seed of the real E2E suite; the parked deterministic tests come back after this round,
rebuilt against the wired architecture.

### Smoke transcript (2026-07-09, live run)

```
== turn 1 ==
USER:   Can you find my draft titled 'Roman Concrete Heals Itself; Ours Just Crumbles'?
AGENT:  Found your draft "Roman Concrete Heals Itself; Ours Just Crumbles" — it's shown on the
        right with its details. What would you like to do with it?
belief: intent=Research flow=find confidence=1.0
stack:  [('find', 'Completed')]

== turn 2 ==
USER:   Great, put together an outline for it.
AGENT:  It looks like the post didn't carry over cleanly — could you confirm you'd like the
        outline for "Roman Concrete Heals Itself; Ours Just Crumbles"?
belief: intent=Draft flow=outline confidence=1.0
stack:  [('find', 'Completed'), ('outline', 'Active')]

== turn 3 ==
USER:   Looks good, release it to the blog.
AGENT:  "Roman Concrete Heals Itself; Ours Just Crumbles" is now live on the blog!
belief: intent=Publish flow=release confidence=1.0
stack:  [('find', 'Completed'), ('outline', 'Invalid'), ('release', 'Completed')]
```

Every turn detects the right intent/flow at 1.0 and the loop replies without a crash. One
behavior gap for a later round: turn 2's outline flow did not pick up the grounded post from
turn 1's find (it asked for confirmation), and turn 3's intent-differs fallback then correctly
retired it as Invalid when release took over. The grounding hand-off between flows is the gap,
not the turn loop. Two build fixes surfaced by the smoke: `_render_preferences` still read
`memory.preferences` (0.2 rename miss → `user_preferences`), and the script must `load_dotenv`
like the webserver/harness or the NLU voters lose their API key.

## Deferred

- Re-detection (`contemplate`) — removed from PEX in 0.2; under the sequential loop its natural
  home is step 0 (a turn that arrives while a flow is stalled re-detects over the failed flow).
  Not in this round; needs its own decision.
- The NLU scratchpad review (§3.3), MEM auto-promotion, preferences persistence (unless D1-B).
