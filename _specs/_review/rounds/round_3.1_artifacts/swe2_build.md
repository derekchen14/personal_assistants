# Round 3.1 — SWE2 change set

## Self-review

What changed (4 files, D1-A/D2-A/D3-A):
- nlu.py 3.1.1: `predict` detects first with `hint=''`, calls `_classify_intent` only when new
  `_intent_split` is True, then re-detects with `hint=<intent>`. 3.1.3: `intent`->`hint=''` rename on
  `predict`, `_detect_flow`, `_detect_flow_prompt`, `_flow_candidate_names`; empty test flips
  `is None`->`not hint`. `_classify_intent`/schemas kept for the tie-break + contemplate.
  `understand`/`think` untouched (D3-A).
- for_experts.py D1-A: new `GENERIC_FLOW_INSTRUCTIONS` + `GENERIC_FLOW_EXAMPLES` (6 cross-intent
  shots, one per flow-owning intent) and an empty-`intent` branch in `build_flow_prompt` so an empty
  hint no longer hits `get_prompt('')`. Kept the generic prompt in for_experts.py (not
  experts/__init__.py) to avoid an import cycle -- SWE2 deviation flagged in my plan.
- for_orchestrator.py 3.1.2 (prose only): header comment, INTENT_TAXONOMY ("ALREADY classified"/"ACT,
  don't re-classify" -> form-a-sense/never-assert/lean-Plan-or-Clarify), and TOOL_POLICY
  "classified"->"detected".
- nlu_unit_tests.py: 3 existing `intent=` kwargs renamed to `hint=`; new TestPredictTieBreak with the
  9 spec tests.

Scope: only 3.1; no 3.2/3.3/3.4. No new components/config/state fields; one new private method + one
prompt-constant pair, both named in the spec. No `_intent_candidates` helper (spec simplification 1).
No defensive guards added.

Spec tests satisfied: acceptance 1-6, 8, 9; all 9 model-unit tests and the generic-prompt test pass.
Acceptance 7 (live eval before/after on 8 scenarios) is the orchestrator's to run.

## Diff

```diff
diff --git a/assistants/Hugo/backend/modules/nlu.py b/assistants/Hugo/backend/modules/nlu.py
index e52395c..12d6a7c 100644
--- a/assistants/Hugo/backend/modules/nlu.py
+++ b/assistants/Hugo/backend/modules/nlu.py
@@ -258,20 +258,30 @@ class NLU:
 
     # ── Prediction ────────────────────────────────────────────────────
 
-    def predict(self, user_text:str) -> dict:
-        intent = self._classify_intent(user_text)
-        detection = self._detect_flow(user_text, intent)
+    def predict(self, user_text:str, hint:str='') -> dict:
+        detection = self._detect_flow(user_text, hint)      # hint='' on the pre-hook first pass
+        if self._intent_split(detection):                   # low-confidence AND spans >1 intent
+            intent = self._classify_intent(user_text)       # the retained tie-break call
+            detection = self._detect_flow(user_text, hint=intent)
         return {
             'flow_name': detection['flow_name'],
             'confidence': detection['confidence'],
             'pred_flows': detection.get('pred_flows', []),
         }
 
-    def _detect_flow_prompt(self, user_text:str, intent:str, convo_history:str) -> str:
-        candidate_names = self._flow_candidate_names(intent)
+    def _intent_split(self, detection:dict) -> bool:
+        """True only when the ranked flows span more than one intent AND top-1 sits under the
+        confidence floor — the single case where a coarse-intent tie-break earns its extra call.
+        Under D1-A the span clause is almost always true, so the confidence floor is the real
+        trigger. At most one extra classify + one extra detect per turn."""
+        intents = {FLOW_CATALOG[f['flow_name']]['intent'] for f in detection['pred_flows']}
+        return len(intents) > 1 and detection['confidence'] < self.ambiguity.confidence_min
+
+    def _detect_flow_prompt(self, user_text:str, hint:str, convo_history:str) -> str:
+        candidate_names = self._flow_candidate_names(hint)
         catalog = render_flow_catalog(candidate_names, FLOW_CATALOG, flow_classes)
         active_post = self._active_post_dict()
-        return build_flow_prompt(user_text, intent, convo_history,
+        return build_flow_prompt(user_text, hint, convo_history,
                                  catalog, active_post=active_post)
 
     def _active_post_dict(self) -> dict | None:
@@ -320,10 +330,10 @@ class NLU:
             self._raise_if_debug(ecp)
             return 'Converse'
 
-    def _detect_flow(self, user_text:str, intent:str|None=None) -> dict:
+    def _detect_flow(self, user_text:str, hint:str='') -> dict:
         convo_history = self.world.context.compile_history()
-        prompt = self._detect_flow_prompt(user_text, intent, convo_history)
-        candidate_names = self._flow_candidate_names(intent)
+        prompt = self._detect_flow_prompt(user_text, hint, convo_history)
+        candidate_names = self._flow_candidate_names(hint)
         schema = _flow_detection_schema(candidate_names)
 
         def _call_voter(voter:dict) -> dict | None:
@@ -359,11 +369,11 @@ class NLU:
 
         return self._tally_votes(votes)
 
-    def _flow_candidate_names(self, intent:str|None) -> list[str]:
-        if intent is None:
+    def _flow_candidate_names(self, hint:str='') -> list[str]:
+        if not hint:
             return list(FLOW_CATALOG)
-        edges = _get_edge_flows_for_intent(intent)
-        return [name for name, cat in FLOW_CATALOG.items() if cat['intent'] == intent or name in edges]
+        edges = _get_edge_flows_for_intent(hint)
+        return [name for name, cat in FLOW_CATALOG.items() if cat['intent'] == hint or name in edges]
 
     def _fill_slots(self, flow, payload:dict={}):
         last_turn = self.world.context.last_user_turn
diff --git a/assistants/Hugo/backend/prompts/for_experts.py b/assistants/Hugo/backend/prompts/for_experts.py
index 117de89..d55ee47 100644
--- a/assistants/Hugo/backend/prompts/for_experts.py
+++ b/assistants/Hugo/backend/prompts/for_experts.py
@@ -300,6 +300,80 @@ User: "start a new post about remote work tips"
 ```
 </positive_example>'''
 
+# ── Generic flow stage: used when there is no intent hint (empty first pass) ──
+
+GENERIC_FLOW_INSTRUCTIONS = (
+    'Choose the single flow that best matches what the user wants across ALL intents. The candidate '
+    'list spans every flow; the detected flow fixes the intent, so do not pre-commit to one intent '
+    'family. Reason first about the user\'s goal, then commit to one flow.'
+)
+
+GENERIC_FLOW_EXAMPLES = '''<positive_example>
+## Conversation History
+
+User: "pull up the posts on onboarding"
+## Output
+
+```json
+{"reasoning": "User wants to locate existing posts by topic.", "flow_name": "find", "confidence": 0.88}
+```
+</positive_example>
+
+<positive_example>
+## Conversation History
+
+User: "sketch out the structure for a piece on remote teams"
+## Output
+
+```json
+{"reasoning": "User wants an outline for a new post.", "flow_name": "outline", "confidence": 0.85}
+```
+</positive_example>
+
+<positive_example>
+## Conversation History
+
+User: "check the intro for tone drift"
+## Output
+
+```json
+{"reasoning": "User wants a voice and consistency audit of existing prose.", "flow_name": "audit", "confidence": 0.83}
+```
+</positive_example>
+
+<positive_example>
+## Conversation History
+
+User: "push it live now"
+## Output
+
+```json
+{"reasoning": "User wants to publish the current post.", "flow_name": "release", "confidence": 0.86}
+```
+</positive_example>
+
+<positive_example>
+## Conversation History
+
+User: "any tips for keeping readers past the first paragraph?"
+## Output
+
+```json
+{"reasoning": "Open-ended writing question, no content operation.", "flow_name": "chat", "confidence": 0.8}
+```
+</positive_example>
+
+<positive_example>
+## Conversation History
+
+User: "map out a three-part series and then draft the first one"
+## Output
+
+```json
+{"reasoning": "Multi-step request spanning several intents.", "flow_name": "plan", "confidence": 0.82}
+```
+</positive_example>'''
+
 JSON_ONLY_REMINDER = 'Reply with the JSON object only. No prose, no markdown fences around the object.'
 
 
@@ -374,16 +448,18 @@ def build_intent_prompt(user_text:str, convo_history:str,
 
 def build_flow_prompt(user_text:str, intent:str, convo_history:str,
                        candidate_catalog:str, active_post:dict=None) -> str:
-    prompt_fields = get_prompt(intent)
-    instructions = prompt_fields['instructions'].strip()
-    rules = prompt_fields['rules'].strip()
-    examples = prompt_fields['examples'].strip()
-
-    rules_body = rules if rules else PRECEDENCE_NOTE
+    if intent:
+        prompt_fields = get_prompt(intent)
+        instructions = prompt_fields['instructions'].strip()
+        rules = prompt_fields['rules'].strip() or PRECEDENCE_NOTE
+        examples = prompt_fields['examples'].strip()
+    else:
+        instructions, rules, examples = (
+            GENERIC_FLOW_INSTRUCTIONS, PRECEDENCE_NOTE, GENERIC_FLOW_EXAMPLES)
     task_body = (
         f'{BACKGROUND_STATIC}\n\n'
         f'## Instructions\n\n{instructions}\n\n'
-        f'## Rules\n\n{rules_body}'
+        f'## Rules\n\n{rules}'
     )
     current = _render_current_scenario(user_text, convo_history, active_post, intent)
     parts = [
diff --git a/assistants/Hugo/backend/prompts/for_orchestrator.py b/assistants/Hugo/backend/prompts/for_orchestrator.py
index ac72de5..9099f3a 100644
--- a/assistants/Hugo/backend/prompts/for_orchestrator.py
+++ b/assistants/Hugo/backend/prompts/for_orchestrator.py
@@ -23,17 +23,18 @@ from schemas.ontology import FLOW_CATALOG
 
 # ── Tier 1: stable ───────────────────────────────────────────────────────
 
-# NLU classifies the coarse intent and detects the flow before the loop runs; the orchestrator
-# reads that detection from belief and acts on it.
+# NLU detects the flow before the loop runs, and the detected flow fixes the intent; the
+# orchestrator reads that detection from belief and acts on it.
 INTENT_TAXONOMY = (
     '## Intent Taxonomy\n\n'
     'Work is organized into **flows** — units of work that share a goal (drafting a post, '
-    'releasing it, browsing notes, etc.). Flows group under one of seven **intents**. NLU runs '
-    'before you and has ALREADY classified the intent and detected the flow for this turn — read '
-    'them from belief with `read_state` (user_beliefs.intent, pred_flows, pred_slots). Your job '
-    'is to ACT on that detection, not to re-classify it; treat your own read of the intent as '
-    'internal reasoning, and bias toward Plan or Clarify only when the detection looks uncertain '
-    'or the request spans several steps:\n'
+    'releasing it, browsing notes, etc.). Flows group under one of seven **intents**. You form a '
+    'quick sense of the intent as you reason — but you do NOT classify on the record. NLU owns the '
+    'authoritative intent: it is written when NLU detects a flow, and you read it from belief with '
+    '`read_state` (user_beliefs.intent, pred_flows, pred_slots). Use your own sense only to pick '
+    'which flow to activate when the mapping is obvious (a click or a clear continuation). When you '
+    'are unsure — the request is multi-step, vague, or spans intents — bias toward Plan or Clarify, '
+    'which wait for NLU rather than guessing. Never assert a final intent yourself:\n'
     '- **Research**: browse topics, find posts, view and summarize drafts, compare posts.\n'
     '- **Draft**: brainstorm ideas, generate outlines, compose prose from an outline, '
     'refine sections.\n'
@@ -50,7 +51,7 @@ INTENT_TAXONOMY = (
 TOOL_POLICY = (
     '## Tool-Use Policy\n\n'
     '**Understanding a user turn.** NLU runs before you and writes the detection to belief: the '
-    'classified `intent`, ranked candidate flows (`pred_flows`), and filled slot values '
+    'detected `intent`, ranked candidate flows (`pred_flows`), and filled slot values '
     '(`pred_slots`). Call `read_state` to read it — do not re-derive the flow yourself.\n'
     '**You route; flows resolve.** You are not responsible for resolving the user\'s request '
     'yourself — the flow you dispatch does that with its own skill prompt and tools. So you do '
diff --git a/assistants/Hugo/utils/evaluation_suite/_tests/nlu_unit_tests.py b/assistants/Hugo/utils/evaluation_suite/_tests/nlu_unit_tests.py
index afd4e72..f79d6b4 100644
--- a/assistants/Hugo/utils/evaluation_suite/_tests/nlu_unit_tests.py
+++ b/assistants/Hugo/utils/evaluation_suite/_tests/nlu_unit_tests.py
@@ -78,7 +78,7 @@ class TestEnsembleVoting:
         stub = MagicMock(side_effect=mock_call)
         stub.apply_guardrails = real_engineer.apply_guardrails
         nlu.engineer = stub
-        result = nlu._detect_flow('hello', intent='Converse')
+        result = nlu._detect_flow('hello', hint='Converse')
 
         assert result['flow_name'] == 'chat'
         assert result['confidence'] == pytest.approx(1.0)
@@ -91,7 +91,7 @@ class TestEnsembleVoting:
         stub = MagicMock(side_effect=mock_call)
         stub.apply_guardrails = real_engineer.apply_guardrails
         nlu.engineer = stub
-        result = nlu._detect_flow('hello', intent='Converse')
+        result = nlu._detect_flow('hello', hint='Converse')
 
         assert result['flow_name'] == 'chat'
         assert result['confidence'] == 0.3
@@ -106,12 +106,73 @@ class TestEnsembleVoting:
         stub = MagicMock(side_effect=mock_call)
         stub.apply_guardrails = real_engineer.apply_guardrails
         nlu.engineer = stub
-        result = nlu._detect_flow('give me ideas', intent='Draft')
+        result = nlu._detect_flow('give me ideas', hint='Draft')
 
         assert result['flow_name'] == 'brainstorm'
         assert result['confidence'] == pytest.approx(0.70)   # med voter alone (D6 two-voter ensemble)
 
 
+class TestPredictTieBreak:
+    """Round 3.1: predict detects first (hint='') and classifies only to break a low-confidence
+    cross-intent tie. _intent_split gates that extra call; _flow_candidate_names narrows by hint."""
+
+    def test_predict_skips_classify_on_confident_detection(self, nlu):
+        detection = {'flow_name': 'outline', 'confidence': 0.9,
+                     'pred_flows': [{'flow_name': 'outline', 'confidence': 0.9, 'votes': 2}]}
+        nlu._detect_flow = MagicMock(return_value=detection)
+        nlu._classify_intent = MagicMock()
+        result = nlu.predict('draft me an outline')
+        nlu._classify_intent.assert_not_called()
+        assert result['flow_name'] == 'outline'
+
+    def test_predict_escalates_on_low_conf_cross_intent(self, nlu):
+        low = {'flow_name': 'outline', 'confidence': 0.4,
+               'pred_flows': [{'flow_name': 'outline', 'confidence': 0.4, 'votes': 1},
+                              {'flow_name': 'find', 'confidence': 0.35, 'votes': 1}]}
+        draft = {'flow_name': 'compose', 'confidence': 0.8,
+                 'pred_flows': [{'flow_name': 'compose', 'confidence': 0.8, 'votes': 2}]}
+        nlu._detect_flow = MagicMock(side_effect=[low, draft])
+        nlu._classify_intent = MagicMock(return_value='Draft')
+        result = nlu.predict('do the thing')
+        nlu._classify_intent.assert_called_once()
+        assert nlu._detect_flow.call_count == 2
+        assert nlu._detect_flow.call_args_list[1].kwargs['hint'] == 'Draft'
+        assert result['flow_name'] == 'compose'
+
+    def test_intent_split_true_when_flows_span_intents_and_low_conf(self, nlu):
+        detection = {'confidence': 0.4,
+                     'pred_flows': [{'flow_name': 'outline'}, {'flow_name': 'find'}]}
+        assert nlu._intent_split(detection) is True
+
+    def test_intent_split_false_when_confident(self, nlu):
+        detection = {'confidence': 0.9,
+                     'pred_flows': [{'flow_name': 'outline'}, {'flow_name': 'find'}]}
+        assert nlu._intent_split(detection) is False
+
+    def test_intent_split_false_when_single_intent(self, nlu):
+        detection = {'confidence': 0.4,
+                     'pred_flows': [{'flow_name': 'outline'}, {'flow_name': 'compose'}]}
+        assert nlu._intent_split(detection) is False
+
+    def test_classify_intent_still_callable(self, nlu):
+        nlu.engineer = MagicMock(return_value={'reasoning': 'polish', 'intent': 'Revise'})
+        assert nlu._classify_intent('polish the intro') == 'Revise'
+
+    def test_candidate_names_empty_hint_is_full_catalog(self, nlu):
+        assert nlu._flow_candidate_names('') == list(FLOW_CATALOG)
+
+    def test_candidate_names_hint_narrows_to_intent(self, nlu):
+        names = nlu._flow_candidate_names('Draft')
+        assert {'outline', 'compose', 'refine', 'brainstorm'} <= set(names)
+        assert 'release' not in names
+
+    def test_generic_flow_prompt_used_when_no_hint(self):
+        from backend.prompts.for_experts import build_flow_prompt, GENERIC_FLOW_INSTRUCTIONS
+        prompt = build_flow_prompt('publish it', '', '', 'catalog')
+        assert prompt
+        assert GENERIC_FLOW_INSTRUCTIONS in prompt
+
+
 # ═══════════════════════════════════════════════════════════════════
 # NLU react()
 # ═══════════════════════════════════════════════════════════════════
```
