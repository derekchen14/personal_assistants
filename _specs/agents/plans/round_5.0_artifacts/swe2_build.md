# SWE2 build — round 5.0

## Notes
Implemented round 5.0 exactly per the approved direction across the three backend files.

WORKTREE BASE FIX (deviation, unavoidable): the worktree was created on a stale branch (worktree-wf_d90c1e7a-21e-5 at commit fa49a89) that PREDATES the entire round 5.0 codebase — it had no for_orchestrator.py, no orchestrator PEX (_run_loop/_guarded_call/activate_flow/_dispatch_*), and execute() was just `def execute(self, state, context)`. The spec's symbols and line numbers matched the round/5.0-pex-hooks branch (e7c2cbb), which was already checked out in a different worktree (so I could not check it out directly). I `git reset --hard round/5.0-pex-hooks` on my disposable worktree branch to get the correct base, verified the code matched the spec line-for-line, then applied the edits. The diff above is my changes against that base.

Changes made:
1. agent.py: added `nlu_thread=thread` kwarg to the single pex.execute call. `if thread: thread.join()` turn-boundary settle left untouched.
2. pex.py: added `self._nlu_thread = None` field in __init__; added `nlu_thread=None` keyword-only param to execute() with `self._nlu_thread = nlu_thread  # hook: PEX start` as first body line; added the `_settle_nlu()` private method after _security_check; three join sites (_dispatch_read_state first line, stackon-active branch before _apply_belief_slots, activate_flow first body line); five hook-name comments (pre-tool, post-tool, pre-flow, post-flow, PEX end — PEX start is inline on the field assignment).
3. for_orchestrator.py: appended the read_state sentence to the Plan bullet as content-only string lines.

SCOPE: skipped APPROVED DIRECTION part 4 (the test class in utils/evaluation_suite/_tests/pex_unit_tests.py) — my SWE2 instructions explicitly restrict me to backend files only (agent.py, modules/pex.py, prompts/for_orchestrator.py) and state tests are added by the orchestrator.

No new concept beyond the sanctioned nlu_thread handle + _settle_nlu(). The six hook points are comments naming existing hooks — no registry, no callbacks, no method extraction, no renames.

VERIFICATION: `python -c "import ast; ast.parse(...)"` passes for all three files. Did not run the pytest suite (it lives under utils/, out of my scope and mid-restructure); the free suite + 8-scenario live gate are the orchestrator's step per the approved direction. Two lines run slightly over 100 chars (the _nlu_thread field comment at ~101 and the execute signature at ~109) but both are under the 120-char hard stop and are verbatim from the spec.

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
index 164e7bf..f105abc 100644
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
@@ -266,11 +274,12 @@ class PEX:
 
     # -- Acting loop (the Assistant's single PEX entry) -------------------
 
-    def execute(self, state, context, system_prompt, *, dax=None, payload=None, text='') -> str:
+    def execute(self, state, context, system_prompt, *, dax=None, payload=None, text='', nlu_thread=None) -> str:
         """The acting loop the Assistant calls once per turn, after NLU has written belief. A
         pure click (dax, no text) is resolved deterministically — no LLM. Otherwise the bounded
         orchestrator loop reads belief (read_state) and decides by intent per the system prompt,
         dispatching tool calls through `_dispatch_tool`. Returns the spoken utterance."""
+        self._nlu_thread = nlu_thread  # hook: PEX start
         self._completed_this_turn = []
         if dax and not text.strip():
             utterance = self._execute_click(state, context, dax, payload or {})
@@ -283,6 +292,7 @@ class PEX:
                            f'Do not re-decide the click — build on it.\n{text}')
             context.append_message({'role': 'user', 'content': message})
             utterance = self._run_loop(system_prompt)
+        # hook: PEX end
         self._record_checkpoint(state, context)
         return utterance
 
@@ -363,6 +373,7 @@ class PEX:
                     result = {'_success': False, '_error': 'server_error',
                               '_message': f'{type(ecp).__name__}: {ecp}'}
                     last_call = None
+                # hook: post-tool
                 errors = errors + 1 if not result['_success'] else 0
                 log.info('  orch round=%d tool=%s ok=%s', round_idx + 1, tool_use.name,
                          result['_success'])
@@ -397,6 +408,7 @@ class PEX:
         `last_call` is (name+args key, succeeded). Dedupe only fires when the previous identical
         call SUCCEEDED — retrying the same call after a transient tool error (server_error from
         an overloaded LLM, a flaky channel API) is legitimate recovery, not a loop."""
+        # hook: pre-tool
         call = (tool_use.name, json.dumps(dict(tool_use.input or {}), sort_keys=True, default=str))
         if tool_use.name not in valid:
             result = {'_success': False, '_error': 'invalid_input',
@@ -553,6 +565,7 @@ class PEX:
     # try/except and returned as corrective tool errors for the orchestrator loop to retry on.
 
     def _dispatch_read_state(self, params:dict) -> dict:
+        self._settle_nlu()
         return {'_success': True, 'state': self.world.current_state().read_state()}
 
     def _dispatch_write_state(self, params:dict) -> dict:
@@ -576,6 +589,7 @@ class PEX:
         if params['op'] == 'stackon' and params.get('active'):
             # Single-call staging (Derek 2026-07-03): stackon handed over matching slots; fold
             # in belief's pred_slots, then run the policy — no update_flow / activate_flow calls.
+            self._settle_nlu()
             self._apply_belief_slots(state, params['flow_name'])
             return self.activate_flow({'flow_name': params['flow_name']})
         return {'_success': True, 'state': document}
@@ -612,9 +626,11 @@ class PEX:
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
@@ -629,6 +645,7 @@ class PEX:
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
