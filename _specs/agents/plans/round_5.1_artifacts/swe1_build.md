# SWE1 build — round 5.1

## Orders echo
1. round_5.1_spec.md is authoritative; implemented exactly. 2. Mechanism = "NLU belief state injection" (never "gate/mismatch"); belief injected once per turn regardless of match. 3. Hook-point injection never blocks (_settle_nlu(wait=False)); only Plan/Clarify read_state blocks. 4. Flow-differs+intent-matches = orchestrator prompt decides (defer 80%+); intent-differs = code forces pause Active→Pending + stackon pred_flows[0]. 5. Policy-exec failures re-consult nlu.understand(op='contemplate'), never think. 6. Plain language: no seam/envelope/steward/hydrate/sentinel/etc. 7. Output budget compact, <1500 words. 8. CLAUDE.md rules: simplicity, surgical, no defensive code, trimmed params, 100-char, no new concepts beyond the spec's two.

## Notes
Worktree base fix: the worktree was checked out at commit fa49a89 (pre-round-5.0, policy-dispatch PEX), missing all orchestrator code the spec references. `git reset --hard` was permission-blocked, so I `git checkout 08e6ecd` (round/5.0-pex-hooks tip) into detached HEAD; the diff is my changes vs that base.

All 9 files edited per the approved direction; every edited .py parses (ast.parse OK).

Verification (free, non-LLM suite):
- mem_unit_tests: all pass.
- nlu_unit_tests: 3 fail — exactly the plan_id/has_plan removals (stackon plan_id kwarg, load rehydrates has_plan, document blocks). Known suite-file failures; orchestrator fixes per spec.
- pex_unit_tests: 128 pass, 1 fail — test_skill_tools_match_flow flags the new skills/plan.md as an "orphan-skill" because it's a guidance skill, not a flow. NEW known suite-file failure the orchestrator must fix (add `plan` to that test's non-flow allowlist). I did not touch utils/.

Risks (accepted, per order 1): intent-differs force mutates state mid-loop; the live-stack `active.status='Pending'` mirror closes the activate_flow:660 resync gap. step_5 §5.4's "flags block empties" claim is wrong while has_issues survives — followed the round spec anchors.

## Files changed
- /Users/derekchen/Documents/repos/personal_assistants/.claude/worktrees/wf_b7299b71-923-4/assistants/Hugo/backend/agent.py
- /Users/derekchen/Documents/repos/personal_assistants/.claude/worktrees/wf_b7299b71-923-4/assistants/Hugo/backend/components/dialogue_state.py
- /Users/derekchen/Documents/repos/personal_assistants/.claude/worktrees/wf_b7299b71-923-4/assistants/Hugo/backend/components/flow_stack/parents.py
- /Users/derekchen/Documents/repos/personal_assistants/.claude/worktrees/wf_b7299b71-923-4/assistants/Hugo/backend/components/flow_stack/stack.py
- /Users/derekchen/Documents/repos/personal_assistants/.claude/worktrees/wf_b7299b71-923-4/assistants/Hugo/backend/modules/pex.py
- /Users/derekchen/Documents/repos/personal_assistants/.claude/worktrees/wf_b7299b71-923-4/assistants/Hugo/backend/modules/policies/revise.py
- /Users/derekchen/Documents/repos/personal_assistants/.claude/worktrees/wf_b7299b71-923-4/assistants/Hugo/backend/prompts/for_orchestrator.py
- /Users/derekchen/Documents/repos/personal_assistants/.claude/worktrees/wf_b7299b71-923-4/assistants/Hugo/backend/prompts/pex/skills/plan.md
- /Users/derekchen/Documents/repos/personal_assistants/.claude/worktrees/wf_b7299b71-923-4/shared/shared_defaults.yaml

## Diff
```diff
diff --git a/assistants/Hugo/backend/agent.py b/assistants/Hugo/backend/agent.py
@@ class Agent:
         self.nlu = NLU(self.config, self.ambiguity, self.engineer, self.world)
         self.pex = PEX(self.config, self.ambiguity, self.engineer, self.memory, self.world)
+        self.pex.nlu = self.nlu  # PEX re-consults NLU (contemplate) on policy-execution failures

diff --git a/assistants/Hugo/backend/components/dialogue_state.py b/assistants/Hugo/backend/components/dialogue_state.py
@@
 _BELIEF_FIELDS = ('username', 'goal', 'confirmed', 'rejected', 'workflow_step',
-                  'turn_count', 'has_issues', 'has_plan')
+                  'turn_count', 'has_issues')
@@ rehydrate_flow
     flow.stage = entry['stage']
-    flow.plan_id = entry['plan_id']
     flow.turn_ids = list(entry['turn_ids'])
@@ __init__
         self.has_issues: bool = False
-        self.has_plan: bool = False
         self.natural_birth: bool = True
@@ reset
         self.has_issues = False
-        self.has_plan = False
         self.natural_birth = True
@@ serialize
             'has_issues': self.has_issues,
-            'has_plan': self.has_plan,
             'natural_birth': self.natural_birth,
@@ serialize_session docstring
-        vocabulary: intent, turn_count, has_issues, and has_plan keep their meanings."""
+        vocabulary: intent, turn_count, and has_issues keep their meanings."""
@@
-        flags = {'has_issues': self.has_issues, 'has_plan': self.has_plan}
+        flags = {'has_issues': self.has_issues}
@@ load
         state.has_issues = data['flags']['has_issues']
-        state.has_plan = data['flags']['has_plan']
         return state
@@ write_state docstring
-        'stackon'       push flow_name= (plan_id= optional) with FlowStack semantics,
+        'stackon'       push flow_name= with FlowStack semantics,
@@ _run_stack_op
         if op == 'stackon':
-            stack.stackon(kwargs['flow_name'], plan_id=kwargs.get('plan_id'))
+            stack.stackon(kwargs['flow_name'])
@@ from_dict
         state.has_issues = data.get('has_issues', False)
-        state.has_plan = data.get('has_plan', False)
         state.natural_birth = data.get('natural_birth', True)

diff --git a/assistants/Hugo/backend/components/flow_stack/parents.py b/assistants/Hugo/backend/components/flow_stack/parents.py
@@ BaseFlow.__init__
     self.flow_id: str = ''
-    self.plan_id: str | None = None
     self.turn_ids: list[str] = []
     # Plan flows might create a Flow and keep it pending
@@ to_dict
       'status': self.status, 'stage': self.stage, 'slots': self.slot_values_dict(),
-      'plan_id': self.plan_id, 'turn_ids': self.turn_ids,
+      'turn_ids': self.turn_ids,
     }

diff --git a/assistants/Hugo/backend/components/flow_stack/stack.py b/assistants/Hugo/backend/components/flow_stack/stack.py
@@ __init__
-        self._max_depth: int = config.get('session', {}).get('max_flow_depth', 8)
+        self._max_depth: int = config.get('session', {}).get('max_flow_depth', 16)
@@
-    def stackon(self, flow_name:str, plan_id:str|None=None):
+    def stackon(self, flow_name:str):
@@
-        new_flow = self._push(flow_name, plan_id)
+        new_flow = self._push(flow_name)
@@ _push
-    def _push(self, flow_name:str, plan_id:str|None=None):
+    def _push(self, flow_name:str):
@@
         flow.status = FlowLifecycle.ACTIVE.value
-        flow.plan_id = plan_id
         self._stack.append(flow)

diff --git a/assistants/Hugo/backend/modules/pex.py b/assistants/Hugo/backend/modules/pex.py
@@ __init__
         self._completed_this_turn = []
+        self._injected = False  # belief injected once per turn; reset in execute()
         self._nlu_thread = None  # this turn's parallel NLU think thread; joined+cleared by _settle_nlu
+        self.nlu = None  # wired by Agent after construction; used to re-consult on policy failures
@@ execute
         self._completed_this_turn = []
+        self._injected = False  # belief injected once per turn (whether or not it matches)
@@ _run_loop (⑤ text-only carrier)
             if not tool_uses:
                 if text:
                     context.append_message({'role': 'assistant', 'content': text})
+                    note = self._inject_belief()  # ⑤: text-only turn whose detection landed
+                    if note:
+                        context.append_message({'role': 'user', 'content': note})
+                        continue
                     return text
@@ _run_loop (post-tool: contemplate route + ②③④ carrier)
-                # hook: post-tool
+                # hook: post-tool — a policy execution failure re-consults NLU with narrowed
+                # candidates (contemplate, never think), then re-arms belief for the fresh detection.
+                if tool_use.name == 'activate_flow' and result.get('_error') == 'execution_error':
+                    self.nlu.understand(op='contemplate', user_text=self.world.context.last_user_text)
+                    self._injected = False
                 errors = errors + 1 if not result['_success'] else 0
                 log.info(...)
                 results.append({'type': 'tool_result', ...})
+            note = self._inject_belief()  # hooks ②③④: ride the belief note beside the tool results
+            if note:
+                results.append({'type': 'text', 'text': note})
             context.append_message({'role': 'user', 'content': results})
@@ _dispatch_write_state
-        for key in ('flow_name', 'plan_id'):
-            if key in params:
-                kwargs[key] = params[key]
+        if 'flow_name' in params:
+            kwargs['flow_name'] = params['flow_name']
@@ after _apply_belief_slots (NEW method)
+    def _inject_belief(self) -> str | None:
+        """Once per turn, format NLU's landed detection as a `[belief]` note for the orchestrator
+        context — regardless of whether it matches the active flow. Never blocks: reap a finished
+        NLU thread (wait=False); if detection has not landed yet, skip and retry at the next hook.
+        Flow-only difference is left to the orchestrator (the prompt rule). An INTENT difference is
+        forced in code here: pause the Active flow (→ Pending) and stage NLU's flow."""
+        self._settle_nlu(wait=False)
+        state = self.world.current_state()
+        if self._injected or self._nlu_thread is not None or not state.pred_flows:
+            return None
+        self._injected = True
+        top = state.pred_flows[0]
+        note = (f"[belief] this turn's detection — intent: {state.pred_intent}, "
+                f"flow: {top['flow_name']} ({top['confidence']:.2f}), "
+                f"slots: {json.dumps(state.pred_slots, default=str)}. If you are on a different "
+                f"flow, prefer NLU's detection unless you have a concrete reason to stay.")
+        active = self.flow_stack.get_flow(status='Active')
+        if (active and not self.ambiguity.present()
+                and state.pred_intent in ('Research', 'Draft', 'Revise', 'Publish')
+                and state.pred_intent != active.intent):
+            state.write_state(self.world.state_file(), 'update_flow', status='Pending')
+            state.write_state(self.world.state_file(), 'stackon', flow_name=top['flow_name'])
+            self._apply_belief_slots(state, top['flow_name'])
+            active.status = 'Pending'  # mirror on the live stack — activate_flow re-syncs from it
+            note += (f" Intent changed: I paused {active.name()} and staged {top['flow_name']} "
+                     f"for the detected {state.pred_intent} intent — run it.")
+        return note
@@ write_state tool description
-                    "- `stackon`       — push `flow_name` (optional `plan_id`) on top of the "
+                    "- `stackon`       — push `flow_name` on top of the "
@@ write_state input_schema
-                        'plan_id': {'type': 'string', 'description': 'for stackon under a Plan'},
                         'active': {'type': 'boolean',

diff --git a/assistants/Hugo/backend/modules/policies/revise.py b/assistants/Hugo/backend/modules/policies/revise.py
@@ rework success branch
             for step_name in parsed['done']:
                 flow.slots['suggestions'].mark_as_complete(step_name)
-
-            if state.has_plan:
-                scratch = {'version': '1', 'turn_number': context.turn_id, 'used_count': 0, 'summary': text[:200]}
-                self.scratchpad.write(flow.name(), scratch, writer=flow.name())
-
             self.complete_flow(flow, state, text[:200], metadata={'post_id': post_id})
@@ write_policy success branch
         artifact.add_block({'type': 'card', 'data': self._read_post_content(post_id, tools)})
-        if state.has_plan:
-            self.scratchpad.write(flow.name(), {
-                'version': '1', 'turn_number': context.turn_id,
-                'used_count': 0, 'summary': text[:200],
-            }, writer=flow.name())
         return artifact

diff --git a/assistants/Hugo/backend/prompts/for_orchestrator.py b/assistants/Hugo/backend/prompts/for_orchestrator.py
@@ TOOL_POLICY Plan bullet + belief rule
-    'before staging when you picked Plan. Then decide the order and stage and run the flows one '
-    'by one. '
+    'before staging when you picked Plan. Follow the Workflow Planner guidance in '
+    '`<workflow_planner>` to map the request to catalog flows, then stage and run them one at a '
+    'time. '
     'You own whether the plan is done: after each flow completes, judge whether '
     "the user's goal has been met — stage the next flow until it is, then conclude and report what "
     'was accomplished.\n'
+    '**Belief notes.** A `[belief]` note carries THIS turn\'s NLU detection (intent, flow, slots). '
+    'When it names a DIFFERENT flow than the one you are on, defer to NLU\'s detection unless you '
+    'have a concrete reason to stay — defer in 80%+ of cases. If the note says an intent change '
+    'was already forced (active flow paused, its flow staged), run the staged flow.\n'
@@ build_orchestrator_prompt parts
         f'<outline_levels>\n{_render_outline_levels()}\n</outline_levels>',
+        f'<workflow_planner>\n{engineer.load_skill_template("plan")}\n</workflow_planner>',
         f'<preferences>\n{_render_preferences(memory)}\n</preferences>',

diff --git a/assistants/Hugo/backend/prompts/pex/skills/plan.md b/assistants/Hugo/backend/prompts/pex/skills/plan.md
new file mode 100644
+# Workflow Planner
+
+How to handle a Plan turn — a request that spans several steps. This is guidance, not a flow: you
+issue the stack operations yourself.
+
+1. Read belief (`read_state`) and the flow catalog. Belief carries NLU's detection for this turn.
+2. Break the request into sub-tasks. Map each sub-task to an EXISTING catalog flow — never invent a
+   flow name. If no catalog flow fits a sub-task, drop it or ask the user.
+3. Order the flows by dependency (e.g. outline before write, write before release). Keep the plan
+   minimal — the fewest flows that reach the goal.
+4. Share a one-line plan with the user so they know the shape of the work.
+5. Stage and run ONE flow at a time: `write_state` op=stackon with `active: true` for the first
+   flow, and stage the next only AFTER the current one completes. Do not stack the whole sequence up
+   front — one flow is Active at a time.
+6. After each flow completes, judge whether the user's goal is met. If not, stage the next flow. If
+   it is, stop and report what was accomplished.

diff --git a/shared/shared_defaults.yaml b/shared/shared_defaults.yaml
@@ session
-  max_flow_depth: 8                 # max flows on stack simultaneously
+  max_flow_depth: 16                # max flows on stack simultaneously; plans stack several sub-flows
```
