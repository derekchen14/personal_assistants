# DoE adjudication — round 5.0

## Winner
composed

## Divergence
The two builds are identical in agent.py and for_orchestrator.py and in every hunk of pex.py except two spots. (1) execute() signature: SWE1 wrapped it to two lines; SWE2 kept the spec's verbatim one-line signature (~110 chars, under the 120 hard stop, and one fewer line). (2) The stackon-active settle: SWE1 added an inline comment explaining why the join sits before the fold; SWE2 left the bare call. Join semantics are correct and identical in both: _settle_nlu joins then clears the handle so later calls (including activate_flow's backstop two lines after the stackon settle) are no-ops; the agent.py turn-boundary join stays and is safe because joining an already-joined Thread is a Python no-op; execute() reassigns _nlu_thread at PEX start every turn, so an unsettled handle cannot leak across turns; the think thread never calls into PEX, so no self-join/deadlock. Neither build has a defensive guard against a contract-guaranteed value — the `if self._nlu_thread` check covers the real None case on click/awaited paths.

## Ponytail
- Took SWE2's one-line execute() signature over SWE1's two-line wrap (net -1 line, matches the spec text verbatim)
- Kept SWE1's inline comment on the stackon settle (zero extra lines; without it the call looks redundant next to activate_flow's settle and invites deletion, but the fold reads pred_slots BEFORE activate_flow settles)
- Nothing else cut: every remaining added line is spec-mandated (six hook comments, three join sites, one prompt sentence); no speculative code, no defensive guards found

## Notes
Verified against the live branch round/5.0-pex-hooks: `git apply --check` passes, applied cleanly, all three files AST-parse, and the free suite is green (pex_unit_tests 129 passed, nlu+mem 86 passed, ~2s total). Working tree was then reverted, so this diff can be git-applied verbatim from the repo root. The pex.py index line was dropped from the diff header because the composed blob matches neither SWE's hash; git apply does not need it. Outstanding: approved-direction item 4 (the TestSettleNlu class in utils/evaluation_suite/_tests/pex_unit_tests.py) is in NEITHER build — both SWEs were explicitly scoped to backend files with tests deferred to the orchestrator. It still needs to be written before the round ships, along with the 8-scenario live gate. The one-line execute() signature (~110 chars) and the _nlu_thread field comment (~103 chars) exceed the ~100 guideline but sit under the 120 hard stop and are verbatim from the spec.

## Shipped diff
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
             # Single-call staging (the user 2026-07-03): stackon handed over matching slots; fold
             # in belief's pred_slots, then run the policy — no update_flow / activate_flow calls.
+            self._settle_nlu()  # staging path skips read_state; the fold reads THIS turn's belief
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

> Post-adjudication amendment (the user): flow-execution settles became non-blocking
> (wait=False) and the PEX start/end comments were dropped — see round_5.0_spec.md.
