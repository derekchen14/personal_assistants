# Round 5.2 — SWE1 implementation plan

Base: 0f27939. All spec line references were checked against the live files; every range in the
spec matches the source except the three items under "Deviations and gaps" below. All paths are
relative to `assistants/Hugo/`. New code bodies are taken verbatim from the spec sections named —
the spec is authoritative and already contains the exact replacement text, so this plan gives
placement, order, and the checks I ran, and only repeats code where the spec leaves a choice.

## Verified reference map (spec → live source, all confirmed)

| Spec section | File and lines | Confirmed content |
| --- | --- | --- |
| 5.2.2 | dialogue_state.py:160-178 | `write_state` with the three-branch op dispatch |
| 5.2.2 | dialogue_state.py:194-205 | `_update_flow` (validates status AFTER slot fill today) |
| 5.2.2 | dialogue_state.py:207-221 | `_run_stack_op` + the throwaway-stack builder |
| 5.2.2 | dialogue_state.py:4, 74; rehydrate_flow at 35-47 | as stated |
| 5.2.3 | pex.py:600-631 | `_dispatch_write_state`; repeat block is 613-623 exactly |
| 5.2.3 | pex.py:7 | the rehydrate_flow import |
| 5.2.4 | pex.py:633-642, 644-672 | `_apply_belief_slots`; the extra fallback call is line 668 |
| 5.2.5 | pex.py:674-688; agent.py:79-81; for_orchestrator.py:97-103 | as stated |
| 5.2.6 | pex.py:698 call site, 723 refresh, 735-763 helper | as stated |
| 5.2.7 | pex.py:596-598; agent.py:108-117 (save at 114) | as stated |
| 5.2.8 | world.py:4, 49-59, 73 | as stated; `reset()` already assigns `_stack` directly |
| 5.2.9 | base.py:224-237 | pre-write copy at 230, status repeat at 235 |
| 5.2.10 | pex.py:429; dialogue_state.py:15; base.py:12, 15, 106; world.py:50 | as stated |
| 5.2.11 | all named test lines in pex/nlu/mem unit tests | as stated (details below) |

Cross-checks run:
- `grep -rn "write_state(" backend utils` — every caller is covered by a spec section; no
  stragglers. `_traces/tolerance_rules.md` mentions write_state ops but describes tool-call
  sequences, not the two-copy design; untouched.
- Policy mid-run calls (draft.py:167,204 stackon; revise.py:103,107,211 fallback) act on
  `self.flow_stack` (the component) already — untouched per builder notes.
- `nlu_unit_tests.py:14` already imports `flow_classes, FlowStack`; no import edit needed there.
- `mem_unit_tests.py`: `World` imported at 13, `DialogueState` at 274, `FlowStack` at 500;
  only `flow_classes` is missing (add to line 500). The messages session-load test lives in
  `TestMessageList` (line 424), fixtures `sessions_dir, minimal_config`; the conftest
  `sessions_dir` fixture monkeypatches `world._SESSIONS_DIR`, so the new test's write-then-load
  round trip works as written in the spec.
- `_dispatch_tool` (pex.py:497) has a bare `except Exception` — the new crash shapes (attribute
  error on `None` stack, `peek()` returning `None` on an empty stack) still convert to corrective
  tool errors, same as today's index errors.
- model_tests.py and conftest.py: no references to prestack, the deleted helpers, or direct
  stack-op write_state calls — spec's "no changes" claim holds.

## Deviations and gaps (implement-as-specified where possible; deviations flagged)

1. **stack.py:109 comment names `_stack_flow`** — the spec's sweep list misses it, but acceptance
   criterion 2 greps `_stack_flow` under `backend/` and must return nothing. These two spec
   clauses conflict; criterion 2 can only pass by editing this line. Planned edit (minimal):
   - before (109): `# (activate_flow via _stack_flow, or pop_completed surfacing the next top).`
   - after: `# (activate_flow, or pop_completed surfacing the next top).`
2. **world.py:50 docstring instruction is not a single-word swap.** The current sentence spans
   lines 50-52 and also covers messages.jsonl; the spec's target sentence ends "...rebuilds the
   flow stack from it". Planned wording keeps both facts and contains the spec's exact sentence:
   `"""Bind this World to a session. An existing dir reloads its state.json as the current
   state and rebuilds the flow stack from it; messages.jsonl is attached as the persistent
   message list; a fresh id defers dir creation to session_dir() (lazy, first turn)."""`
3. **agent.py:114 trailing comment.** The live save line carries
   `# _ensure_session guarantees a bound session`; the spec snippet shows the save line bare.
   I keep the live line unchanged and only insert the new refresh line above it — the surgical
   reading of "insert one line before the save".

## Edit order

The whole round ships as one diff, so order is for reviewability and so each step leaves the tree
importable. Production first (contract change outward), then prompts, then tests.

1. **dialogue_state.py** (5.2.2 + 5.2.10)
   1. Line 4: `from backend.components.flow_stack import FlowStack, flow_classes` →
      `from backend.components.flow_stack import flow_classes`.
   2. Line 15: drop the adverb so the parenthetical reads
      `(tool arguments are unpredictable input).`
   3. Lines 35-47 `rehydrate_flow`: append to the docstring's last sentence:
      `Used at session load (World.open_session) and in serialization round-trip tests.`
   4. Line 74: `self.flow_stack: list[dict] = []  # saved copy of the FlowStack component (see
      write_state)`.
   5. Lines 160-178: replace `write_state` with the spec 5.2.2 body (signature
      `write_state(self, path, op, stack=None, **kwargs)`; refresh
      `self.flow_stack = stack.to_list()` when `stack is not None`, then save).
   6. Lines 194-205: replace `_update_flow` with the spec body — `(self, stack, fields:dict)`,
      grounding check FIRST, then slots, stage, status; no trailing copy line.
   7. Delete lines 207-221 (both helpers). `_check_grounding` (223+) keeps its position as the
      next method.
2. **pex.py** (5.2.3, 5.2.4, 5.2.5, 5.2.6, 5.2.7, 5.2.10)
   1. Line 7: delete the rehydrate_flow import line.
   2. Line 429: drop the adverb, leaving `LLM output is unpredictable input.`
   3. Lines 596-598 `read_state`: insert
      `state.flow_stack = self.flow_stack.to_list()  # saved copy tracks the one stack`
      between the `current_state()` fetch and the return (spec 5.2.7 body).
   4. Lines 600-631: replace `_dispatch_write_state` with the spec 5.2.3 body — precheck reads
      `self.flow_stack.peek()`, single `state.write_state(..., stack=self.flow_stack, **kwargs)`,
      repeat block 613-623 and its comment gone, single-call stackon branch unchanged.
   5. Lines 633-642: replace `_apply_belief_slots` with the spec 5.2.4 body
      (`top = self.flow_stack.peek()`; write passes `stack=self.flow_stack`).
   6. Lines 644-672 `inject_belief_state`: line 666 gains `stack=self.flow_stack` (call split
      across two lines per the spec snippet); line 668 (the second fallback call + comment)
      deleted. Docstring and note text unchanged.
   7. Delete lines 674-688 (`prestack`).
   8. Line 698: replace `flow = self._stack_flow(state, params['flow_name'])` with the spec
      5.2.6 three lines (`name = ...`; `flow = self.flow_stack.find_by_name(name) or
      self.flow_stack.stackon(name)`; `flow.status = 'Active'` + comment). Line 723 refresh
      stays.
   9. Delete lines 735-763 (`_stack_flow`). Its docstring's slot-layering rationale is copied
      nowhere.
3. **agent.py** (5.2.5, 5.2.7)
   1. Line 81: delete the `self.pex.prestack(state)` line; the `else:` branch keeps only the
      awaited `self.nlu.understand(...)` call.
   2. Before line 114's save: insert
      `state.flow_stack = self.pex.flow_stack.to_list()  # refresh the saved copy, then save`.
4. **world.py** (5.2.8, 5.2.10)
   1. Line 4: `from backend.components.dialogue_state import DialogueState, rehydrate_flow`.
   2. Lines 49-52 docstring: reword per Deviation 2 above.
   3. Lines 56-59: replace with the spec 5.2.8 body — on an existing state file, insert the
      loaded state, then
      `self.flow_stack._stack = [rehydrate_flow(entry) for entry in state.flow_stack]`, return
      state; else return None.
5. **base.py** (5.2.9, 5.2.10)
   1. Line 12: last word of "an interception ..." becomes `hook`.
   2. Line 15: line-end parenthetical becomes `(integration point).`
   3. Line 106: the word before "heading" becomes `marker`.
   4. Lines 224-237: replace `complete_flow` with the spec 5.2.9 body — top check via
      `self.flow_stack.peek().flow_id != flow.flow_id`, write passes `stack=self.flow_stack`,
      no pre-write copy, no post-write status line.
6. **for_orchestrator.py** (5.2.5): replace lines 97-99 (through `ONE call does everything: `)
   with the single spec line; lines 100-103 untouched.
7. **stack.py:109** — Deviation 1 comment fix.
8. **Tests** — see next section.

## Test changes (utils/evaluation_suite/_tests, all verified against live line numbers)

### pex_unit_tests.py

1. Lines 96-102 `test_write_state_stacks_and_saves`: append
   `assert mock_agent.pex.flow_stack.peek().flow_type == 'outline'`.
2. Lines 104-117: rename to `test_write_state_pop_completed_pops_the_stack`, replace with the
   spec 5.2.11 body (manual copy lines 112-113 and old docstring gone).
3. Lines 194-212: rename to `test_write_state_slots_reach_the_policy_run`; add docstring
   "slots written via write_state land on the live flow that activate_flow runs."; the two
   write_state calls (197-199) gain `stack=pex.flow_stack` (add `pex = wired.pex` binding — the
   test currently only binds it at 195, which stays); line 209 assert becomes
   `assert pex.flow_stack.find_by_name('outline') is not None`; the comment on 209 goes.
4. Hypothesis machine 1454-1600, per spec item 4: header 1454-1463 rewritten; `__init__`
   comment 1488-1489 rewritten; rules `stackon` (1500-1511, capture `top_before`, write_state
   with `stack=self.stack`, then `new_flow = self.stack._stack[-1]`), `fallback` (1513-1528),
   `fill_source` (1530-1539), `complete_top` (1541-1545), `mark_pending` (1547-1553),
   `pop_completed` (1555-1565) each drop the direct-mutation line(s) and pass
   `stack=self.stack`; invariant 1589-1597 renamed `saved_copy_matches_the_stack`, body kept,
   comment replaced.
5. Line 1739 header → `# Single-call stackon (write_state op=stackon active=true)`.
   Docstring 1744-1746 loses the prestack sentence (ends after "one call"). Line 1765 →
   `top = pex.flow_stack.peek()`. Delete lines 1778-1786 and 1787-1797 (both prestack tests;
   1797 is the last line of the second).
6. Lines 1876-1878 and 1890-1892: replace each three-line block with the spec item 6 body
   (dispatch stackon, `live = pex.flow_stack.peek()`, promote to Active). Asserts stay.
7. Lines 1900-1902 `TestPlanLifecycle` docstring → the spec item 7 text. Body untouched.

### nlu_unit_tests.py

`TestWriteStateOps` (498-595): class docstring (499) → the spec text. Each stack-op /
update_flow call gains a local `stack = FlowStack({}, flow_classes=flow_classes)` and
`stack=stack`:
- 526-552: rename to `test_op_sequence_keeps_saved_copy_current`; docstring reworded to match;
  delete the paired direct lines 534, 537-540, 542, 544, 547, 549; final asserts become the
  two-line pair from the spec (`state.flow_stack == stack.to_list()` and the file reload match) —
  note `_without_ids` is no longer needed here since there is one stack, but I will KEEP the
  plain equality exactly as the spec writes it.
- 554-561, 563-569, 571-583, 585-595: add the stack and `stack=stack` on stack ops and
  update_flow calls; every assertion unchanged.
- 501-503, 505-513, 515-524 need no stack (the `update` op and the two raising calls; the
  `merge` raise happens before any stack use).

### mem_unit_tests.py

- Line 500 import gains `flow_classes`:
  `from backend.components.flow_stack import FlowStack, flow_classes`. `DialogueState` (274) and
  `World` (13) are already imported; no other import edits.
- Add `test_open_session_rebuilds_flow_stack` (spec 5.2.11 body verbatim) as the last method of
  `TestMessageList` (after line 492), matching the `sessions_dir, minimal_config` fixtures of
  the messages test above it.

### model_tests.py / conftest.py

No changes (verified by grep).

## Verification plan

From the `assistants/Hugo` cwd (imports resolve wrong otherwise):
1. `python -m pytest utils/evaluation_suite/_tests/pex_unit_tests.py -x -q`
2. `python -m pytest utils/evaluation_suite/_tests/nlu_unit_tests.py -x -q`
3. `python -m pytest utils/evaluation_suite/_tests/mem_unit_tests.py -x -q`
4. `python -m pytest utils/evaluation_suite/_tests/model_tests.py -x -q`
5. Acceptance greps: `grep -rn "prestack\|_run_stack_op\|_stack_flow\|PRE-STACKED" backend utils`
   (empty); rehydrate_flow referenced in backend only at its definition and world.py; no
   `FlowStack(` construction outside World.__init__, dialogue_state (removed), and tests.
6. Banned-word grep over every touched file; net-deletion check via `git diff --stat`.

## Risks

1. **stack.py:109 (Deviation 1)** — spec-internal conflict; I edit one comment line the sweep
   list does not name so acceptance grep 2 can pass. If the PM prefers, the alternative is to
   relax criterion 2, but the one-line comment fix is smaller.
2. **world.py:50 (Deviation 2)** — the instruction ("replace its second word") cannot produce
   the target sentence alone; my wording keeps the messages.jsonl fact. Flagging in case the PM
   intended to drop that clause.
3. **Empty-stack crash shape changes.** Old code raised on `state.flow_stack[-1]` (index error);
   new code hits `peek()` returning `None` (attribute error) — in `_dispatch_write_state`'s
   precheck, `_update_flow`, and `complete_flow`'s top check (attribute error instead of the
   ValueError message). All routes still land in `_dispatch_tool`'s bare except → corrective
   error; direct-call tests only exercise non-empty stacks. Accepted per the crash-loud rule.
4. **Behavior change on awaited-think turns** (prestack removed): first orchestrator loop now
   starts without the detection stacked; one extra tool round. Spec names this as accepted cost;
   the live 8-scenario gate after shipping is where a regression would show, not the free suite.
5. **`fallback` at depth limit.** `FlowStack.fallback` pushes then marks the old top Invalid, so
   at max depth a forced fallback in `inject_belief_state` raises the depth RuntimeError where
   the old file-backed path rebuilt a stack with the same bound — no new failure mode, but now a
   single raise instead of two copies diverging. Hypothesis's fallback rule keeps its depth
   guard, so the machine never hits it.
6. **`update` op with stack=None from tests** stays valid (`stack is not None` guards only the
   copy refresh); production always passes the stack, so the saved copy cannot go stale through
   write_state. The only refresh points outside write_state are the four the spec names
   (activate_flow 723, read_state, the Agent end-of-turn save, session load).
7. **Banned-word note:** the Agent's end-of-turn method name (agent.py:108) and two nearby
   comments (agent.py:59,121; pex.py:146) contain a word from the banned list; they are
   pre-existing, outside the spec's sweep list, and criterion 7 only forbids NEW occurrences —
   left untouched. Same for the DialogueState.load docstring at dialogue_state.py:135 and the test
   stub docstring at pex_unit_tests.py:149.
8. **nlu_unit_tests.py:19 / mem_unit_tests.py:499 unused rehydrate_flow imports** stay
   (pre-existing, per builder notes). In mem_unit_tests it remains unused after this round; if a
   linter gate is added later it will flag them.
