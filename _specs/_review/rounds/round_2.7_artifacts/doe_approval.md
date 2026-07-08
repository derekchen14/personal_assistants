# DoE approval — round 5.0

## Verdict
Merge, SWE1 as base. The plans are the same on agent.py, _settle_nlu, the two spec-named join sites, the prompt sentence, and the six hook comments (SWE1 spelled the comments out; the spec's build list requires them). SWE2 wins one point: its third _settle_nlu call at the head of the write_state stackon+active branch is adopted, because the orchestrator prompt steers turns to single-call staging that skips read_state, so _apply_belief_slots (pex.py:579) would fold LAST turn's pred_slots before activate_flow's join fires — a confirmed hole in the two-site design, and a call site of an existing method is not a new concept. SWE2's test plan is trimmed to SWE1's size.

## Ponytail cuts
- SWE2 test 3 (test_settle_is_idempotent) — it tests a 3-line guard; test 1's cleared-handle assertion already proves the clear
- Dedicated activate_flow backstop test (SWE1 optional test 3 / SWE2 test 4) — the join there is the same one line; the stackon+active fold test exercises the meaningful stale path instead
- SWE2's multi-sentence docstring on _settle_nlu — one comment line suffices
- Testing multiple belief fields (SWE1 writes pred_flows, SWE2 writes pred_intent) — pick one field per test, no duplicated variants
- Any join inside _guarded_call for every tool — joining on all pre-tool dispatches would serialize lookups and serialize the parallel NLU/PEX processing (neither plan proposed it; recorded so the builder doesn't add it)
- declare_intent tool / hook registry — already rejected by the spec, stays rejected

## Approved direction
Round 5.0 build instructions (branch round/5.0-pex-hooks). Four files, ~35 lines. One new concept only: the nlu_thread handle + _settle_nlu(); the six hook points are comments naming existing hooks — no registry, no method extraction, no renames.

1. /Users/derekchen/Documents/repos/personal_assistants/assistants/Hugo/backend/agent.py
   In _orchestrate, add the kwarg to the single pex.execute call (lines 82-83):
   `utterance = self.pex.execute(state, self.world.context, self.system_prompt, dax=dax, payload=payload, text=text, nlu_thread=thread)`
   `thread` is already in scope: None on the click and awaited-think paths, a started Thread on the parallel path. Keep the `if thread: thread.join()` turn-boundary settle at lines 84-85 exactly as-is (joining an already-joined Thread is a no-op).

2. /Users/derekchen/Documents/repos/personal_assistants/assistants/Hugo/backend/modules/pex.py
   a. __init__, next to `self._completed_this_turn = []` (line ~150): add `self._nlu_thread = None  # this turn's parallel NLU think thread; joined+cleared by _settle_nlu`.
   b. execute() signature (line 269): add `nlu_thread=None` as the last keyword-only param → `def execute(self, state, context, system_prompt, *, dax=None, payload=None, text='', nlu_thread=None) -> str:`. First body line, above `self._completed_this_turn = []`: `self._nlu_thread = nlu_thread  # hook: PEX start`.
   c. New private method, placed after _security_check (~line 213):
      ```
      def _settle_nlu(self):
          # Join this turn's parallel NLU think thread so belief reads see THIS turn's
          # detection, then clear it — later calls are no-ops.
          if self._nlu_thread:
              self._nlu_thread.join()
              self._nlu_thread = None
      ```
   d. Join site 1 (pre-tool, belief read): first line of _dispatch_read_state (line 555): `self._settle_nlu()`.
   e. Join site 2 (pre-flow backstop): first line of activate_flow body (line 615, before `state = self.world.current_state()`): `self._settle_nlu()`.
   f. Join site 3 (belief fold): in _dispatch_write_state, inside the `if params['op'] == 'stackon' and params.get('active'):` branch (line 576), add `self._settle_nlu()` as the branch's first line, BEFORE `self._apply_belief_slots(...)`. Reason: the prompt's single-call staging path skips read_state, and the fold reads state.pred_flows/pred_slots — without this line it folds last turn's slots. Idempotent no-op when read_state already settled.
   g. Hook-name comments only (no code changes): `# hook: pre-tool` above the guard block in _guarded_call (~line 400), `# hook: post-tool` above the `errors = ...` line in _run_loop (~line 366), `# hook: pre-flow` at the _security_check call in activate_flow (~line 618), `# hook: post-flow` at the _validate_artifact call (~line 632), `# hook: PEX end` above the _record_checkpoint call in execute (~line 286). (PEX start was added in b.)

3. /Users/derekchen/Documents/repos/personal_assistants/assistants/Hugo/backend/prompts/for_orchestrator.py
   In TOOL_POLICY's `- **Plan** →` bullet (lines 63-69), append one sentence after '...instead of guessing a flow or wandering through lookups.': "`read_state` always reflects THIS turn's detection — read it before staging when you picked Plan." One string line within the existing constant; no restructuring (the prompt is byte-stable per session, so this is a content-only edit).

4. /Users/derekchen/Documents/repos/personal_assistants/assistants/Hugo/utils/evaluation_suite/_tests/pex_unit_tests.py
   Add `import time` and `from threading import Thread` to the imports. Add one class `class TestSettleNlu:` near TestSingleCallStaging (line ~1720), using the existing sessions_dir/mock_agent fixtures (conftest.py). Exactly three tests:
   - test_read_state_joins_nlu_thread: open_session; `state = mock_agent.world.current_state()`; a target fn that does `time.sleep(0.05)` then sets `state.pred_flows = [{'flow_name': 'outline', 'confidence': 0.9, 'votes': 2}]`; start the Thread, set `mock_agent.pex._nlu_thread = thread`; call `result = mock_agent.pex._dispatch_read_state({})`; assert the returned state document's belief shows flow 'outline' (assert on whatever field read_state's serialized document carries pred_flows under — check dialogue_state.read_state/serialize_session, ~lines 120-130) and `mock_agent.pex._nlu_thread is None`.
   - test_read_state_no_thread_unchanged: `mock_agent.pex._nlu_thread = None`; `_dispatch_read_state({})` returns `_success` True with default belief; no exception.
   - test_stackon_active_settles_before_fold: same slow-thread trick but the target sets `state.pred_flows` + `state.pred_slots = {'source': [{'post': 'p1'}]}` after the sleep; monkeypatch `pex.activate_flow` to a stub returning `{'_success': True, 'status': 'Completed'}` (same pattern as TestSingleCallStaging.test_stackon_active_folds_slots_and_activates); dispatch `write_state {'op': 'stackon', 'flow_name': 'outline', 'active': True}`; assert the rehydrated top flow entry carries the thread-written slot value (proves the fold waited for the join) and the handle is cleared.
   Do NOT add an idempotency test or a dedicated activate_flow backstop test.

Verification: run the free suite (pytest with cwd and sys.path[0] set to assistants/Hugo — see the tests-cwd gotcha); all existing tests must stay green (click/awaited/plain-reply paths pass thread=None and are behaviorally unchanged). Then the 8-scenario live gate; expect movement on the B04.C01-class stale-origin failures and no added wall time on non-Plan turns.
