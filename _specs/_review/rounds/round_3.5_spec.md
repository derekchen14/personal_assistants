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

- **`plan` is never stacked.** A Plan detection stackons the decomposed STEPS (domain flows), never a
  `plan` flow — so `plan` needs no flow class and no slot-fill prompt. Its gap is the decomposition
  prompt (this round's centerpiece) plus surviving `get_prompt('Plan')`.
- **`clarify` is never stacked.** `think` routes it through `_write_non_policy_belief`
  (`nlu.py:132-146`): the Ambiguity Handler recognizes a general ambiguity and the scratchpad entry
  says "detected clarify; nothing stacked". So `clarify` needs no flow class and no slot-fill prompt
  either. Its gap is surviving `get_prompt('Clarify')` and a sane candidate list.

So the deliverables are: (1) the plan decomposition prompt + schema + the `think` wiring that stacks
the steps, (2) detection-prompt coverage for the Plan and Clarify intents, (3) a fix to Clarify's
candidate narrowing. Nothing to author for {000} or {39B}.

## 3.5.1 — Plan decomposition from NLU

### Problem

Detection returns ONE flow (`_flow_detection_schema`, `dialogue_state.py:19-31`). Round 3.4's T8
promises "a Plan detection stackons every step in reverse execution order", but no prompt or schema
exists that returns a step list — S7's find → outline → schedule has nowhere to come from. Today
`_write_non_policy_belief('plan')` sets `state.has_plan = True`, stacks nothing, and validate's plan
entry records the empty decomposition (`nlu.py:132-139` carries the TODO).

### Solution Contract

Decomposition is a separate NLU call after detection lands `plan`, not a change to the detection
schema — the detection snippet already tells voters "the plan is decomposed elsewhere; your job is
only the entry flow" (`for_experts.py:368-371`). One LLM call returns the ordered steps; `think`
stackons them in reverse execution order (last step first, so the first step ends up on top); each
step is a real domain flow that the existing per-flow machinery fills and runs. No slot fill at
decompose time — S7's NLU 3 row is "skipped, since state.has_plan": each step's policy fills its own
slots with `fill_slots_by_label` when it runs, and step inputs usually depend on earlier steps'
outputs anyway. Validate's plan
entry then lists the stacked steps exactly as T9 already writes it (summary only, no `new_flow` key,
so PEX's hook 3/5 reads skip it); PEX's hook-point-1 read sees the steps on the stack directly.

Proposed new surface (needs Derek's sign-off before building — no new concepts without approval):

- `DialogueState.decompose_plan(engineer, context, user_text)` — sits beside `classify_intent` /
  `detect_flows` / `fill_slots` as the fourth prediction method on the component.
- `_plan_decomposition_schema` (module-level in `dialogue_state.py`, beside
  `_flow_detection_schema`): `{reasoning, steps: [{flow_name (enum of stackable flows), goal}]}`,
  2-5 steps. `goal` is one sentence of what the step should accomplish — it seeds the step's
  slot-fill later, it is NOT a slot write. Run the shape through the offline schema linter
  (`test_nlu_schemas.py`) — nested arrays of enum-bearing objects are near the known-rejected zone.
- `PLAN_PROMPT` in a new `backend/prompts/experts/plan_flows.py`, exporting
  `PROMPTS = {'Plan': PLAN_PROMPT}` like every other intent module — which also closes the
  `get_prompt('Plan')` KeyError for free. The prompt's `instructions`/`rules`/`examples` teach
  decomposition: steps are stackable domain flows only (never `plan`, `clarify`, or `chat`), 2-5
  steps, forward through the pipeline, one S7-style exemplar (find → outline → schedule) and one
  two-step exemplar.

### Implementation sketch

```python
# nlu.py — _write_non_policy_belief's plan branch becomes:
if flow_name == 'plan':
    state.has_plan = True
    steps = state.decompose_plan(self.engineer, context, user_text)   # [{flow_name, goal}, ...]
    for step in reversed(steps):                                       # last step first → first on top
        self.world.flows.stackon(step['flow_name'], transfer=False)
```

The per-step `goal` rides the scratchpad plan entry (validate already writes the step list; extend
the summary line, no new entry key), so PEX and later steps can read what each step is for.

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
| NLU 2 | `detect_flows` | the vote converges on `plan`, ideally detects find {001}, outline {002}, and schedule {4AC} |
| NLU module | `think` | multi-step confirmed: sets `state.has_plan = True` and stackons every step in reverse execution order — `stackon('schedule', active=false)`, `stackon('outline', active=false)`, then `stackon('find')` on top |
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
This is a brainstorm {39D} flow, but the intent classifier can't reach it since the Draft intent really only lines up with outline {002} at the basic-flow mapping. Thus, classify_intent falls back to Clarify {09F}.
NLU takes on the responsibility for choosing the correct flow.

| phase | method | what happens |
|---|---|---|
| Assistant | `take_turn` | empty stack |
| NLU 1 | `classify_intent` | intent: Clarify — no real signal |
| PEX module | `prepare` | same |
| Assistant | run NLU | same |
| NLU module | `check` | clears any prior ambiguity; picks the Clarify detection snippet |
| PEX module | `prepare` | **wait** — hook point 1: Clarify blocks here until NLU settles |
| PEX 2 | - | skipped, because Clarify is not an actionable prediction |
| NLU 2 | `detect_flows` | the ensemble detects `brainstorm` {39D} |
| NLU module | `think` | since Clarify carried no flow, there is no possible conflict, so NLU directly places {39D} on the stack |
| NLU 3 | fill_slots() | NLU predicts slots for brainstorm and runs `fill_slot_values()` |
| NLU module | `validate()` | makes sure slot-values are valid, writes the detected flow as an entry in the scratchpad |
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

Proposed, pending approval: `DialogueState.decompose_plan` + `_plan_decomposition_schema`, and two
new intent modules in the existing experts registry (`plan_flows.py`, `clarify_flows.py` — new files
in an existing pattern, not a new pattern). Everything else reuses the current registries.

## How to verify

1. `get_prompt('Plan')` and `get_prompt('Clarify')` return prompt dicts — no KeyError.
2. The gap query prints `[]` for the experts registry against the Intent enum's live values.
3. A plan turn (S7's "research X, outline it, then schedule it") stacks three steps in execution
   order (find on top) and validate's entry lists them; `has_plan` is True.
4. A clarify-intent detection runs over the full candidate list and returns a domain flow with low
   confidence; the turn's entry reads "detected clarify; nothing stacked" only when the vote itself
   lands on clarify.
5. Unit suites stay green; the schema linter accepts `_plan_decomposition_schema`.

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
