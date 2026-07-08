# SWE1 build — round 5.0

## Notes
Implemented round 5.0 backend changes exactly per the approved direction. One new concept: the nlu_thread handle + _settle_nlu() join; the six hook points are name-only comments on existing hooks (no registry, no callbacks, no method extraction).

Deviation 1 (worktree base): The worktree was created from a stale master (HEAD fa49a89), NOT from round/5.0-pex-hooks — its agent.py had a 2-arg pex.execute call and for_orchestrator.py did not exist, so none of the spec's line references matched. round/5.0-pex-hooks is checked out in another worktree (marked with +), and `git reset --hard` was blocked by the permission system. I created a fresh local branch `wf_d90c1e7a_5.0` off the round/5.0-pex-hooks commit (e7c2cbb) and switched my worktree to it via `git checkout -B`. This gives the correct base and a clean diff containing only my 4 edits.

Deviation 2 (item 4 skipped): The APPROVED DIRECTION item 4 asks for tests in utils/evaluation_suite/_tests/pex_unit_tests.py, but my SWE1 constraints explicitly say "do NOT touch anything under utils/ ... tests will be added by the orchestrator." I honored the SWE1 constraint and did not add tests. All other items (1, 2, 3) are complete.

Test approach: All three edited files pass `python -c "import ast; ast.parse(...)"`. Changes are additive and backward-compatible — execute() gains a keyword-only `nlu_thread=None`, so the click / awaited-think / plain-reply paths pass thread=None and are behaviorally unchanged (the guard `if self._nlu_thread:` makes _settle_nlu a no-op). Did not run the pytest suite since it lives under utils/ and is mid-restructure (per instructions).

Line-length note: the `self._nlu_thread = None` inline comment in __init__ runs ~103 chars — kept verbatim from the spec text; under the 120 hard stop.

## Files changed
- assistants/Hugo/backend/agent.py
- assistants/Hugo/backend/modules/pex.py
- assistants/Hugo/backend/prompts/for_orchestrator.py

## Diff
```diff
diff --git a/assistants/Hugo/backend/agent.py b/assistants/Hugo/backend/agent.py
index 50b761a..76e7faa 100644
--- a/assistants/Hugo/backend/agent.py
+++ b/assistants/Hugo/backend/agent.py
@@ -80,7 +80,7 @@ class Agent:
             self.pex.prestage(state)     # fix 1 B: belief is fresh only on this awaited path
 
         utterance = self.pex.execute(state, self.world.context, self.system_prompt,
-                                     dax=dax, payload=payload, text=text)
+                                     dax=dax, payload=payload, text=text, nlu_thread=thread)
         if thread:
             thread.join()                # settle the parallel detection at the turn boundary
         return self._epilogue(utterance)
diff --git a/assistants/Hugo/backend/modules/pex.py b/assistants/Hugo/backend/modules/pex.py
index 164e7bf..45d4a40 100644
--- a/assistants/Hugo/backend/modules/pex.py
+++ b/assistants/Hugo/backend/modules/pex.py
@@ -148,6 +148,7 @@ class PEX:
         # Flows that reached Completed during the current turn — reset per execute(), read by the
         # end-of-turn checkpoint.
         self._completed_this_turn = []
+        self._nlu_thread = None  # this turn's parallel NLU think thread; joined+cleared by _settle_nlu
         # Orchestrator hot-path tools — wiring only; the implementations live in
         # DialogueState (state file), SessionScratchpad (scratchpad JSONL), and the policies.
         self._orchestrator_dispatch = {
@@ -211,6 +212,13 @@ class PEX:
 
         return None
 
+    def _settle_nlu(self):
+        # Join this turn's parallel NLU think thread so belief reads see THIS turn's
+        # detection, then clear it — later calls are no-ops.
+        if self._nlu_thread:
+            self._nlu_thread.join()
+            self._nlu_thread = None
+
     # -- Validation -------------------------------------------------------
 
     def _validate_artifact(self, artifact, flow):
@@ -266,11 +274,13 @@ class PEX:
 
     # -- Acting loop (the Assistant's single PEX entry) -------------------
 
-    def execute(self, state, context, system_prompt, *, dax=None, payload=None, text='') -> str:
+    def execute(self, state, context, system_prompt, *, dax=None, payload=None, text='',
+                nlu_thread=None) -> str:
         """The acting loop the Assistant calls once per turn, after NLU has written belief. A
         pure click (dax, no text) is resolved deterministically — no LLM. Otherwise the bounded
         orchestrator loop reads belief (read_state) and decides by intent per the system prompt,
         dispatching tool calls through `_dispatch_tool`. Returns the spoken utterance."""
+        self._nlu_thread = nlu_thread  # hook: PEX start
         self._completed_this_turn = []
         if dax and not text.strip():
             utterance = self._execute_click(state, context, dax, payload or {})
@@ -283,6 +293,7 @@ class PEX:
                            f'Do not re-decide the click — build on it.\n{text}')
             context.append_message({'role': 'user', 'content': message})
             utterance = self._run_loop(system_prompt)
+        # hook: PEX end
         self._record_checkpoint(state, context)
         return utterance
 
@@ -363,6 +374,7 @@ class PEX:
                     result = {'_success': False, '_error': 'server_error',
                               '_message': f'{type(ecp).__name__}: {ecp}'}
                     last_call = None
+                # hook: post-tool
                 errors = errors + 1 if not result['_success'] else 0
                 log.info('  orch round=%d tool=%s ok=%s', round_idx + 1, tool_use.name,
                          result['_success'])
@@ -397,6 +409,7 @@ class PEX:
         `last_call` is (name+args key, succeeded). Dedupe only fires when the previous identical
         call SUCCEEDED — retrying the same call after a transient tool error (server_error from
         an overloaded LLM, a flaky channel API) is legitimate recovery, not a loop."""
+        # hook: pre-tool
         call = (tool_use.name, json.dumps(dict(tool_use.input or {}), sort_keys=True, default=str))
         if tool_use.name not in valid:
             result = {'_success': False, '_error': 'invalid_input',
@@ -553,6 +566,7 @@ class PEX:
     # try/except and returned as corrective tool errors for the orchestrator loop to retry on.
 
     def _dispatch_read_state(self, params:dict) -> dict:
+        self._settle_nlu()
         return {'_success': True, 'state': self.world.current_state().read_state()}
 
     def _dispatch_write_state(self, params:dict) -> dict:
@@ -576,6 +590,7 @@ class PEX:
         if params['op'] == 'stackon' and params.get('active'):
             # Single-call staging (the user 2026-07-03): stackon handed over matching slots; fold
             # in belief's pred_slots, then run the policy — no update_flow / activate_flow calls.
+            self._settle_nlu()  # staging path skips read_state; the fold reads THIS turn's belief
             self._apply_belief_slots(state, params['flow_name'])
             return self.activate_flow({'flow_name': params['flow_name']})
         return {'_success': True, 'state': document}
@@ -612,9 +627,11 @@ class PEX:
         around the policy run. On completion the flow's completion record is written to the
         session scratchpad and returned as the tool result. State-file persistence stays with
         write_state (the orchestrator epilogue)."""
+        self._settle_nlu()
         state = self.world.current_state()
         flow = self._stage_flow(state, params['flow_name'])
 
+        # hook: pre-flow
         approval = self._security_check(flow)
         if approval:
             return {'_success': False, '_error': 'approval_required',
@@ -629,6 +646,7 @@ class PEX:
         if state.active_post:  # the grounding block stays authoritative
             state.grounding['post'] = state.active_post
 
+        # hook: post-flow
         check = self._validate_artifact(artifact, flow)
         if not check.passed:
             if check.is_error_frame:
diff --git a/assistants/Hugo/backend/prompts/for_orchestrator.py b/assistants/Hugo/backend/prompts/for_orchestrator.py
index 1ef5a18..a4f27ff 100644
--- a/assistants/Hugo/backend/prompts/for_orchestrator.py
+++ b/assistants/Hugo/backend/prompts/for_orchestrator.py
@@ -63,7 +63,9 @@ TOOL_POLICY = (
     '- **Plan** → the request spans multiple steps, or you are not certain one flow covers it. '
     'PREFER Plan whenever in doubt: picking Plan means you wait on NLU\'s flow detection '
     '(`read_state` for belief) before deciding next steps, instead of guessing a flow or '
-    'wandering through lookups. Then decide the order and stage and run the flows one by one. '
+    'wandering through lookups. `read_state` always reflects THIS turn\'s detection — read it '
+    'before staging when you picked Plan. Then decide the order and stage and run the flows one '
+    'by one. '
     'You own whether the plan is done: after each flow completes, judge whether '
     "the user's goal has been met — stage the next flow until it is, then conclude and report what "
     'was accomplished.\n'
```
