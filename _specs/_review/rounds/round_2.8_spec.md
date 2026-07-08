# Round 2.8 — One flow stack

Status: PM spec, implements the design direction approved by the user 2026-07-04.
Base commit: 0f27939 (all line numbers below refer to it).

## The problem

Two copies of the flow stack exist today. The FlowStack component (`world.flow_stack`, shared as
`pex.flow_stack` and `policy.flow_stack`) holds real flow objects and is what policies, NLU, and
`activate_flow` read. `DialogueState.flow_stack` holds a list of dicts saved in state.json; every
`write_state` stack op rebuilds a THROWAWAY FlowStack from those dicts, mutates it, and serializes
back (dialogue_state.py:207-221), while pex.py:618-623 repeats each op on the component to keep
the copies in step. This round removes the second copy: **the FlowStack component is the only
flow stack**. `DialogueState.flow_stack` becomes a saved copy — written from
`flow_stack.to_list()` before each save, read once at session load.

After this round, one stack op = one mutation of one object. No repeated writes anywhere.

## 2.8.1 Where the write_state ops live (the resolved question)

**Resolution: the ops stay in `DialogueState.write_state`, which gains a `stack` parameter —
callers pass the live FlowStack component.** Signature:
`write_state(self, path, op, stack=None, **kwargs)`.

Justification: the alternative (moving stackon/fallback/pop_completed/update_flow into
`PEX._dispatch_write_state`) splits the op vocabulary across two classes, forces the grounding
validation (`_check_grounding`, which reads `self.grounding`) out of the class that owns the
grounding data, and leaves `BasePolicy.complete_flow` — which has a state, a state-file path, and
a flow stack but no PEX — without a surface to call. Passing the stack in keeps exactly the
contracts we have today: `write_state` stays the one method that mutates session state and saves
state.json, the op vocabulary stays in one place, tests keep calling `state.write_state(...)`
directly, and PEX's dispatch stays a thin wire. It is the shape with the fewest concepts: no new
class, no new method, one new parameter.

`stack=None` is a real default, not a guard: op `update` touches no flows and legitimately has no
stack. Stack ops called without a stack crash on `None.stackon(...)` — loud, as required.

## 2.8.2 dialogue_state.py — write_state mutates the live stack

**Edit `write_state` (lines 160-178).** New body:

```python
def write_state(self, path, op, stack=None, **kwargs) -> dict:
    """The write_state tool surface — the ONLY writer of state.json. Ops:
    'update'        mutate user-belief / grounding / flag fields (kwargs = fields),
    'update_flow'   mutate the top flow of the live stack (slots= / stage= / status=;
                    completion is grounding-validated),
    'stackon'       push flow_name= with FlowStack semantics,
    'fallback'      replace the top flow with flow_name=,
    'pop_completed' remove Completed/Invalid flows, activating the next Pending one.
    `stack` is the FlowStack component — the one flow stack. Stack ops mutate it directly;
    self.flow_stack is only a saved copy, refreshed from stack.to_list() before the save."""
    if op == 'update':
        self._apply_update(kwargs)
    elif op == 'update_flow':
        self._update_flow(stack, kwargs)
    elif op == 'stackon':
        stack.stackon(kwargs['flow_name'])
    elif op == 'fallback':
        stack.fallback(kwargs['flow_name'])
    elif op == 'pop_completed':
        stack.pop_completed()
    else:
        raise ValueError(f'Unknown write_state op: {op!r}')
    if stack is not None:
        self.flow_stack = stack.to_list()
    self.save(path)
    return self.serialize_session()
```

**Edit `_update_flow` (lines 194-205)** — takes the live stack, validates status BEFORE any
mutation so a rejected write leaves the live flow untouched:

```python
def _update_flow(self, stack, fields:dict):
    flow = stack.peek()
    if 'status' in fields:  # validate first — a rejected write must not mutate the live flow
        self._check_grounding(flow, fields['status'])
    if 'slots' in fields:
        flow.fill_slot_values(normalize_slot_values(flow, fields['slots']))
        flow.is_filled()
    if 'stage' in fields:
        flow.stage = fields['stage']
    if 'status' in fields:
        flow.status = fields['status']
```

**Delete lines 207-221** — `_run_stack_op` and the private helper below it that rebuilt a
throwaway FlowStack from the saved dicts. Both are gone; nothing replaces them.

**Line 4 import**: `FlowStack` is now unused here — the import becomes
`from backend.components.flow_stack import flow_classes`.

**Line 74**: add the copy comment:
`self.flow_stack: list[dict] = []  # saved copy of the FlowStack component (see write_state)`.

**`rehydrate_flow` (lines 35-47) survives unchanged** — its docstring's last sentence gains:
"Used at session load (World.open_session) and in serialization round-trip tests."

## 2.8.3 pex.py — single write in _dispatch_write_state; delete the repeated ops

**Edit `_dispatch_write_state` (lines 600-631).** The unknown-slot precheck reads the live top
directly; the write passes the live stack; the repeat block (lines 613-623) and its comment are
deleted:

```python
def _dispatch_write_state(self, params:dict) -> dict:
    state = self.world.current_state()
    kwargs = dict(params.get('fields', {}))
    if 'flow_name' in params:
        kwargs['flow_name'] = params['flow_name']
    if params['op'] == 'update_flow' and 'slots' in kwargs:
        top = self.flow_stack.peek()
        unknown = [name for name in kwargs['slots'] if name not in top.slots]
        if unknown:  # corrective error — fill_slot_values would drop these silently
            return {'_success': False, '_error': 'invalid_input',
                    '_message': f'flow {top.name()!r} has no slot(s) {unknown}; '
                                f'valid slots: {list(top.slots)}'}
    document = state.write_state(self.world.state_file(), params['op'],
                                 stack=self.flow_stack, **kwargs)
    if params['op'] == 'stackon' and params.get('active'):
        # Single-call stack-on (the user 2026-07-03): stackon handed over matching slots; fold
        # in belief's pred_slots, then run the policy — no update_flow / activate_flow calls.
        self._check_nlu(wait=False)
        if self._nlu_thread is None:  # fold only a landed detection — never a mid-write belief
            self._apply_belief_slots(state, params['flow_name'])
        return self.activate_flow({'flow_name': params['flow_name']})
    return {'_success': True, 'state': document}
```

PEX always passes `stack=self.flow_stack`, including op `update` — the refresh of the saved copy
is then a harmless no-op-equivalent and the call site stays uniform.

**Line 7**: delete `from backend.components.dialogue_state import rehydrate_flow` — PEX no longer
rebuilds flows from saved dicts anywhere.

## 2.8.4 pex.py — _apply_belief_slots and inject_belief_state write once

**Edit `_apply_belief_slots` (lines 633-642)** — read the live top, write once:

```python
def _apply_belief_slots(self, state, flow_name:str):
    """Fold belief's `pred_slots` into the just-stacked flow when NLU's detection is this
    same flow — the code-side replacement for the recipe's update_flow step."""
    if not state.pred_flows or state.pred_flows[0]['flow_name'] != flow_name:
        return
    top = self.flow_stack.peek()
    slots = {name: value for name, value in state.pred_slots.items()
             if name in top.slots and value}
    if slots:
        state.write_state(self.world.state_file(), 'update_flow',
                          stack=self.flow_stack, slots=slots)
```

**Edit `inject_belief_state` (lines 644-672)** — the forced-fallback path becomes one write.
Line 666 gains `stack=self.flow_stack`; line 668 (`self.flow_stack.fallback(...)` and its
comment) is deleted:

```python
        old_name = active.name()
        state.write_state(self.world.state_file(), 'fallback',
                          stack=self.flow_stack, flow_name=top['flow_name'])
        self._apply_belief_slots(state, top['flow_name'])
        note += (...)   # unchanged
```

## 2.8.5 Delete prestack (pex.py, agent.py, for_orchestrator.py)

**Delete `PEX.prestack` (pex.py:674-688) entirely.** The orchestrator receives the belief note at
its first hook and the single-call stackon recipe covers the awaited-think turns. Accepted cost:
one extra tool round on those turns.

**agent.py:79-81** — the awaited-think branch loses the call:

```python
        else:                            # utterance, no active entity: think, awaited
            self.nlu.understand(op='think', user_text=text, payload=payload)
```

**for_orchestrator.py:97-99** — the "Stacking and dispatching flows" bullet loses the PRE-STACKED
claim. Replace lines 97-99 (through "ONE call does everything: ") with:

```python
    '**Stacking and dispatching flows.** To stack on and run a flow, ONE call does everything: '
```

The rest of the bullet (lines 100-103) is unchanged.

## 2.8.6 pex.py — collapse _stack_flow into activate_flow

With one stack the live flow is always current: there is no state-file entry to layer on and no
lazy rebuild. **Delete `_stack_flow` (pex.py:735-763)** and replace its call site
(`flow = self._stack_flow(state, params['flow_name'])`, line 698) with two inline lines:

```python
        name = params['flow_name']
        flow = self.flow_stack.find_by_name(name) or self.flow_stack.stackon(name)
        flow.status = 'Active'  # pushes wait as Pending; running the policy promotes
```

`find_by_name` already skips Completed/Invalid entries (stack.py:61-68), so a finished run of the
same flow is never re-targeted — the grounding-switch protection is preserved without the extra
branch. `activate_flow`'s copy refresh at line 723 (`state.flow_stack = self.flow_stack.to_list()`)
stays: policies mutate live flow status during `execute`, and the tool result's state must show it.

## 2.8.7 Saved-copy refresh at the two remaining serialization points

The saved copy must be current whenever the session document is serialized or saved. `write_state`
now refreshes internally (2.8.2) and `activate_flow` keeps its refresh (2.8.6). Two more points:

**`PEX.read_state` (pex.py:596-598)** — the orchestrator's ground-truth read must show the live
stack even after a policy-internal stackon/fallback (draft.py:167,204; revise.py:103,107,211):

```python
    def read_state(self, params:dict) -> dict:
        self._check_nlu()
        state = self.world.current_state()
        state.flow_stack = self.flow_stack.to_list()  # saved copy tracks the one stack
        return {'_success': True, 'state': state.read_state()}
```

**Agent end-of-turn POST-HOOK (agent.py:108-117)** — insert one line before the save at line 114:

```python
        state.flow_stack = self.pex.flow_stack.to_list()  # refresh the saved copy, then save
        state.save(self.world.state_file())
```

## 2.8.8 world.py — session load rebuilds the one stack

`rehydrate_flow` survives ONLY here. **Edit `open_session` (world.py:56-59)**:

```python
        state_file = session_path / 'state.json'
        if state_file.exists():
            state = self.insert_state(DialogueState.load(state_file))
            self.flow_stack._stack = [rehydrate_flow(entry) for entry in state.flow_stack]
            return state
        return None
```

Add `from backend.components.dialogue_state import DialogueState, rehydrate_flow` (extends the
existing line 4 import). Direct `_stack` assignment matches the existing `reset()` usage
(world.py:73); no new FlowStack method.

## 2.8.9 base.py — complete_flow checks and writes through the one stack

**Edit `complete_flow` (base.py:224-237).** The pre-write copy (line 230) and the post-write
status repeat (line 235) are deleted; the top-of-stack check reads the live stack:

```python
    def complete_flow(self, flow, state, summary:str, metadata:dict|None=None) -> dict|None:
        """The single call a policy makes at the moment its flow finishes. The status change goes
        through write_state op='update_flow' (so the grounding validation fires and state.json is
        rewritten) and the completion record {flow, summary, metadata} is appended to the session
        scratchpad; activate_flow collects it via pop_completion and returns it as the tool
        result. Call it before stacking any follow-up flow — the completing flow must be top of
        stack."""
        if self.flow_stack.peek().flow_id != flow.flow_id:
            raise ValueError(f'complete_flow: {flow.name()!r} is not top of stack — finish or '
                             f'pop the flows above it first')
        state.write_state(self._state_file(), 'update_flow', stack=self.flow_stack,
                          status='Completed')
        self._completion = self.scratchpad.write_completion(flow.name(), summary,
                                                            metadata=metadata)
        return self._completion
```

`write_state` sets `flow.status` on the same live object the policy holds, so the old mirror line
is dead.

## 2.8.10 Comment and word sweep in touched files

The wipe-risk bug class no longer exists; its warnings go with it. Also sweep the banned words in
the files this round edits (only the listed lines — no drive-by rewrites elsewhere):

- pex.py:613-617 — deleted with the repeat block (2.8.3).
- pex.py:668, 686 — deleted with their code (2.8.4, 2.8.5).
- pex.py:429 — `_guarded_call` docstring: drop the adverb before "unpredictable input", leaving
  "LLM output is unpredictable input."
- dialogue_state.py:15 — `normalize_slot_values` docstring: drop the same adverb, leaving
  "(tool arguments are unpredictable input)".
- base.py:12 — replace the last word of "an interception ..." with "hook"; base.py:15 — replace
  the parenthetical at line end with "(integration point)".
- base.py:106 — the comment's third word (before "heading") becomes "marker", so it reads
  "Strip the hidden-section marker heading ...".
- world.py:50 — open_session docstring: replace its second word so the sentence reads "reloads
  its state.json as the current state and rebuilds the flow stack from it".

## 2.8.11 Test changes (utils/evaluation_suite/_tests)

All in-place edits; run from the assistants/Hugo cwd.

### pex_unit_tests.py

1. `test_write_state_stacks_and_saves` (96-102): add one assert that the one stack got the push —
   `assert mock_agent.pex.flow_stack.peek().flow_type == 'outline'`.
2. `test_write_state_pop_completed_mirrors_live_stack` (104-117): rename to
   `test_write_state_pop_completed_pops_the_stack`. Delete the manual copy lines (112-113) and the
   old docstring; new body:

   ```python
   def test_write_state_pop_completed_pops_the_stack(self, sessions_dir, mock_agent):
       """pop_completed acts on the one flow stack and the saved document shows it."""
       mock_agent.world.open_session('wire-test')
       pex = mock_agent.pex
       pex.flow_stack.stackon('chat').status = 'Completed'
       result = pex._dispatch_tool('write_state', {'op': 'pop_completed'})
       assert result['_success'] is True
       assert result['state']['flow_stack'] == []
       assert pex.flow_stack.to_list() == []
   ```
3. The test at 194-212 (its old name claims the flow "lives only in the state file", which is no
   longer a real situation): rename to `test_write_state_slots_reach_the_policy_run`. The two
   direct `state.write_state` calls (197-199) gain `stack=pex.flow_stack`; the assert at 209 flips
   to `assert pex.flow_stack.find_by_name('outline') is not None`; docstring: "slots written via
   write_state land on the live flow that activate_flow runs." Everything else stays.
4. Hypothesis machine (1454-1600): one stack now, so every rule issues each op ONCE through
   `write_state(..., stack=self.stack, ...)` — the paired direct-mutation lines are deleted.
   - Header comment 1454-1463: rewrite to "Drives the FlowStack component through random-but-valid
     write_state op sequences. Catches FSM-discipline regressions (depth bounds, status
     transitions, pop_completed semantics, get_flow filtering) and serialization round-trip loss
     of the saved copy in state.json."
   - `stackon` rule (1500-1511): drop `self.stack.stackon(name)`; call
     `self.state.write_state(self.state_file, 'stackon', stack=self.stack, flow_name=name)`;
     capture `top_before` first and set `new_flow = self.stack._stack[-1]` after; keep the same
     asserts.
   - `fallback` rule (1513-1528): drop `self.stack.fallback(name)`; write_state with
     `stack=self.stack`; keep the asserts (they read `self.stack`).
   - `fill_source` rule (1530-1539): drop the direct `fill_slot_values`/`is_filled` pair;
     write_state `update_flow` with `stack=self.stack` only.
   - `complete_top` (1541-1545) / `mark_pending` (1547-1553): drop the direct status assignment;
     write_state `update_flow` with `stack=self.stack` (keep the `if self.stack._stack:` guard).
   - `pop_completed` rule (1555-1565): drop `self.stack.pop_completed()`; write_state with
     `stack=self.stack`; keep the after-checks.
   - Invariant `file_backed_stack_matches_in_memory` (1589-1597): body unchanged — it now checks
     saved copy == live stack == saved file. Rename to `saved_copy_matches_the_stack` and drop the
     "Phase-1 equivalence gate" comment in favor of "the saved copy and file track the one stack".
   - `__init__` comment 1488-1489 ("File-backed twin...") → "The DialogueState carries the saved
     copy of this stack in its flow_stack block."
5. Header comment 1739 → `# Single-call stackon (write_state op=stackon active=true)`.
   `TestSingleCallStackon` docstring (1744-1746) loses the prestack sentence. Line 1765
   `top = rehydrate_flow(state.flow_stack[-1])` → `top = pex.flow_stack.peek()`.
   **Delete** `test_prestack_stacks_confident_detection` (1778-1786) and
   `test_prestack_skips_plan_converse_and_ambiguity` (1787-1797).
6. `TestBeliefInjection.test_intent_differs_forces_fallback` (1872-1884): replace lines 1876-1878
   with a single stack-on through the dispatch, then promote:

   ```python
       pex._dispatch_tool('write_state', {'op': 'stackon', 'flow_name': 'outline'})
       live = pex.flow_stack.peek()
       live.status = 'Active'   # stackon lands Pending; model a mid-turn running flow
   ```
   All asserts (1881-1884) stay. Same replacement in
   `test_flow_differs_same_intent_no_forcing` (1890-1892).
7. `TestPlanLifecycle` (1899-1929): body unchanged — it is the regression proof. Docstring →
   "A stacked multi-flow plan survives completions: there is exactly one flow stack, so a
   completion can no longer wipe the Pending flows of a plan (code review 2026-07-04,
   Critical 1)."

### nlu_unit_tests.py

`TestWriteStateOps` (498-595): each test that issues a stack op or update_flow creates
`stack = FlowStack({}, flow_classes=flow_classes)` and passes `stack=stack` on those calls
(`test_read_state_returns_document`, `test_update_op_mutates_and_saves`, and the two raises in
`test_unknown_op_and_unknown_fields_raise` need no stack). Specifics:

- `test_op_sequence_matches_in_memory_flowstack` (526-552): the two-implementation comparison is
  gone. Rename to `test_op_sequence_keeps_saved_copy_current`; drive the SAME op sequence through
  `write_state(path, op, stack=stack, ...)` only (delete every paired direct-stack line: 534,
  537-540, 542, 544, 547, 549), then assert:

  ```python
      assert state.flow_stack == stack.to_list()
      assert DialogueState.load(path).flow_stack == state.flow_stack
  ```
- `test_grounding_validation_raises_on_ungrounded_completion` (554-561): add `stack=stack`; the
  asserts at 560-561 hold — validation fires before any mutation, so the live flow, the saved
  copy, and the file all still show Pending.
- `test_grounding_validation_passes_once_post_is_set` (563-569),
  `test_update_flow_normalizes_llm_shaped_slot_values` (571-583),
  `test_grounding_validation_skips_topic_grounded_flows` (585-595): add `stack=stack` to each
  stack op / update_flow call; assertions unchanged.
- Class docstring (499): "write_state is the only writer of state.json; stack ops mutate the
  FlowStack passed in as `stack` and refresh the saved copy."

### mem_unit_tests.py

Add one session-load test next to the existing messages session-load test at lines 486-492,
using the imports already present at lines 499-500 plus `flow_classes` and `DialogueState` (add
to those import lines if missing):

```python
def test_open_session_rebuilds_flow_stack(self, sessions_dir, minimal_config):
    stack = FlowStack({}, flow_classes=flow_classes)
    state = DialogueState(intent='Draft', dax=None, turn_count=1)
    state.conversation_id = 'convo-43'
    (sessions_dir / 'convo-43').mkdir(parents=True)
    state.write_state(sessions_dir / 'convo-43' / 'state.json', 'stackon',
                      stack=stack, flow_name='outline')
    world = World(minimal_config)
    world.open_session('convo-43')
    top = world.flow_stack.peek()
    assert top.flow_type == 'outline' and top.status == 'Pending'
    assert top.flow_id == stack.peek().flow_id
```

(Place it inside the class that owns the messages test; match its fixture usage.)

### model_tests.py / conftest.py

No changes — verified: neither references prestack, the deleted helpers, or direct stack-op
write_state calls.

## 2.8.12 Acceptance criteria

1. Free suite green with ZERO skips from the assistants/Hugo cwd: `pex_unit_tests.py`,
   `nlu_unit_tests.py`, `mem_unit_tests.py`, `model_tests.py`. Builders run NO live evals — the
   orchestrator runs the live 8-scenario gate after shipping.
2. Greps return nothing under `backend/` and `utils/`:
   `grep -rn "prestack\|_run_stack_op\|_stack_flow\|PRE-STACKED" backend utils`.
3. `rehydrate_flow` is referenced in `backend/` only by its definition (dialogue_state.py) and
   `world.py` (session load). Tests may still use it for serialization round-trips
   (pex_unit_tests.py:1419-1449).
4. Exactly one flow stack: no code path constructs a FlowStack outside `World.__init__` and tests.
5. `DialogueState.write_state` remains the only production writer of state.json besides the Agent
   end-of-turn save (agent.py:114), and both are immediately preceded by (or internally perform) a
   `flow_stack.to_list()` refresh of the saved copy.
6. NET DELETION: the diff removes more lines than it adds. Expected wins: dialogue_state.py:207-221
   (-15), pex.py mirror block + prestack + _stack_flow (-60 or so), base.py (-2), test prestack
   block (-20), against small additions (stack= threading, world.py +2, agent.py +1, pex
   read_state +1, one new mem test).
7. Banned-word sweep of 2.8.10 applied; no new occurrences introduced anywhere in the diff.

## Builder notes

- Do not touch policies' own mid-run `flow_stack.stackon/fallback` calls (draft.py, revise.py) —
  they already act on the one stack and are covered by the read_state / activate_flow refreshes.
- `nlu_unit_tests.py:19` imports `rehydrate_flow` without using it; `mem_unit_tests.py:499`
  likewise. Pre-existing — leave them unless your edits make the file's linter fail.
- The two-stack slot-layering rationale comments (old pex.py:735-763 docstring) must not be
  copied anywhere — with one stack the live flow is always current.
- pex.py:146-147 and other comments naming Agent internals stay as they are.
