# Round 2.12 — Stack Discipline Implementation

Maps to **Master Plan · Round 2 (PEX)**. This is the TEMPORARY implementation record for the stack
contract finalized 2026-07-09: everything here describes the gap between today's code and the
permanent contract, and closes when the work ships. The permanent contract lives in
`_specs/components/workflow_planner.md` (stack invariants, decision table, scenario matrix 1-21);
the problem history and settled decisions D1-D6 live in `round_3.3_spec.md`.

Already shipped (commit `b24c374`): fill-in-place against a stalled Active flow, persistent
ambiguity across detours, per-turn `counts` reset, `find` writing candidate records to
`grounding.choices`, MEM clearing consumed choices, the detour scratchpad note. Derek then removed
`manage_flows` op `activate` in PEX and added `_dispatch_top_policy` (runtime-owned policy
execution) + `flow_names` batch stackon. This round finishes both moves and closes the remaining
gaps.

---

## 2.12.1 — Remove 'bind before detecting': NLU always detects flows, then fills slots

The 'bind before detecting' concept from the round-3.3 implementation is REMOVED, not reordered:
there is no special path for any turn. NLU always runs flow detection, then slot-filling — uniform
across `react`/`think`/`contemplate`. From NLU's perspective there is no such thing as a fresh,
resumed, or Continue turn — every turn is the same two steps. Only the inputs differ: the `hint`,
the voter families, and which flow the fill lands on (the existing Active flow when detection
matches it, a new flow otherwise).

Current code to unwind: `nlu.py` `think()` runs `_bind_stalled_flow` BEFORE `_detect_flow` —
slot-filling first, detection only on an empty fill. That inversion goes.

Target shape:

```python
def think(self, user_text:str, payload:dict={}, hint:str=''):
    detection = self._detect_flow(user_text, hint)
    if self._intent_split(detection):
        intent = self._classify_intent(user_text)
        detection = self._detect_flow(user_text, hint=intent)

    flow_name = detection['flow_name']
    top = self.world.flows.get_flow()
    if top and top.status == 'Active' and top.name() == flow_name and not top.is_filled():
        return self._fill_active_flow(top, payload)       # fill in place: no new stackon

    ... today's fresh-flow path (transient fill, _repair_entities, belief, _stack_detected_flow),
    plus the detour note when an Active flow was jumped ...
```

- `_fill_active_flow` is `_bind_stalled_flow` minus the routing decision: fill the stacked flow
  (`_fill_slots(top, payload, stalled=True)`), `_repair_entities`, resolve the ambiguity when
  `is_filled()`, write belief from the detection tally as usual (no special confidence value —
  on a Continue turn the tally already covers PEX's vote plus the two off-family voters), refresh
  `state.flow_stack`.
- If the fill leaves the flow unfilled (vague answer that resolved nothing), the flow stays Active
  with its ambiguity — same turn-end shape as today; do NOT fall through to stacking a duplicate.
- Detection returning a DIFFERENT flow while an Active flow is mid-task = detour/abandonment; the
  detour path is `_stack_detected_flow` + `_note_detour` (both exist).

Renames (the `bind` vocabulary is banned): `_bind_stalled_flow` → `_fill_active_flow`;
`_fill_slots(..., bind=False)` → `stalled=False`; `build_bind_guidance` → `build_pending_question`
(for_nlu.py; the `<pending_question>` tag is already the name). Update the probe script
(`probe_bind.py` → `probe_fill.py`) to the detect-first semantics: mock `_detect_flow` to return the
matching flow for the answer case, a different flow for the detour case.

## 2.12.2 — Detour reverts the stalled flow to Pending

Contract: when a new flow is stacked over an in-flight Active flow, the Active flow reverts to
Pending ("queued and not yet completed"); `pop` later promotes it back and the runtime re-runs its
policy. SETTLED (planner spec scenario 10): `FlowStack.stackon` (stack.py) pushes the child AND
demotes the parent to Pending — when the current top is Active and a DIFFERENT flow type is pushed,
set the old top to Pending. Covers all three writers (NLU staging, PEX tool, policy prerequisites)
at one choke point; policy self-demotion becomes redundant and can be dropped from policies when
encountered.

Also in `stackon`: the duplicate check must become entity-aware (planner spec scenario 12b). Today,
when an unfinished flow of the same type is already on the stack, pushing that flow again does
nothing — the stack assumes the user repeated the same task and returns the existing flow. That
blocks stacking several `summarize` flows over different posts. The comparison is the value in each
flow's ENTITY SLOT (`flow.slots[flow.entity_slot]` — every flow declares one, an invariant that
holds across domains; not every flow has a post): a push whose entity-slot value differs is a new
task, not a repeat. Note: 12b also expects the same-type Active flows to run in parallel (the
Concurrency Model's asyncio tasks); the runtime currently runs one policy at a time, so this round
ships sequential execution and the parallel upgrade stays a separate task.

## 2.12.3 — No slot transfer while an ambiguity is open

Contract (scenario 15 + D-list): `stackon`'s matching-slot transfer is helpful ONLY when
no ambiguity is open — a stalled flow's values are exactly what is in question. Implementation
decision needed: `FlowStack` has no ambiguity reference. Options: (a) callers pass
`stackon(name, transfer=False)` when `world.ambiguity.present`; (b) FlowStack gets the handler at
construction. Proposal: (a) — two call sites (NLU `_stack_detected_flow`, PEX
`_dispatch_write_state`), no new wiring.

## 2.12.4 — Dispatch contract: restore `active=true`, finish the activate-removal fallout

SETTLED (2026-07-09): `stackon`'s `active` flag DEFAULTS TO TRUE — push and run, so most turns never
mention it; `active=false` queues a plan step as Pending without running it. Exactly three stack
events run the top policy: `stackon` (default), `fallback`, and a `pop` that surfaces a Pending
flow. `update` never triggers a run. Code changes in `pex.py` `_dispatch_write_state`: restore the
`active` param with default true (gate `_dispatch_top_policy` on it); keep the auto-run on fallback
and pop; drop it from update. Proposal: drop the `flow_names` batch param — plan queuing is now
sequential `stackon(active=false)` pushes with the final step pushed plain.

The op removal also left 10 red tests and three stale prompt/doc surfaces that still instruct
`op="activate"` (the orchestrator collects corrective tool errors until swept):

- `utils/evaluation_suite/_tests/pex_unit_tests.py` — TestOrchestratorDispatch::
  test_manage_flows_stacks_and_saves; TestDispatchFlow (4: completion_record, write_state_slots,
  non_completed_status, empty_artifact); TestPolicyCompletion (2: record_once, ungrounded_block);
  TestSingleCallStackon::test_stackon_without_active_only_stacks; TestBeliefInjection::
  test_intent_differs_forces_fallback; TestPlanLifecycle::test_plan_flows_survive_completion.
  Update each to the new contract: `op='activate'` is `invalid_input`; `stackon(active=true)`,
  `fallback`, and pop-promotion run the top policy (`_dispatch_top_policy`); a plain stackon only
  pushes. Tests that only need "run this policy now" can call `pex.activate_flow(...)` directly —
  it is internal runtime plumbing, not a tool.
- `backend/prompts/for_orchestrator.py` (~lines 84-95, 115, 132) — rewrite the flow-running
  instructions: stackon (active defaults true), fallback, and pop-promotion run the top policy;
  there is no activate op; selecting the Continue intent triggers the Active flow's run.
- `backend/prompts/pex/skills/plan.md` (line 18) and `utils/helper_ref.md` (line 226) — same sweep.

## 2.12.5 — The Continue intent (8th PEX intent option)

New intent for the PEX agent's choice set: **Continue** — this turn advances the flow that is
already Active; no new flow, no re-route (permanent statement in the planner spec's "The Continue
intent"). Eight options total: Research, Draft, Revise, Publish, Converse, Plan, Clarify, Continue.
Implementation surfaces:

- `backend/prompts/for_orchestrator.py` — the System-1 intent taxonomy grows to 8. Prompt rules for
  Continue: legal only while an Active flow exists; pick it when the utterance answers the open
  question, elaborates on the active task, or says "keep going"; after picking it, make progress on
  the Active flow (run its policy) instead of stacking anything.
- NLU `hint` handling (`nlu.py`) — on a Continue turn the Assistant passes the ACTIVE FLOW NAME as
  the hint, not an intent. `_flow_candidate_names` gets a flow-name branch: candidates = that flow
  plus its edge flows. nlu.think() otherwise operates exactly the same — flow detection, then
  slot-filling; no special path.
- Voter config — a Continue turn runs TWO medium voters instead of three, because PEX already
  offered a flow-level vote by selecting Continue. The two families are the ones PEX is NOT running
  on (read the orchestrator family from config): Claude-PEX → gemini + gpt; GPT-PEX → gemini +
  claude; Gemini-PEX → gpt + claude. SETTLED: PEX's active-flow selection seeds the votes list as
  the third vote, so `_tally_votes` / `_score_votes` run unchanged over three votes (3/3 = 0.9,
  2/3 = 0.7, splits as today).
- `Intent`/taxonomy surfaces that enumerate PEX's options (orchestrator prompt text; NOT
  `schemas.ontology.Intent`, which stays the six flow-owning intents unless ruled otherwise).

## 2.12.6 — Dispatch trigger when continuing an Active flow — SETTLED (planner scenario 20)

Continuing a stalled Active flow performs no stack operation, so nothing fires
`_dispatch_top_policy`. SETTLED: PEX selecting the **Continue** intent (2.12.5) IS the trigger —
the runtime runs the Active flow's policy. Recovery when PEX mispredicts a task intent instead:
`manage_flows(op="update", fields={status: "Active"})` re-runs the flow — a status write through
`update` is the manual run button; an `update` that only touches slots never triggers a run.

## 2.12.7 — Reconcile the revise slot-prompt rules with the snippet-id doctrine

Found while working scenario 15. The settled doctrine (2026-07-09): NLU always fills the WHOLE
entity `{post, sec, snip, chl}` — never a lone part — and on a re-fill it is expected to keep the
same `post`/`sec` rather than change them. `snip` stores an id: a sentence index or an
end-exclusive `[start, end]` slice per `schemas/tools.yaml` (`read_section`/`revise_content`), which
the policy resolves by reading the section — NLU leaves it empty unless an id is actually present
in the context. One surface currently contradicts this:

- `backend/prompts/nlu/revise_slots.py` instructs snip-only fills carrying description values
  ("fill `source.snip` and leave `post`/`sec` off — this triggers a re-route to Write"; exemplars
  hold values like "the second paragraph in my methods section"). Rewrite the rules and exemplars:
  the full entity every time, `snip` only as an id, and paragraph-scope routing signaled by flow
  detection (write vs rework), not by a description parked in `snip`.

With that fixed, `WriteFlow.source = SourceSlot(1, 'sec')` is correct as-is — the fallback hands
write `post`+`sec` and the policy fills `snip` — so the earlier idea of loosening write's
filled-check to "sec OR snip" is withdrawn.

## 2.12.8 — Turn-end invariant check (log-only)

After `store_turn`, log a warning when the turn-end shape is violated (a Pending flow on top, or a
Completed/Invalid entry surviving). Post-hooks validate, they never rewrite state — this is a diagnostic,
not a guard. Small; ship last.

## 2.12.9 — Ontology change: `inspect` restored, `browse` merged into `find`

`inspect` {1AD} is back in FLOW_ONTOLOGY (Research): reports metrics and metadata — word/section
counts, reading time, image count, post size, tags, dates, channels, status — absorbing the old
`check`. `browse` is merged into `find` (find's description already covers posts, drafts, and
notes). Ripples to sweep this round:

- `flow_stack/__init__.py` + `flows.py`: add `InspectFlow` (slots/tools per the ontology entry),
  delete `BrowseFlow`.
- `policies/research.py`: add the `inspect` dispatch + policy — per planner scenario 18, the
  sub-agent reaches MEM/metadata for the answer, writes the result to the session scratchpad, and
  completes; remove `browse_policy` (its note-search behavior folds into `find_policy`).
- Prompts: `prompts/nlu/research_slots.py` (browse → inspect entries), the experts/research
  exemplars, the `pex/skills/` + `starters/` files (the flow_classes lint couples these), and the
  orchestrator taxonomy text.
- `FLOW_ONTOLOGY` stale edge reference: `brainstorm.edge_flows` still lists 'browse'.
- Tests and dev fixtures that name `browse` (nlu react rows, unit tests, eval scenario labels) —
  update as touched; the eval scenarios are dev-set fixtures, not gates.

## Rulings landed (planner spec scenarios 18-21, settled 2026-07-09)

- **18 (compound utterance)** — detection keys on the new request (`inspect`); the resumed flow's
  slot-filling captures the answer clause later. The planner spec's scenario 18 walkthrough is the
  reference behavior for the inspect policy (2.12.9).
- **19 (cancel everything)** — new method `FlowStack.update_flow(flow_name, **fields)`: unlike the
  top-only ops, it reaches any depth (like `find_by_name`) and writes slots/stage/status in place
  without running anything. Rewire `DialogueState._update_flow` / the manage_flows `update` op onto
  it; PEX cancels a whole stack by marking each flow Invalid, then one `pop` sweeps them all.
- **20 (dispatch trigger when continuing an Active flow)** — settled in 2.12.6: Continue is the trigger.
- **21 (concurrent ambiguities)** — `recognize()` must ADD to `metadata` without kicking out prior
  keys, and `counts` keeps incrementing (multiple open ambiguities are legal); `observation` is
  immutable — never appended to, may be lost in an overlap. Consequence for the round-3.3 code:
  `_note_detour` currently appends to `observation`; move the detour note into `metadata` (the
  scratchpad note stays).

## Verification

1. `run_suite.py --tests` green (244 baseline, minus tests deleted by the activate sweep).
2. `probe_fill.py`: answer-turn fills the Active flow in place (no new stack entry, ambiguity
   resolved); detour-turn stacks the detected flow, stalled flow reverts to Pending, ambiguity
   persists, scratchpad note written.
3. Replay the round-3.3 trace cases (`B05.C09`, `B06.C12`, `B05.C06`) — reply turns fill the
   existing flow instead of stacking duplicates.
