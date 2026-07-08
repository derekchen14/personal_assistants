# Round 5.1 — Workflow Planner skill + NLU belief state injection

Status: APPROVED IN DIRECTION 2026-07-03 (the user), mechanism REVISED by the user 2026-07-03: the
round 2.7 gate analysis called this a "mismatch gate" — wrong on both words. It is **NLU belief
state injection**: belief is injected into the PEX orchestrator context on every turn, mismatch or
not. Implements `round_5_plan.md` (locked §5.1-§5.4) plus the injection.

**AMENDMENT 2 (the user 2026-07-03, applied post-build):**
- No "staging" language anywhere — it is "stacking on" / "stacking a flow". Code renames:
  `prestage()` → `prestack()`, `_stage_flow()` → `_stack_flow()`; prompt and spec text swept.
  (The pre-existing `stage` FIELD on flow entries is a different concept and stays.)
- No "catalog flows" — say "flows in the existing ontology" / "existing flows". The
  anti-invention clause stays (LLMs do make up flow names).
- Plans stack ALL relevant flows AT ONCE (reversing the one-at-a-time model): reverse execution
  order, first-to-run pushed last with `active: true`. The stack holds the plan — observable by
  any agent, survives orchestrator mistakes and compaction.
- The pending mode is real now: `_push` lands flows as Pending (was hardcoded Active);
  activation (`_stack_flow`, `pop_completed`) promotes to Active. `fallback`'s replacement goes
  straight to Active — it takes over from a flow that was already running.

**AMENDMENT (the user 2026-07-03, applied by the orchestrator after the builds land):**
- Rename `_dispatch_read_state()` → `pex.read_state()` (public) — it IS how PEX reads the NLU
  belief state; the name should say so.
- Rename `_settle_nlu()` → `inject_belief_state()` — "settle" is wrong (NLU may not have finished
  thinking, and NLU also holds the Ambiguity Handler and Session Scratchpad, which this function
  does not cover); the function's job is bringing NLU's belief into PEX.

## What this round builds

1. **The Workflow Planner skill** (`backend/prompts/pex/skills/plan.md`) — how-to guidance for the
   Plan intent: decompose into EXISTING catalog flows, order by dependency, stage and run one at a
   time, share a one-line plan, judge goal completion after each flow (round_5_plan §5.1-5.2). The skill
   returns nothing; PEX issues the stack ops itself.
2. **NLU belief state injection** (the user 2026-07-03, replaces the "mismatch gate"):
   - Once per turn, the landed detection (intent, top flows + confidence, slots) is injected into
     the orchestrator's context — REGARDLESS of whether it matches the active flow.
   - Injection is attempted at hook points **② pre-tool-call, ③ post-tool-call, ④ tool-retry,
     and ⑤ post-LLM**, until it succeeds once. ① pre-LLM is too early (NLU has usually not
     answered yet); ⑥ verification is too late (the work is already done). **None of these hook
     points force an NLU response** — each checks briefly whether NLU has completed
     (`_settle_nlu(wait=False)`), incorporates what NLU has to say if so, and otherwise
     continues. This is in contrast to the injection points caused by Plan and Clarify, which
     REQUIRE awaiting NLU (their `read_state` blocks).
   - **Flow differs, same intent** → the ORCHESTRATOR decides: continue the original flow or stop
     and go with NLU's proposed flow. The prompt tells it to defer to NLU in most cases (80%+).
   - **Intent differs** → CODE forces a FALLBACK (the user 2026-07-03): the active flow is marked
     Invalid — we are not coming back to it — and NLU's detected flow takes over as Active. No
     orchestrator discretion.
   - **Any other issue during policy execution** → re-consult NLU via `nlu.contemplate()`
     (nlu.py:118, the failed-flow re-route with narrowed candidates) — never `think()`.
3. **Depth 8→16** (`shared/shared_defaults.yaml:55`, `stack.py:12` fallback). Keep the overflow
   `RuntimeError`.
4. **Remove dead Plan state** (round_5_plan §5.4): `has_plan`
   (dialogue_state.py:9,62,100,115,129,155,249; revise.py:67,227 — redundant with completion
   records) and `plan_id` (parents.py:14,87; dialogue_state.py:44,170,215; stack.py:17,27,97-108;
   pex.py:578,960,979). NOTE (SWE1 round-1 finding): the removals also touch suite files
   (nlu_unit_tests.py, mem_unit_tests.py, _snapshot.py) — the orchestrator fixes those, not the
   builders.

## New concepts

1. **The Workflow Planner skill file** (`skills/plan.md`), read once by
   `build_orchestrator_prompt` into Tier 2 via the existing `load_skill_template`. Content: map
   sub-tasks to catalog flows only, order by dependency, stage and run ONE AT A TIME (stacking the
   whole sequence up front breaks the single-Active model — SWE1 round-1 finding, supersedes the
   earlier "bottom = last" example), one-line plan to the user, judge the goal after each flow.
2. **Belief injection state**: a per-turn `injected` flag + one builder that formats the belief
   note, e.g. `[belief] this turn's detection — intent: Revise, flow: rework (0.86), slots:
   {source: [...]}. If you are on a different flow, prefer NLU's detection unless you have a
   concrete reason to stay.` Plus the intent-differs forcing step (pause + stage) in code.

No other new state: injection reuses `_settle_nlu(wait=False)`, `pred_flows`/`pred_intent`,
`flow_stack`, and the existing message list.

## Big decisions (trade-offs)

**1. How injection physically lands in the message list (API pairing constraint).**
An assistant message with `tool_use` blocks must be followed by a user message whose content is
the matching `tool_result` blocks — a free-standing user text message cannot sit between them.
- (A, chosen) Two carriers: during tool rounds, the belief note rides the SAME user message as
  that round's tool results (an extra text block beside the `tool_result` blocks — API-legal);
  after a text-only model response (⑤ post-LLM), the note is appended as its own user message and
  the loop runs one more round instead of ending the turn. Pros: covers ②③④ moments with zero
  extra rounds; the ⑤ path catches exactly the failed turns from the 2.7 gate (12/15 ended
  text-only, no tool calls); never blocks. Cons: two code paths for one concept; a text-only turn
  that ends before NLU lands is still possible (rare — the boundary join then reconciles at the
  next turn).
- (B) Inject only at ⑤ (one carrier). Pros: single path. Cons: tool-heavy turns get belief a full
  round later than necessary — the staging decision may already be made.
- (C) Rewrite context mid-turn (edit earlier messages). Rejected: mutating history breaks the
  append-only context and prompt caching.

**2. Where the Workflow Planner guidance lives** — unchanged from round-1 plan: skill file read
into Tier 2 (locked round_5_plan decision; ~250 tokens/turn riding the prompt cache), over a prompt
constant or on-demand loading.

**3. Intent-differs forcing mechanics.** Code compares `pred_intent` to the active flow's intent
at injection time; on difference (and no pending ambiguity, and a domain `pred_intent`): a
`fallback` — active flow → Invalid, NLU's `pred_flows[0]` swapped in as Active — and the belief
note states what was forced.
Trade-off: a wrong NLU intent now overrides the orchestrator with no appeal — accepted, NLU's
intent is authoritative by design ("coarse intent is NLU's authoritative write", pex.md); the
counterweight is round 2.3 exemplars.

## Alternatives considered (not built)

- **Blocking injection** (wait for NLU at ②): rejected — only Plan and Clarify wait (the user's
  dispatch rule); flow execution never blocks.
- **Corrective-error-only reaction at pre-flow** and **prompt-only strengthening**: both rejected
  in round-1 planning — they miss text-only turns, which are the dominant failure.
- **Per-step replanning** (§S-1), **multi-active concurrency** (§S-2): deferred per round_5_plan.
- **LATS decomposition search**: dropped in round_5_plan.

## Build list

1. `backend/prompts/pex/skills/plan.md` — the Workflow Planner skill (new file).
2. `backend/prompts/for_orchestrator.py` — Tier 2 reads the skill; Plan bullet points at it; a
   belief-note rule in TOOL_POLICY: when a `[belief]` note arrives and names a different flow,
   defer to NLU's detection unless there is a concrete reason to stay (80%+ defer).
3. `backend/modules/pex.py` — per-turn `injected` flag; `_inject_belief()` (settle wait=False,
   landed? format note; intent-differs → pause active + stackon pred flow); call attempts at the
   ②③④ carrier (the tool-results message in `_run_loop`) and the ⑤ carrier (text-only response
   branch, continue one round); route policy-execution failures to `nlu.understand(op=
   'contemplate')` where the loop currently retries blind; remove `plan_id` from the write_state
   schema/dispatch.
4. `shared/shared_defaults.yaml` + `flow_stack/stack.py` — depth 16.
5. `dialogue_state.py`, `flow_stack/parents.py`, `stack.py`, `policies/revise.py` — remove
   `has_plan` + `plan_id`.
6. Tests (orchestrator writes them): injection lands exactly once (tool round and text-only
   variants); intent-differs pauses and stages in code; flow-differs leaves the decision to the
   model (no forcing); depth 16; serialization drops `plan_id`/`has_plan`.

## Verification

- Free suite green, 0 skips (including the suite-file fixes for the removals).
- Live gate, standard 8: completion target > 0.60; watch mean turn seconds (the ⑤ carrier adds a
  round only on text-only turns whose detection landed).
- Smoke: a multi-step request runs flows one at a time with goal judgment; an intent-differs turn
  visibly pauses and switches; a flow-differs turn shows the model deferring to NLU.
