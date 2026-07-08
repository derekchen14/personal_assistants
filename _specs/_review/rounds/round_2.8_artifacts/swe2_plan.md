# Round 5.2 — SWE2 implementation plan

Spec: `_specs/agents/plans/round_5.2_spec.md` (authoritative). Base: 0f27939. All paths below are
relative to `assistants/Hugo/`. I verified every file and line reference in the spec against the
live source at tip; every reference is correct. The working tree only has unrelated eval-dataset
edits, so the checked-out source matches 0f27939 for every file this round touches.

Plan only — no edits applied.

## Edit order

Apply as one diff; the tree does not pass tests between steps 1 and 8 (step 1 changes the
write_state contract that pex.py and the tests still assume until their own steps land). Order
below is dependency order for review, not a run-the-suite-between-steps sequence.

### 1. backend/components/dialogue_state.py

- Line 4, before: `from backend.components.flow_stack import FlowStack, flow_classes`
  after: `from backend.components.flow_stack import flow_classes`
- Line 15: drop the adverb, leaving `(tool arguments are unpredictable input).` (spec 5.2.10).
- Lines 35-47 `rehydrate_flow`: body unchanged; append to the docstring:
  "Used at session load (World.open_session) and in serialization round-trip tests."
- Line 74, before: `self.flow_stack: list[dict] = []`
  after: `self.flow_stack: list[dict] = []  # saved copy of the FlowStack component (see write_state)`
- Lines 160-178 `write_state`: replace with the spec 5.2.2 body verbatim — signature
  `write_state(self, path, op, stack=None, **kwargs) -> dict`; ops dispatch to `_apply_update` /
  `_update_flow(stack, kwargs)` / `stack.stackon` / `stack.fallback` / `stack.pop_completed`;
  then `if stack is not None: self.flow_stack = stack.to_list()`; then `self.save(path)`.
- Lines 194-205 `_update_flow`: replace with the spec 5.2.2 body — `flow = stack.peek()`, grounding
  validation runs FIRST (before any slot/stage/status mutation), then slots, stage, status.
- Lines 207-221: delete `_run_stack_op` and the private stack-rebuild helper below it. Nothing
  replaces them.

### 2. backend/modules/policies/base.py

- Lines 224-237 `complete_flow`: replace with the spec 5.2.9 body — top-of-stack check becomes
  `if self.flow_stack.peek().flow_id != flow.flow_id: raise ValueError(...)`; the pre-write copy
  (old line 230) and the post-write status repeat (old line 235) are deleted; the write becomes
  `state.write_state(self._state_file(), 'update_flow', stack=self.flow_stack, status='Completed')`.
  Docstring per spec (drops "top of the stack" phrasing changes only as spec'd).
- Line 12: last word of the "interception ..." phrase becomes "hook".
- Line 15: the line-end parenthetical becomes "(integration point)".
- Line 106: the coined word before "heading" becomes "marker", so the comment reads
  "Strip the hidden-section marker heading so prose-only posts display cleanly without the marker".

### 3. backend/modules/pex.py

- Line 7: delete `from backend.components.dialogue_state import rehydrate_flow`.
- Line 429 `_guarded_call` docstring: drop the adverb, leaving "LLM output is unpredictable input."
- Lines 596-598 `read_state`: replace with the spec 5.2.7 body — insert
  `state.flow_stack = self.flow_stack.to_list()  # saved copy tracks the one stack` before the
  return; bind `state = self.world.current_state()` on its own line.
- Lines 600-631 `_dispatch_write_state`: replace with the spec 5.2.3 body — the unknown-slot
  precheck reads `top = self.flow_stack.peek()`; the write passes `stack=self.flow_stack`;
  the repeat block and its comment (613-623) are gone; the `active` branch is unchanged.
- Lines 633-642 `_apply_belief_slots`: replace with the spec 5.2.4 body —
  `top = self.flow_stack.peek()`; the write gains `stack=self.flow_stack`.
- Lines 644-672 `inject_belief_state`: only the forced-fallback branch changes. Line 666 gains
  `stack=self.flow_stack` (wraps to two lines per spec); line 668 (the second `fallback` call and
  its comment) is deleted. `old_name`, `_apply_belief_slots`, and the `note +=` stay.
- Lines 674-688: delete `prestack` entirely.
- Line 698 in `activate_flow`, before: `flow = self._stack_flow(state, params['flow_name'])`
  after (spec 5.2.6):
  ```python
  name = params['flow_name']
  flow = self.flow_stack.find_by_name(name) or self.flow_stack.stackon(name)
  flow.status = 'Active'  # pushes wait as Pending; running the policy promotes
  ```
  Verified: `find_by_name` (stack.py:61-68) skips Completed/Invalid, and `stackon`'s
  same-type dedupe (stack.py:25) also skips terminal tops, so a finished run is never re-targeted.
  The copy refresh at line 723 stays.
- Lines 735-763: delete `_stack_flow` entirely. Its docstring's two-stack slot-layering rationale
  is not copied anywhere (builder note).

### 4. backend/agent.py

- Lines 79-81: the awaited-think branch keeps the `understand` call and loses line 81
  (`self.pex.prestack(state)` and its comment).
- Line 114 area (POST-HOOK, lines 108-117): insert one line before the save:
  `state.flow_stack = self.pex.flow_stack.to_list()  # refresh the saved copy, then save`

### 5. backend/components/world.py

- Line 4, after: `from backend.components.dialogue_state import DialogueState, rehydrate_flow`
- Lines 56-59 `open_session`: replace per spec 5.2.8 — bind the loaded state, then
  `self.flow_stack._stack = [rehydrate_flow(entry) for entry in state.flow_stack]`, then return it.
  Line 55 (`attach_messages`) stays above, untouched.
- Line 50 docstring: the second sentence becomes "An existing dir reloads its state.json as the
  current state and rebuilds the flow stack from it; a fresh id defers dir creation to
  session_dir() (lazy, first turn)." (see risk R2 on the dropped messages.jsonl mention).

### 6. backend/prompts/for_orchestrator.py

- Lines 97-99: replace through "ONE call does everything: " with
  `'**Stacking and dispatching flows.** To stack on and run a flow, ONE call does everything: '`
  Lines 100-103 unchanged.

### 7. backend/components/flow_stack/stack.py — NOT in the spec's edit list (see risk R1)

- Line 109 comment names the deleted `_stack_flow`; acceptance grep 2 fails without an edit.
  Minimal fix, before: `# (activate_flow via _stack_flow, or pop_completed surfacing the next top).`
  after: `# (activate_flow, or pop_completed surfacing the next top).`

### 8. utils/evaluation_suite/_tests/pex_unit_tests.py (spec 5.2.11, all verified in place)

1. Lines 96-102: add `assert mock_agent.pex.flow_stack.peek().flow_type == 'outline'` at the end.
2. Lines 104-117: replace with `test_write_state_pop_completed_pops_the_stack` exactly as spec'd
   (drops the manual copy lines 112-113 and the old docstring).
3. Lines 194-212: rename to `test_write_state_slots_reach_the_policy_run`; add
   `stack=pex.flow_stack` to the two write_state calls (197-199); line 209 assert flips to
   `assert pex.flow_stack.find_by_name('outline') is not None`; new docstring per spec.
4. Hypothesis machine 1454-1600:
   - 1454-1463 header: rewrite per spec (one stack, FSM-discipline + saved-copy round-trip).
   - 1488-1489 `__init__` comment → "The DialogueState carries the saved copy of this stack in
     its flow_stack block."
   - `stackon` rule 1500-1511: capture `top_before` first, single
     `self.state.write_state(self.state_file, 'stackon', stack=self.stack, flow_name=name)`,
     then `new_flow = self.stack._stack[-1]`; delete the direct `self.stack.stackon(name)`;
     asserts unchanged.
   - `fallback` 1513-1528: delete line 1524; write_state gains `stack=self.stack`; asserts stay.
   - `fill_source` 1530-1539: delete lines 1535-1537 (direct top fill pair); keep the guard;
     write_state gains `stack=self.stack`.
   - `complete_top` 1541-1545 / `mark_pending` 1547-1553: delete the direct status line; keep the
     `if self.stack._stack:` guard; write_state gains `stack=self.stack`.
   - `pop_completed` 1555-1565: delete line 1558; write_state gains `stack=self.stack`; keep the
     after-checks (also keep the now-unused-looking `before_completed` capture only if still read —
     it is not read today; it stays as-is since the spec says keep the after-checks and delete only
     the direct call. See risk R6.)
   - Invariant 1589-1597: rename to `saved_copy_matches_the_stack`; comment → "the saved copy and
     file track the one stack"; body unchanged.
5. Line 1739 header → `# Single-call stackon (write_state op=stackon active=true)`.
   Docstring 1744-1746 loses its second clause (the deleted code path's sentence).
   Line 1765 → `top = pex.flow_stack.peek()`. Delete tests at 1778-1786 and 1787-1797; keep two
   blank lines before `class TestCheckNlu` (today line 1797 runs straight into 1798).
6. Lines 1876-1878 and 1890-1892, each replaced with:
   ```python
   pex._dispatch_tool('write_state', {'op': 'stackon', 'flow_name': 'outline'})
   live = pex.flow_stack.peek()
   live.status = 'Active'   # stackon lands Pending; model a mid-turn running flow
   ```
   All asserts (1881-1884, 1893-1896) stay.
7. TestPlanLifecycle 1899-1929: docstring only, per spec.

### 9. utils/evaluation_suite/_tests/nlu_unit_tests.py

- Class docstring 499 → "write_state is the only writer of state.json; stack ops mutate the
  FlowStack passed in as `stack` and refresh the saved copy."
- 526-552: rename to `test_op_sequence_keeps_saved_copy_current`; delete lines 534, 537-540, 542,
  544, 547, 549; every remaining stack op / update_flow call gains `stack=stack`; final asserts:
  `assert state.flow_stack == stack.to_list()` and
  `assert DialogueState.load(path).flow_stack == state.flow_stack`
  (note: exact equality — flow_ids now round-trip identically, `_without_ids` no longer needed here).
- 554-561, 563-569, 571-583, 585-595: each test creates
  `stack = FlowStack({}, flow_classes=flow_classes)` and passes `stack=stack` on stack ops and
  update_flow calls; assertions unchanged. `test_read_state_returns_document`,
  `test_update_op_mutates_and_saves`, and the two raises in
  `test_unknown_op_and_unknown_fields_raise` need no stack.
- Imports: `FlowStack` and `flow_classes` are already imported (used at 531); no import edits.

### 10. utils/evaluation_suite/_tests/mem_unit_tests.py

- Line 500 gains `flow_classes`: `from backend.components.flow_stack import FlowStack, flow_classes`.
  `DialogueState` is already imported at line 274; `World`, `sessions_dir`, `minimal_config` are in
  scope (conftest patches `_SESSIONS_DIR`, verified at conftest.py:121-125).
- Add `test_open_session_rebuilds_flow_stack` inside `TestMessageList` (class at 424), directly
  after the existing messages session-load test (486-492), body verbatim from spec 5.2.11.

### model_tests.py / conftest.py

No changes — verified by grep: neither references the deleted helpers, the deleted PEX method, or
direct stack-op write_state calls.

## Verification (from assistants/Hugo cwd)

1. `python -m pytest utils/evaluation_suite/_tests/pex_unit_tests.py utils/evaluation_suite/_tests/nlu_unit_tests.py utils/evaluation_suite/_tests/mem_unit_tests.py utils/evaluation_suite/_tests/model_tests.py -q`
   — green, zero skips (per feedback: a skip counts as a failure).
2. `grep -rn "prestack\|_run_stack_op\|_stack_flow\|PRE-STACKED" backend utils` — empty (needs
   step 7 for stack.py:109).
3. `grep -rn "rehydrate_flow" backend` — dialogue_state.py definition + world.py only.
4. FlowStack construction: world.py:19 and tests only (dialogue_state.py:219 deleted).
5. Diff line count: expect net deletion (prod removes ~95 lines — dialogue_state 15, pex repeat
   block + both deleted methods ~60, base.py 2 — against ~15 added; tests are also net negative
   after the two deleted tests).
6. Banned-word grep over the diff only (spec criterion 7): no new occurrences.

## Risks and flags (implement-as-specified; disagreements flagged here only)

- R1 (spec gap, edit required): stack.py:109's comment names `_stack_flow`, so acceptance
  criterion 2's grep fails with the spec's edit list alone. I add the one-word comment fix in
  step 7. Smallest possible deviation; flagging rather than silently expanding scope.
- R2 (interpretation): spec 5.2.10 quotes the full replacement sentence for the world.py:50
  docstring, and that sentence drops the messages.jsonl mention even though `attach_messages`
  still runs. I match the quoted sentence exactly.
- R3 (accepted behavior change, per spec): deleting the code-side confident stack-on means
  awaited-think turns cost one extra tool round. Spec accepts this; no live-eval check by
  builders — the orchestrator runs the 8-scenario gate after shipping.
- R4 (validation-order change, no observable difference): `_update_flow` now validates status
  before filling slots. `_check_grounding` reads `self.grounding` and a static slot type, never
  the values being written, so no write that passed before now fails (and vice versa).
- R5 (weaker assert, as spec'd): in the Hypothesis `stackon` rule, `new_flow = self.stack._stack[-1]`
  makes `assert self.stack._stack[-1] is new_flow` always true (before, `new_flow` was stackon's
  return value). The Pending-status check still bites via `top_before`. Implementing as spec'd.
- R6 (dead local, as spec'd): `before_completed` in the `pop_completed` rule was already unread at
  0f27939; the spec's "keep the after-checks" leaves it. Pre-existing, not my change to clean.
- R7 (pre-existing banned words outside the sweep list): the Agent post-hook method's name
  (agent.py:87, :108) and the pex test stub docstring at pex_unit_tests.py:149 contain words from
  the banned list. Spec 5.2.10 says listed lines only and criterion 7 bans only NEW occurrences,
  so both stay. Flagging so the orchestrator can queue them for a later sweep.
- R8 (empty-stack error shape): `_dispatch_write_state`'s precheck on an empty stack now raises
  AttributeError (`None.slots`) instead of IndexError; both are caught by `_dispatch_tool` and
  returned as corrective errors, and no test asserts the exception type.
- R9 (exact-equality assert): step 9's new `DialogueState.load(path).flow_stack == state.flow_stack`
  drops `_without_ids` per the spec's code block; flow_ids round-trip through save/load, verified
  against `rehydrate_flow` (copies `entry['flow_id']`) and `to_dict`.
