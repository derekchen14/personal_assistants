# Round 3.5 — Plan decomposition and the missing NLU prompts

Status: EXPANDED 2026-07-17. The original scope (the `propose` slot-fill prompt) shipped 2026-07-03
in PR #5 and survives in the current registry — its record is preserved at the bottom. The round now
covers plan decomposition from NLU plus every remaining NLU prompt gap for the no-policy flows.
Owner module: **NLU**. See also [[round_3.4_spec.md]] (T8's plan branch, the detection snippet).

---

## What is missing today (audited 2026-07-17)

Derek's working assumption was that {29D}, {000}, {09F}, and {39B} are all missing. The audit says
two of the four already exist:

| Flow | dax | Slot-fill prompt (`backend/prompts/nlu/`) | Detection prompt (`backend/prompts/experts/`) | Flow class |
|---|---|---|---|---|
| `chat` | {000} | **exists** (`converse_slots.py`) | **exists** (`converse_flows.py`, keyed 'Converse') | exists (`topic` slot) |
| `propose` | {39B} | **exists** (`revise_slots.py` — the PR #5 fix survived the Phoenix rewrite) | **exists** (exemplar in `revise_flows.py:50`) | exists (`source` + `context`) |
| `plan` | {29D} | missing | **missing — `get_prompt('Plan')` raises KeyError** | none (by design, see below) |
| `clarify` | {09F} | missing | **missing — `get_prompt('Clarify')` raises KeyError** | none (by design, see below) |

Verification commands:

```
python -c "from backend.prompts.nlu import PROMPTS; from schemas.ontology import FLOW_ONTOLOGY; \
  print(sorted(set(FLOW_ONTOLOGY) - set(PROMPTS)))"        # → ['clarify', 'plan']
python -c "from backend.prompts.experts import PROMPTS; print(sorted(PROMPTS))"
  # → ['Converse', 'Draft', 'Publish', 'Research', 'Revise'] — no Plan, no Clarify
```

Two standing decisions carried in from round 3.4 shape what "missing" means for plan and clarify:

- **`plan` oversees, it does not do the work** (per the 2026-07-17 marker rulings — see
  Unresolved Issues). A Plan turn stackons a Pending Plan Flow at the bottom and the detected
  STEPS (domain flows) above it. The Plan Flow anchors `has_plan` and carries a ChecklistSlot
  of the flows it oversees; when it eventually surfaces as Active, its policy reviews what the
  steps did (reading the session scratchpad) and makes final adjustments — a FUTURE round's
  work, TODO comments only for now, so this round it is removed when it surfaces. No slot-fill
  prompt (think writes the checklist directly, no LLM fill). The gaps are the multi-flow
  detection template (this round's centerpiece), the PlanFlow class, and surviving
  `get_prompt('Plan')`.
- **`clarify` is never stacked.** `think` routes it through `_write_non_policy_belief`
  (`nlu.py:132-146`): the Ambiguity Handler recognizes a general ambiguity and the scratchpad entry
  says "detected clarify; nothing stacked". So `clarify` needs no flow class and no slot-fill prompt
  either. Its gap is surviving `get_prompt('Clarify')` and a sane candidate list.

So the deliverables are: (1) list detection — the `flows`-array schema, the one-or-many prompt
instructions, and the `think` wiring that stacks a Plan turn's steps, (2) detection-prompt
coverage for the Plan and Clarify intents, (3) a fix to Clarify's candidate narrowing. Nothing to
author for {000} or {39B}.

## 3.5.1 — Plan decomposition from NLU

### Problem

Detection returns ONE flow (`_flow_detection_schema`, `dialogue_state.py:19-31`). Round 3.4's T8
promises "a Plan detection stackons every step in reverse execution order", but no prompt or schema
exists that returns a step list — S7's find → outline → schedule has nowhere to come from. Today
`_write_non_policy_belief('plan')` sets `state.has_plan = True`, stacks nothing, and validate's plan
entry records the empty decomposition (`nlu.py:132-139` carries the TODO).

### Solution Contract

**No `decompose_plan` — flow detection itself returns a LIST (Derek, 2026-07-17).** The model is
`handling_ambiguity/prompts/flow_detection.py` (exp 1): the detection output becomes
`{"reasoning": ..., "flows": ["<flow>", "<optional_second_flow>", ...]}`, so multiple flows are
detected in the ONE existing call. This is primarily a prompt + schema update, not a new concept:
the belief's `pred_flows` is already a list, `think` already stacks from it, and the plan case is
just the multi-entry reading of the same output. A plan turn's steps ARE its detected flows, in
execution order; there are no per-step `goal` strings and no second LLM round.

- `_flow_detection_schema` — `flow_name` (single enum) becomes `flows`: an array of enum strings
  (`{'type': 'array', 'items': {'type': 'string', 'enum': candidates}}`). Run it through the
  offline schema linter; verify `minItems` survives the provider rules or enforce non-empty in
  code.
- The base flow prompt gains exp 1's instructions 3-4: most utterances map to ONE flow; output
  multiple only for a genuinely multi-part request (exp 1's example 5: "rework" + "syndicate")
  or when two readings are both plausible. The Plan snippet (picked by `check` when
  `pred_intent == 'Plan'`) instructs the ordered decomposition: every step a stackable domain
  flow, in execution order, 2-5 steps.
- `PLAN_PROMPT` in a new `backend/prompts/experts/plan_flows.py` (exports
  `PROMPTS = {'Plan': ...}`, closing the `get_prompt('Plan')` KeyError) — instructions/rules/
  examples teach the ordered multi-flow output, with one S7-style exemplar (find → outline →
  schedule) and one two-step exemplar.
- `think` consumes the list: a single flow runs today's path on `flows[0]`; a Plan turn with
  multiple flows sets `has_plan`, stackons the steps in reverse execution order (`active=False`,
  first step Active), and validate writes the plan entry (summary lists the steps; no `new_flow`
  key, so hooks 3/5 skip it). No slot fill on the plan pass — each step's policy fills its own
  slots with `fill_slots_by_label` when it runs, and step inputs usually depend on earlier
  steps' outputs anyway.
- The ensemble tallies per flow, with the membership/order defaults settled 2026-07-17 (an
  algorithm tuning problem — these are the defaults, revisit later):
  - **Membership:** every flow any voter names goes through the tally and survives on majority
    support. Predictions `[[A], [A, B], [A]]` → A survives at 3/3; B drops at 1/3.
  - **Order:** the Claude voter's proposed order is canonical — Sonnet among the 3 medium
    voters, Opus once the 5-voter escalation ran. If Claude predicted `[B, C, D, E]` and the
    survivors are D, E, and B, the order is B > D > E; since this is a stack, `think` appends
    in reverse — E first, then D, then B on top. Edge handling: a survivor Claude never named
    follows the Claude-ordered ones in support order; if the Claude vote was lost (provider
    outage), fall back to the highest-support voter's order.
  - `pred_flows` keeps its exact shape — ranked `{name, dax, confidence}`, confidence = that
    flow's support across voters, survivors first, dropped flows after. The candidate flows
    and their tallies are ALSO written to the turn's scratchpad entry (Derek, 2026-07-17) —
    the back-up channel: PEX can stack a dropped flow later or do other clean-up. Multi-flow
    output on a NON-plan turn is exp 3's cardinality signal: the alternatives ride
    `pred_flows` as they do today, and the existing low-confidence machinery
    (`needs_clarification`) decides whether to ask.

### Implementation sketch

```python
# dialogue_state.py — the schema's one changed property:
'flows': {'type': 'array', 'items': {'type': 'string', 'enum': list(candidate_flow_names)}}

# nlu.py — think consumes the list; the plan path replaces _write_non_policy_belief's branch:
flows = detection['flows']
if state.pred_intent == 'Plan' and len(flows) > 1:
    state.has_plan = True
    for step in reversed(flows):                    # last step first → first on top
        self.world.flows.stackon(step, transfer=False, active=False)
    self.world.flows.get_flow().status = 'Active'   # the first step runs now; the rest wait
```

Two items carried in from round 3.4's T21 verification (2026-07-17) — both bite only once plans
actually stack steps, so they land here:

- **The back-to-PEX-2 loop has no take_turn counterpart.** The Canonical Turn table says "if
  flow_stack still has pending flows go back to PEX 2 to loop"; today `take_turn` runs
  `pex.execute` once (plus the one contemplate re-entry) and step chaining happens inside that
  single pass — the agent activates each surfaced `next_flow` across its own rounds. Decide with
  the decomposition work whether a take_turn re-entry loop is needed (and its guard — likely
  `state.has_plan`, so non-plan Pending work still waits for the user) or whether the single-pass
  agent loop covers S7's "each pass runs the next step" as is.
- **validate's plan branch swallows mid-plan announcements.** `elif state.has_plan` fires on
  EVERY NLU pass while a plan is live, so a divergent detection on a mid-plan turn writes a plan
  entry (no `new_flow` key) instead of an announcement — hooks 3/5 can never surface it. The
  branch needs a narrower condition, e.g. only on the pass where think stacked the steps.

## Scenario walkthroughs (S7 and S8, moved from round 3.4)

The Plan and Clarify traces, expanded over the Canonical Turn (round_3.4_spec.md) —
the target behavior once this round lands. Their phase rows read exactly like the
other nine scenarios; the S numbering is shared across the two files.

### S7 — Plan: multiple stacked (not queued) steps

"Find my three best posts, draft a new one on that theme, then schedule it." Starting on an empty stack.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | empty stack |
| NLU 1 | `classify_intent` | intent: Plan — no real signal |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | clears any prior ambiguity; picks the Plan detection snippet |
| PEX module | `prepare` | **wait** — hook point 1: Plan blocks here until NLU settles |
| PEX 2 | - | skipped, stack is empty so no model call needed to manage workflow |
| NLU 2 | `detect_flows` | the detection returns the ordered step list — `{"flows": ["find", "outline", "schedule"]}` (the Plan snippet instructed the multi-flow output; one call, no separate decomposition) |
| NLU module | `think` | multiple flows on a Plan turn: sets `state.has_plan = True`, stackons the Plan Flow first (`stackon('plan', active=False)` — Pending at the bottom, its `steps` checklist filled directly with find → outline → schedule), then every step in reverse execution order — `stackon('schedule', active=False)`, `stackon('outline', active=False)`, `stackon('find', active=False)`, then the top step is marked Active |
| NLU 3 | fill_slots() | skipped, since state.has_plan |
| NLU module | `validate()` | writes the plan entry as always — summary lists the stacked steps (no `new_flow` key, so hooks 3/5 never mistake it for a conflict) |
| PEX module | `execute` | prepare's hook-1 block has ended; `understand(op='read')`'s document carries the stacked plan in `flow_stack` → PEX reviews it and runs the top step (`manage_flows` op='update', fields={'status': 'Active'} on `find`) |
| PEX 4 | policy sub-agent | `find` looks for three posts |
| PEX module | — | the hook-3 read finds only the plan entry (no `new_flow` key) — nothing to surface |
| PEX 5 | manage_flows() | skipped |
| PEX module | `verify()` | same |
| Assistant | `take_turn` | the plan steps wait Pending → back to PEX 2 to loop; each pass runs the next step until no Pending flow remains. There's a good chance we get stuck on schedule since we haven't converted the outline to prose yet. Schedule may try to stack on 'compose', but let's assume the agent decides to ask for clarification this time. |
| PEX 6 | `respond` | Ask a clarification question with `ambiguity.ask()` |
| MEM module | `start()` | system turn added: completed: find, outline · active: schedule |
| MEM 7 | `_compaction` + `_promote` | same |
| MEM module | `finish()` | same |

### S8 — Clarify: waiting on NLU results

"Can you come up with a few angles for describing the bifurcation process?"
This is a brainstorm {39D} flow, but the TypeSafe classifier can't reach it: the Draft intent
really only lines up with outline {002} at the basic-flow mapping, so the needs_clarify noul
crosses the 0.8 gate and classify_intent stores Clarify. NLU takes on the responsibility for
choosing the correct flow — the Clarify template says commit only at EXTREME confidence and
abstain (an empty `flows` list) otherwise. Here the utterance itself is unambiguous, so the
voters commit.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | empty stack |
| NLU 1 | `classify_intent` | intent: Clarify — the needs_clarify noul crossed the gate |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | clears any prior ambiguity; picks the Clarify detection snippet (extreme confidence or abstain) |
| PEX module | `prepare` | **wait** — hook point 1: Clarify blocks here until NLU settles |
| PEX 2 | - | skipped, because Clarify is not an actionable prediction |
| NLU 2 | `detect_flows` | Clarify owns no flows, so `_candidate_names` falls back to the full 16-flow list; every voter returns `{"flows": ["brainstorm"]}` — "come up with a few angles" is idea generation beyond doubt |
| NLU module | `think` | the single-flow path on `flows[0]`: since Clarify carried no flow there is no possible conflict, so NLU directly places {39D} on the stack |
| NLU 3 | fill_slots() | NLU predicts slots for brainstorm and runs `fill_slot_values()` |
| NLU module | `validate()` | makes sure slot-values are valid, writes the detected flow as an entry in the scratchpad (with the candidate tally) |
| PEX module | `understand` | after prepare's hook-1 block, the document's `flow_stack` shows `brainstorm` {39D} stacked and filled |
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

**The abstention ending (the other half of S8).** On a truly hopeless turn ("can you do
something with the draft") every voter abstains: the tally returns
`{'flows': [], 'confidence': 0.0, 'pred_flows': []}`, think stacks nothing, recognizes the
general ambiguity, and validate writes the "no confident detection; nothing stacked" entry —
the deliberate abstention survives (the chat fallback only fires on a non-empty prediction).
PEX's hook-1 read finds an empty stack and the open ambiguity, and the agent is heavily
pushed to end the turn with `ask_clarification_question` — the machinery working exactly as
it already does on low confidence.


## 3.5.2 — Clarify {09F} detection coverage

### Problem

Two breaks when the working intent is Clarify:

1. `get_prompt('Clarify')` raises KeyError (`experts/__init__.py:97-98`) — the moment
   `state.pred_intent` is 'Clarify' (round 3.4's T16 classifier, or a future tie-break value),
   `_detection_prompt` crashes the think lane. Same for `get_prompt('Plan')`. T16 LANDED
   2026-07-17, so the crash is live: every Plan/Clarify classification fails the turn until
   the registry entries here (`plan_flows.py`, `clarify_flows.py`) land — they are this
   round's most urgent piece, and should land with or before T17 (the TypeSafe swap) so the
   real classifier is judged against a working detection path.
2. `_candidate_names('Clarify')` narrows to `['clarify']` alone — clarify's ontology entry has no
   edge flows, so detection would be a one-option vote. The Clarify snippet says the opposite:
   "Detect the closest flow anyway — low agreement is expected and raises a clarification
   downstream" (`for_experts.py:372-375`).

### Solution Contract

Author a small `CLARIFY_PROMPT` (new `backend/prompts/experts/clarify_flows.py`, exporting
`PROMPTS = {'Clarify': CLARIFY_PROMPT}`): instructions say the turn is underspecified and the job is
the closest reading over the FULL flow list; one exemplar where the vote lands on a domain flow with
low agreement. And `_candidate_names` keeps the full candidate list when the intent maps to no
stackable flow (Clarify's flow set minus non-stackables is empty) — a rule, not a special case:
narrowing that produces zero stackable candidates falls back to the full list.

No slot-fill prompt and no flow class: `clarify` is never stacked (see the table's standing
decision). The `{09F}` dax stays label-only for eval ground truth.

## New concepts introduced

**None requiring new surface.** `decompose_plan` was struck (Derek, 2026-07-17): flow detection
always returns a list of flows — usually one entry, the same structure every turn — and a
Plan-classified turn uses a prompt template that heavily encourages predicting multiple flows.
That is a schema property rename (`flow_name` → `flows`) plus prompt work inside the existing
registries; the only new files are the two intent modules `plan_flows.py` and `clarify_flows.py`
(new files in an existing pattern, not a new pattern).

## Unresolved Issues

All resolved 2026-07-17 (folded into 3.5.1 and the todo) — nothing open; the round is ready
to build:

- Decomposition trigger + where step goals live → dissolved together: there is no plan
  decomposition and no goal strings. Flow detection always returns a list of flows (usually one;
  the structure never changes), a Plan classification swaps in a prompt template that heavily
  encourages multiple flows, and the steps ARE the detected flows in `pred_flows`. A separate
  failure path also dissolves — a plan turn whose detection returns one flow simply runs one
  flow.
- Ensemble membership + order → ruled as tuning defaults (revisit later): majority survival
  through the per-flow tally; the Claude voter's order is canonical (Sonnet at 3 voters, Opus
  at 5), with think stacking the survivors in reverse of that order. Folded into 3.5.1.
- Clarify meaning → the Clarify intent swaps in the clarify prompt template, which encourages
  detecting a flow ONLY at extreme confidence — everything else stays the same. The likely
  result is an EMPTY flows list (voters abstain), which carries no ensemble agreement, so
  `needs_clarification` fires, the Ambiguity Handler recognizes a general ambiguity, and PEX is
  heavily pushed to `ask_clarification_question` when ending the turn — the machinery working
  exactly as it already does. Implementation consequences (T4/T5/T6): the schema allows an
  empty array; `_collect_votes` KEEPS abstentions (an empty list is a vote for nothing and
  counts in the majority denominators); the tally's all-abstain case returns
  `{'flows': [], 'confidence': 0.0, 'pred_flows': []}`; think's empty branch stacks nothing
  and writes a "no confident detection; nothing stacked" entry; validate's chat-fallback must
  not overwrite a deliberate abstention. S8 gets rewritten to this shape (T6).
- plan/clarify as candidates → they leave `FLOW_ONTOLOGY` entirely: there are exactly 16 flows
  to choose from. The Intent enum keeps Plan and Clarify; the {29D}/{09F} daxes stay label-only
  in the eval-dataset contract. On a hopeless turn the voters abstain (empty list) and the
  clarification declares naturally — no special label needed. Checkpoint for T8: sweep the eval
  tooling for plan/clarify ontology lookups so the label vocabulary diverging from the runtime
  ontology breaks nothing.
- The round budget → solved with a reset, not a bigger budget: `_run_loop` becomes
  `while round_idx < self.max_rounds:`, and a completed flow resets `round_idx = 0` — every
  plan step starts with a fresh budget. This also settles the carried back-to-PEX-2 item:
  step chaining stays in the single pass (no take_turn loop); the Canonical Turn's
  "back to PEX 2" row gets aligned when T7 lands.

- Plan Flow marker → RULED (a), 2026-07-17, amended same day: a Plan Flow DOES sit on the
  stack. For S7, think stacks [plan, schedule, outline, find] bottom-up — the Plan Flow first,
  Pending, then the steps in reverse execution order. `has_plan` clears exactly when the Plan
  Flow pops after the last step leaves, and PEX abandons a whole plan with one move: mark it
  Invalid (the scratchpad entry notes it, and the steps above resolve or get invalidated in
  turn). Amendment: the Plan Flow is not a bare marker — it HAS slots, mainly a ChecklistSlot
  of the flows it oversees, and its eventual role is a REVIEW pass: when it surfaces as
  Active, its policy reads the session scratchpad to review what the overseen flows did and
  makes final adjustments. Those details are NOT coded this round — TODO comments only.
  Mechanics that follow now: (1) PlanFlow registers in `flow_classes` only — dax {29D}, intent
  Plan, the `steps` ChecklistSlot, no policy yet — while `plan` stays OUT of `FLOW_ONTOLOGY`,
  so detection's 16 candidates are untouched (`_push` reads `flow_classes`, not the ontology);
  (2) until the review policy exists, a pop that surfaces the Plan Flow removes it instead of
  promoting-and-running it, and `has_plan` clears there — with a TODO marking where the review
  pass slots in.

## Todo List

Ordered by dependency — U-numbers reference the open Unresolved Issues above; nothing below a
design task starts before its ruling.

- [ ] **T1 — stop the live crash (no dependencies, most urgent).** Minimal `plan_flows.py` and
  `clarify_flows.py` in `backend/prompts/experts/`, each exporting `PROMPTS = {'Plan': ...}` /
  `{'Clarify': ...}` with placeholder-quality instructions so `get_prompt('Plan'/'Clarify')`
  stops raising KeyError and a Plan/Clarify classification stops failing the turn. Content gets
  refined by T4/T5; landing this first unblocks live runs. Changes: two new prompt files.
- [ ] **T2 — `_candidate_names` fallback rule (no dependencies).** Narrowing that produces
  zero candidates falls back to the full 16-flow list — once plan/clarify leave the ontology
  (T4), the Plan and Clarify intents own no flows at all, and detection under those intents
  runs over everything. Changes: `dialogue_state.py`.
- [x] **T3 — design rulings (Derek).** All settled 2026-07-17 — see Unresolved Issues: list
  detection with abstention, plan/clarify out of the ontology, the tally defaults, the round
  reset, and the Plan Flow marker.
- [ ] **T4 — list detection.** `_flow_detection_schema`'s `flow_name` becomes the `flows` array
  (through the offline linter); the base flow prompt gains exp 1's one-or-many instructions;
  every intent module's exemplars emit `"flows": [...]` (a one-regex sweep:
  `"flow_name": "x"` → `"flows": ["x"]`, 35 spots across the six experts files);
  `_collect_votes` keeps a vote when its flows filter to a non-empty ontology subset — the
  Continue seed and the no-vote fallback become `{'flows': [hint]}` / `{'flows': ['chat']}`;
  `_tally_votes`/`_score_votes` implement the settled defaults; `PLAN_PROMPT`'s real content
  (the multi-flow template). `think` consumes `flows[0]` on single-flow turns — behavior
  otherwise unchanged. NOTE drafted and reverted 2026-07-17 while still planning — the tally
  came out to this; restore on the go:
  ```python
  def _tally_votes(self, votes:list[dict]) -> dict:
      unique: list[str] = []
      for vote in votes:
          for flow in vote['flows']:
              if flow not in unique:
                  unique.append(flow)
      support = {flow: sum(1 for vote in votes if flow in vote['flows']) for flow in unique}
      survivors = [flow for flow in unique if support[flow] * 2 > len(votes)]
      if not survivors:   # no majority anywhere — keep the single best-supported flow
          survivors = [max(unique, key=support.get)]
      claude = next((vote['flows'] for vote in votes if vote['_model'] == 'claude'), [])
      ordered = [flow for flow in claude if flow in survivors]
      ordered += sorted((flow for flow in survivors if flow not in ordered),
                        key=lambda flow: -support[flow])
      dropped = sorted((flow for flow in unique if flow not in survivors),
                       key=lambda flow: -support[flow])
      pred_flows = [{'name': name, 'dax': flow2dax(name),
                     'confidence': support[name] / len(votes)} for name in ordered + dropped]
      rationale = next((vote['reasoning'] for vote in votes
                        if ordered[0] in vote['flows'] and vote.get('reasoning')), '')
      if rationale:
          pred_flows[0]['rationale'] = rationale
      return {'flows': ordered, 'confidence': self._score_votes(votes, ordered[0]),
              'pred_flows': pred_flows}
  ```
  `_score_votes` deltas: membership checks become `best_flow in vote['flows']`, per-vote
  intent spread reads `vote['flows'][0]`, and agreement saturates at the ladder's (3, ·)
  row — with list votes a flow CAN appear in 4-5 of 5 lists after the mediums split on their
  primaries. Additions from the 2026-07-17 rulings: `plan` and `clarify` leave `FLOW_ONTOLOGY`
  (exactly 16 flows; the Intent enum keeps Plan/Clarify, the daxes stay label-only in the eval
  contract); `_collect_votes` KEEPS abstentions — an empty `flows` list is a vote for nothing
  and counts in the majority denominators — and the drafted tally gains the all-abstain case
  (`{'flows': [], 'confidence': 0.0, 'pred_flows': []}`); the abstain option rides the prompt
  instructions ("output an empty list when no flow fits"). Changes: `dialogue_state.py`,
  `for_experts.py`, `experts/*.py`, `nlu.py`, `schemas/ontology.py`.
- [ ] **T5 — the plan path in think.** Multiple flows on a Plan-classified turn: stack the
  Plan Flow first (Pending — the PlanFlow class in `flow_classes` only: dax {29D}, intent
  Plan, a `steps` ChecklistSlot listing the overseen flows, which think fills directly at
  stacking; the future review policy is a TODO comment), then the steps in reverse execution
  order (`active=False`, first step Active); set `has_plan`; no slot fill on the plan pass; validate writes the plan
  entry keyed on the plan pass itself (op='plan' — the existing op discriminator, not the
  standing `has_plan` flag), so mid-plan divergent detections still write announcements. Per
  Derek 2026-07-17: the candidate flows and their tallies are written to the scratchpad
  entry — PEX can stack a dropped flow later or clean up (support ≤ 0.5 marks a dropped
  flow). The stub below predates the marker ruling — add the marker stackon before the step
  loop when restoring:
  ```python
  # think, after the tie-break block:
  predicted = detection.get('pred_flows', [])
  steps = [flow for flow in detection['flows'] if flow in flow_classes]
  if state.pred_intent == 'Plan' and len(steps) > 1:
      state.has_plan = True
      for step in reversed(steps):                    # last step first → first on top
          self.world.flows.stackon(step, transfer=False, active=False)
      top = self.world.flows.get_flow()
      top.status = 'Active'                           # the first step runs; the rest wait
      state = self._write_belief(steps[0], detection['confidence'], predicted, top)
      self.review_scratchpad()
      return self.validate(state, 'plan')
  flow_name = detection['flows'][0]                   # the single-flow path, unchanged below

  # validate's entry block gains, before the op branches:
  if op != 'react' and state.pred_flows:
      entry['tally'] = {flow['name']: flow['confidence'] for flow in state.pred_flows}
  # and the plan branch keys on the pass, listing steps in execution order:
  elif op == 'plan':
      steps = [step.name() for step in reversed(self.world.flows._stack)]
      entry['summary'] = 'plan: stacked ' + ' → '.join(steps)
  ```
  A bare `plan` VOTE with no usable step list keeps `_write_non_policy_belief`'s branch: flag
  `has_plan` and let the agent build the plan. Depends: T4. Changes: `nlu.py`.
- [ ] **T6 — Clarify runtime behavior + S8 rewrite.** `CLARIFY_PROMPT` encourages detecting
  a flow only at EXTREME confidence (abstain otherwise — the empty list); think's empty-
  detection branch stacks nothing, writes the "no confident detection" entry, and the
  zero-agreement confidence trips `needs_clarification` → general ambiguity → PEX asks.
  `_write_non_policy_belief`'s clarify/plan branches retire with the ontology removal. Rewrite
  S8's premise and rows around the TypeSafe classifier and the abstention path. Depends: T4.
  Changes: `nlu.py`, `clarify_flows.py`, this spec.
- [ ] **T7 — the round reset + has_plan lifecycle.** `_run_loop` becomes
  `while round_idx < self.max_rounds:` and a completed flow resets `round_idx = 0` — every
  plan step starts with a fresh budget; no take_turn loop (align the Canonical Turn's
  "back to PEX 2" row in round_3.4_spec.md). `has_plan` clears when the Plan Flow marker
  pops: a pop that surfaces the marker removes it too instead of promoting it (the marker
  never runs), and that removal clears the flag — replacing the landed empty-stack clearing
  in activate_flow. Verify against a live S7 trace once T5 lands. Depends: T5. Changes:
  `pex.py`, both specs.
- [ ] **T8 — verification.** The How-to-verify list below, a live S7 + S8 trace, the unit
  suites, and a small eval subset that includes plan and clarify turns. Depends: all.

## How to verify

1. `get_prompt('Plan')` and `get_prompt('Clarify')` return prompt dicts — no KeyError.
2. The gap query prints `[]` for the experts registry against the Intent enum's live values.
3. Every detection returns `{"reasoning", "flows": [...]}` — one entry on a normal turn; a plan
   turn (S7's "research X, outline it, then schedule it") returns the ordered steps, and think
   stacks them in execution order (find on top) with `has_plan` True and the plan entry listing
   them.
4. A clarify-intent detection runs over the full candidate list and returns a domain flow with low
   confidence; the turn's entry reads "detected clarify; nothing stacked" only when the vote itself
   lands on clarify (or never, under U2's drop-from-candidates ruling).
5. Unit suites stay green; the schema linter accepts the `flows` array schema.

---

## Shipped 2026-07-03 (PR #5): the `propose` slot-fill prompt

Preserved for history — file paths below are the pre-Phoenix Charlie layout. The fix itself carried
forward: `propose` is in today's registry (`backend/prompts/nlu/revise_slots.py`).

Discovered by the 2026-07-03 evaluation-suite run: whenever NLU detected `propose`, `get_prompt`
raised `KeyError: 'propose'` and the turn fell to the crash fallback (`B01.C04 turn 3`, `B03.C01
turns 3-4`). `propose` was the flow the 48→16 refactor added — registered in `FLOW_CATALOG` and
`flow_classes` with its PEX skill and dax, but its NLU slot-fill prompt was never authored. The fix
was one authored `PROPOSE_PROMPT` (instructions / rules / empty `slots` for procedural rendering /
three exemplars covering a named section + direction, a grounded active post with a TODO, and a bare
"fill in the blank") plus the `'propose'` key in the module's `PROMPTS` dict. Decisions of record:
the `## Slots` section renders procedurally from `flow.slots` (cannot drift from the flow; the
heading lint skips procedural flows), and no exemplar references `ver` — grounding sets it, NLU
never predicts it.
