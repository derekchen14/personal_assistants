# Round 3.1 — SWE1 change set

## Self-review

What changed (D1-A / D2-A / D3-A, scope = §3.1 only):
- nlu.py: predict() now detects first; classify + narrowed re-detect only fires when new
  _intent_split() is True (ranked flows span >1 intent AND top-1 < ambiguity.confidence_min).
  Renamed the intent param to hint='' on predict/_detect_flow/_detect_flow_prompt/_flow_candidate_names;
  empty hint returns the full catalog (revives the existing dead branch). _classify_intent kept.
- experts/__init__.py: added GENERIC_FLOW_PROMPT + GENERIC_FLOW_EXAMPLES (one example per flow-owning
  intent); get_prompt('') now returns it instead of KeyError. rules='' so build_flow_prompt's existing
  PRECEDENCE_NOTE fallback supplies the rules (avoids the circular import the plan flagged).
- for_experts.py: build_flow_prompt intent defaults to '' (convo_history/candidate_catalog also get ''
  defaults, required by Python once intent is defaulted).
- for_orchestrator.py: rewrote the header comment + INTENT_TAXONOMY ("ALREADY classified / don't
  re-classify" removed, Plan/Clarify bias language added) and changed "classified intent" to "detected
  intent" in TOOL_POLICY. Prose only.

Scope adherence: no new components/classes/config keys/state fields; one new private method; no
understand/think signature change (D3-A); no _intent_candidates helper; belief path untouched.

Spec tests satisfied: acceptance §1-6 and §9 map to the TestPredictDispatch cases and the grep target
(no "ALREADY classified" remains). §7/§8 live evals are the orchestrator's to run.

## Diff

```diff
diff --git a/assistants/Hugo/backend/modules/nlu.py b/assistants/Hugo/backend/modules/nlu.py
index e52395c..02895ca 100644
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
+        """True only when the ranked flows span >1 intent AND top-1 is under the confidence floor —
+        the one case a coarse-intent tie-break is worth a call. Under D1-A the span clause is almost
+        always true, so the confidence clause is the real trigger. At most one extra classify + one
+        extra detect per turn."""
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
diff --git a/assistants/Hugo/backend/prompts/experts/__init__.py b/assistants/Hugo/backend/prompts/experts/__init__.py
index 730280a..172cc21 100644
--- a/assistants/Hugo/backend/prompts/experts/__init__.py
+++ b/assistants/Hugo/backend/prompts/experts/__init__.py
@@ -27,5 +27,72 @@ for _mod in _MODULES:
     PROMPTS.update(_mod.PROMPTS)
 
 
+# ── Generic (intent-agnostic) flow prompt — used on the first pass when hint='' ──────
+# One <positive_example> per flow-owning intent (find / outline / rework / release / chat), so an
+# 18-way choice still sees every intent family represented.
+GENERIC_FLOW_EXAMPLES = '''<positive_example>
+## Conversation History
+
+User: "find my posts about onboarding"
+## Output
+
+```json
+{"reasoning": "Locating existing posts.", "flow_name": "find", "confidence": 0.92}
+```
+</positive_example>
+
+<positive_example>
+## Conversation History
+
+User: "outline a post about remote work"
+## Output
+
+```json
+{"reasoning": "Generating an outline.", "flow_name": "outline", "confidence": 0.92}
+```
+</positive_example>
+
+<positive_example>
+## Conversation History
+
+User: "restructure the draft, the sections are out of order"
+## Output
+
+```json
+{"reasoning": "Reworking the draft structure.", "flow_name": "rework", "confidence": 0.90}
+```
+</positive_example>
+
+<positive_example>
+## Conversation History
+
+User: "publish it to the blog"
+## Output
+
+```json
+{"reasoning": "Releasing the post.", "flow_name": "release", "confidence": 0.92}
+```
+</positive_example>
+
+<positive_example>
+## Conversation History
+
+User: "hi there"
+## Output
+
+```json
+{"reasoning": "Simple greeting.", "flow_name": "chat", "confidence": 0.95}
+```
+</positive_example>'''
+
+GENERIC_FLOW_PROMPT = {
+    'instructions': ('Choose the single flow that best matches what the user wants across ALL '
+                     'intents. The candidate list spans every flow; the detected flow fixes the '
+                     'intent, so do not pre-commit to one intent family.'),
+    'rules': '',                       # build_flow_prompt falls back to PRECEDENCE_NOTE
+    'examples': GENERIC_FLOW_EXAMPLES,
+}
+
+
 def get_prompt(intent:str) -> dict[str, str]:
-    return PROMPTS[intent]
+    return PROMPTS[intent] if intent else GENERIC_FLOW_PROMPT
diff --git a/assistants/Hugo/backend/prompts/for_experts.py b/assistants/Hugo/backend/prompts/for_experts.py
index 117de89..d68b66a 100644
--- a/assistants/Hugo/backend/prompts/for_experts.py
+++ b/assistants/Hugo/backend/prompts/for_experts.py
@@ -372,8 +372,8 @@ def build_intent_prompt(user_text:str, convo_history:str,
     return '\n\n'.join(parts)
 
 
-def build_flow_prompt(user_text:str, intent:str, convo_history:str,
-                       candidate_catalog:str, active_post:dict=None) -> str:
+def build_flow_prompt(user_text:str, intent:str='', convo_history:str='',
+                       candidate_catalog:str='', active_post:dict=None) -> str:
     prompt_fields = get_prompt(intent)
     instructions = prompt_fields['instructions'].strip()
     rules = prompt_fields['rules'].strip()
diff --git a/assistants/Hugo/backend/prompts/for_orchestrator.py b/assistants/Hugo/backend/prompts/for_orchestrator.py
index ac72de5..d3e4221 100644
--- a/assistants/Hugo/backend/prompts/for_orchestrator.py
+++ b/assistants/Hugo/backend/prompts/for_orchestrator.py
@@ -23,17 +23,18 @@ from schemas.ontology import FLOW_CATALOG
 
 # ── Tier 1: stable ───────────────────────────────────────────────────────
 
-# NLU classifies the coarse intent and detects the flow before the loop runs; the orchestrator
-# reads that detection from belief and acts on it.
+# NLU detects the flow before the loop runs; that detection fixes the intent, which the
+# orchestrator reads from belief and acts on.
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
index afd4e72..4239e4e 100644
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
@@ -106,12 +106,67 @@ class TestEnsembleVoting:
         stub = MagicMock(side_effect=mock_call)
         stub.apply_guardrails = real_engineer.apply_guardrails
         nlu.engineer = stub
-        result = nlu._detect_flow('give me ideas', intent='Draft')
+        result = nlu._detect_flow('give me ideas', hint='Draft')
 
         assert result['flow_name'] == 'brainstorm'
         assert result['confidence'] == pytest.approx(0.70)   # med voter alone (D6 two-voter ensemble)
 
 
+def _detection(pairs, confidence):
+    """Build a detection dict from (flow_name, weight) pairs at a given top-1 confidence."""
+    pred_flows = [{'flow_name': name, 'confidence': w, 'votes': 1} for name, w in pairs]
+    return {'flow_name': pairs[0][0], 'confidence': confidence, 'pred_flows': pred_flows}
+
+
+class TestPredictDispatch:
+    """predict() detects first and only pays for a classify + narrowed re-detect on a low-confidence
+    cross-intent tie (§3.1.1). _intent_split is the boolean that governs that escalation."""
+
+    def test_predict_skips_classify_on_confident_detection(self, nlu):
+        nlu._detect_flow = MagicMock(return_value=_detection([('outline', 0.9)], 0.9))
+        nlu._classify_intent = MagicMock()
+        result = nlu.predict('draft me an outline')
+        nlu._classify_intent.assert_not_called()
+        assert result['flow_name'] == 'outline'
+
+    def test_predict_escalates_on_low_conf_cross_intent(self, nlu):
+        low = _detection([('outline', 0.5), ('find', 0.5)], 0.4)
+        high = _detection([('compose', 0.8)], 0.8)
+        nlu._detect_flow = MagicMock(side_effect=[low, high])
+        nlu._classify_intent = MagicMock(return_value='Draft')
+        result = nlu.predict('do the thing')
+        nlu._classify_intent.assert_called_once()
+        assert nlu._detect_flow.call_count == 2
+        assert nlu._detect_flow.call_args.kwargs['hint'] == 'Draft'
+        assert result['flow_name'] == 'compose'
+
+    def test_intent_split_true_when_flows_span_intents_and_low_conf(self, nlu):
+        assert nlu._intent_split(_detection([('outline', 0.5), ('find', 0.5)], 0.4)) is True
+
+    def test_intent_split_false_when_confident(self, nlu):
+        assert nlu._intent_split(_detection([('outline', 0.5), ('find', 0.5)], 0.9)) is False
+
+    def test_intent_split_false_when_single_intent(self, nlu):
+        assert nlu._intent_split(_detection([('outline', 0.6), ('compose', 0.4)], 0.4)) is False
+
+    def test_classify_intent_still_callable(self, nlu):
+        nlu.engineer = MagicMock(return_value={'reasoning': 'improving', 'intent': 'Revise'})
+        assert nlu._classify_intent('polish the intro') == 'Revise'
+
+    def test_candidate_names_empty_hint_is_full_catalog(self, nlu):
+        assert nlu._flow_candidate_names('') == list(FLOW_CATALOG)
+
+    def test_candidate_names_hint_narrows_to_intent(self, nlu):
+        names = set(nlu._flow_candidate_names('Draft'))
+        assert {'outline', 'compose', 'refine', 'brainstorm'} <= names
+        assert 'release' not in names
+
+    def test_generic_flow_prompt_used_when_no_hint(self, nlu):
+        from backend.prompts.for_experts import build_flow_prompt
+        prompt = build_flow_prompt('publish it', '', 'history', 'catalog')
+        assert 'across ALL' in prompt
+
+
 # ═══════════════════════════════════════════════════════════════════
 # NLU react()
 # ═══════════════════════════════════════════════════════════════════
```
