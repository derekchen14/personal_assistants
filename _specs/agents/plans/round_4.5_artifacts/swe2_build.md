# Round 4.5 handoff artifact — swe2 build

## diff

diff --git a/assistants/Dana/backend/components/prompt_engineer.py b/assistants/Dana/backend/components/prompt_engineer.py
index 468a384..4ac8a9d 100644
--- a/assistants/Dana/backend/components/prompt_engineer.py
+++ b/assistants/Dana/backend/components/prompt_engineer.py
@@ -54,7 +54,7 @@ class PromptEngineer:
         self.config = config
         self._models = config.get('models', {})
         self._persona = config.get('persona', {})
-        self._resilience = config.get('resilience', {})
+        self._limits = config.get('limits', {})
         self._api_key = os.getenv('ANTHROPIC_API_KEY')
         self._client: anthropic.Anthropic | None = None
         self._gemini_client = None
@@ -111,7 +111,7 @@ class PromptEngineer:
     # ── Resilience config ────────────────────────────────────────────
 
     def _get_retry_config(self) -> tuple[int, float, float]:
-        llm_cfg = self._resilience.get('llm_retries', {})
+        llm_cfg = self._limits.get('llm_retries', {})
         max_attempts = llm_cfg.get('max_attempts', 2)
         backoff_base = llm_cfg.get('backoff_base_ms', 500) / 1000
         backoff_max = llm_cfg.get('backoff_max_ms', 10000) / 1000
diff --git a/assistants/Dana/schemas/config.py b/assistants/Dana/schemas/config.py
index 8421921..41cdbf7 100644
--- a/assistants/Dana/schemas/config.py
+++ b/assistants/Dana/schemas/config.py
@@ -13,7 +13,7 @@ _DOMAIN = Path(__file__).resolve().parent / 'tools.yaml'
 
 _REQUIRED_SECTIONS = frozenset({
     'environment', 'models', 'persona', 'guardrails', 'session',
-    'memory', 'resilience', 'context_window', 'logging', 'display',
+    'memory', 'limits', 'context_window', 'logging', 'display',
     'thresholds', 'response_constraints', 'human_in_the_loop',
 })
 
diff --git a/assistants/Dana/tests/test_ensemble.py b/assistants/Dana/tests/test_ensemble.py
index 4daa5d4..3b74c51 100644
--- a/assistants/Dana/tests/test_ensemble.py
+++ b/assistants/Dana/tests/test_ensemble.py
@@ -49,7 +49,7 @@ def minimal_config():
                 },
             },
         },
-        'resilience': {},
+        'limits': {},
     })
 
 
diff --git a/assistants/Hugo/backend/components/prompt_engineer.py b/assistants/Hugo/backend/components/prompt_engineer.py
index dee4dc5..9e27274 100644
--- a/assistants/Hugo/backend/components/prompt_engineer.py
+++ b/assistants/Hugo/backend/components/prompt_engineer.py
@@ -83,7 +83,7 @@ class PromptEngineer:
         self.config = config
         self._models = config.get('models', {})
         self.persona = config.get('persona', {})
-        self._resilience = config.get('resilience', {})
+        self._limits = config['limits']
         self._clients: dict[str, object] = {}
 
     def _get_client(self, provider:str):
@@ -132,7 +132,7 @@ class PromptEngineer:
         return self._models.get('default', {}).get('temperature', 0.0)
 
     def _get_retry_config(self) -> tuple[int, float, float]:
-        llm_cfg = self._resilience.get('llm_retries', {})
+        llm_cfg = self._limits.get('llm_retries', {})
         max_attempts = llm_cfg.get('max_attempts', 2)
         backoff_base = llm_cfg.get('backoff_base_ms', 500) / 1000
         backoff_max = llm_cfg.get('backoff_max_ms', 10000) / 1000
@@ -212,9 +212,8 @@ class PromptEngineer:
         msgs = list(build_skill_messages(flow, convo_history, user_text, resolved))
         model_id = self._resolve_model(model)
 
-        max_num_calls = 8
-        if flow.name() in ['audit', 'refine', 'rework', 'compose']:
-            max_num_calls *= 2
+        extended = flow.name() in self._limits['extended_call_flows']
+        max_num_calls = self._limits['extended_tool_calls' if extended else 'max_tool_calls']
 
         family = self._model_family(model)
         adapted = self._adapt_tool_defs(family, tool_defs)
diff --git a/assistants/Hugo/backend/modules/pex.py b/assistants/Hugo/backend/modules/pex.py
index 7680977..05d4b2f 100644
--- a/assistants/Hugo/backend/modules/pex.py
+++ b/assistants/Hugo/backend/modules/pex.py
@@ -16,10 +16,6 @@ from utils.helper import dax2flow
 
 log = logging.getLogger(__name__)
 
-# Acting-loop bounds. _MAX_CORRECTIVE bounds consecutive failed tool calls before the loop stops
-# burning rounds.
-_MAX_ROUNDS = 8
-_MAX_CORRECTIVE = 3
 _FALLBACK_MESSAGE = "I wasn't able to finish that. Could you try rephrasing?"
 _NUDGE_MESSAGE = ('Your last response had no visible text and no tool calls. Reply with your '
                   'final response to the user, or call a tool.')
@@ -91,6 +87,8 @@ class PEX:
 
     def __init__(self, config, ambiguity, engineer, memory, world):
         self.config = config
+        self.max_rounds = config['limits']['max_rounds']
+        self.max_corrective = config['limits']['max_corrective']
         self.ambiguity = ambiguity
         self.engineer = engineer
         self.memory = memory
@@ -329,7 +327,7 @@ class PEX:
         nudged = False
         errors = 0
         last_call = None
-        for round_idx in range(_MAX_ROUNDS):
+        for round_idx in range(self.max_rounds):
             response = self.engineer._call_claude(system_prompt, context.messages,
                                                   model_id, tools=tools, max_tokens=4096)
             self._track_usage(response)
@@ -371,7 +369,7 @@ class PEX:
                 results.append({'type': 'tool_result', 'tool_use_id': tool_use.id,
                                 'content': json.dumps(result, default=str)})
             context.append_message({'role': 'user', 'content': results})
-            if errors >= _MAX_CORRECTIVE:
+            if errors >= self.max_corrective:
                 break  # the model keeps failing tool calls — stop burning rounds
         return self._final_emit(system_prompt, model_id)
 
diff --git a/assistants/Hugo/schemas/config.py b/assistants/Hugo/schemas/config.py
index b2d4bbe..d5aa686 100644
--- a/assistants/Hugo/schemas/config.py
+++ b/assistants/Hugo/schemas/config.py
@@ -18,7 +18,7 @@ EVAL_HARNESS = False
 
 _REQUIRED_SECTIONS = frozenset({
     'environment', 'models', 'persona', 'guardrails', 'session',
-    'memory', 'resilience', 'context_window', 'logging', 'display',
+    'memory', 'limits', 'context_window', 'logging', 'display',
     'thresholds', 'response_constraints', 'human_in_the_loop',
 })
 
diff --git a/assistants/Hugo/utils/tests/conftest.py b/assistants/Hugo/utils/tests/conftest.py
index 6dd9a59..3186aa8 100644
--- a/assistants/Hugo/utils/tests/conftest.py
+++ b/assistants/Hugo/utils/tests/conftest.py
@@ -24,7 +24,9 @@ def minimal_config():
             },
             'overrides': {},
         },
-        'resilience': {},
+        'limits': {'max_rounds': 8, 'max_corrective': 3, 'max_tool_calls': 8,
+                   'extended_tool_calls': 16, 'extended_call_flows': ['audit', 'refine',
+                   'rework', 'compose']},
     })
 
 
diff --git a/assistants/Hugo/utils/tests/pex_unit_tests.py b/assistants/Hugo/utils/tests/pex_unit_tests.py
index 9c13ebc..28b2051 100644
--- a/assistants/Hugo/utils/tests/pex_unit_tests.py
+++ b/assistants/Hugo/utils/tests/pex_unit_tests.py
@@ -24,6 +24,7 @@ from backend.components.prompt_engineer import PromptEngineer
 from backend.components.session_scratchpad import SessionScratchpad
 from backend.prompts.for_orchestrator import build_orchestrator_prompt
 from schemas.ontology import FLOW_CATALOG
+from schemas.config import load_config
 
 _HOT_PATH_TOOLS = ('read_state', 'write_state', 'activate_flow',
                    'append_to_scratchpad', 'store_preference', 'read_scratchpad')
@@ -511,6 +512,49 @@ class TestOrchestratorLoop:
         lines = (session / 'messages.jsonl').read_text().splitlines()
         assert len(lines) == 2  # user message + assistant text, mirrored to disk
 
+    def test_max_rounds_read_from_config(self, sessions_dir, monkeypatch):
+        """The round budget flows from config: max_rounds=1 stops the loop after one round and
+        routes to the wrap-up emit. A dead config wire would silently keep the yaml 8."""
+        limits = {'max_rounds': 1, 'max_corrective': 3, 'max_tool_calls': 8,
+                  'extended_tool_calls': 16,
+                  'extended_call_flows': ['audit', 'refine', 'rework', 'compose']}
+        monkeypatch.setattr('backend.agent.load_config',
+                            lambda: load_config(overrides={'debug': True, 'limits': limits}))
+        agent = Agent(username='test_user')
+        agent.nlu.understand = lambda *args, **kwargs: None
+        queue = _script(agent, [_response(_tool_block('read_state', {})),
+                                _response(_text_block('wrapped up'))])
+        result = agent.take_turn('where were we?')
+        agent.close()
+        assert result['message'] == 'wrapped up'
+        assert queue == []  # one round + the forced no-tools wrap-up, nothing more
+        assert agent.world.context.messages[-2] == {'role': 'user', 'content': _WRAP_UP_MESSAGE}
+
+    def test_call_cap_read_from_config(self, engineer, monkeypatch):
+        """The per-flow call cap flows from config: extended_call_flows get extended_tool_calls,
+        every other flow gets max_tool_calls."""
+        captured = []
+
+        def fake_call(system, msgs, model_id, tool_defs, tool_dispatcher, max_tokens, max_num_calls):
+            captured.append(max_num_calls)
+            return ('', [])
+        monkeypatch.setattr(engineer, '_model_family', lambda model: 'claude')
+        monkeypatch.setattr(engineer, '_call_claude_with_tools', fake_call)
+        engineer.tool_call(flow_classes['audit'](), '', {}, [], None, skill_prompt='')
+        engineer.tool_call(flow_classes['find'](), '', {}, [], None, skill_prompt='')
+        assert captured == [16, 8]
+
+    def test_recovery_keys_collapsed(self):
+        """The yaml declares each bound exactly once: no resilience or recovery sections survive,
+        and the promoted values sit under limits."""
+        cfg = load_config()
+        assert 'recovery' not in cfg and 'resilience' not in cfg
+        limits = cfg['limits']
+        assert limits['max_recovery_attempts'] == 2
+        assert (limits['max_rounds'], limits['max_corrective']) == (8, 3)
+        assert (limits['max_tool_calls'], limits['extended_tool_calls']) == (8, 16)
+        assert limits['extended_call_flows'] == ('audit', 'refine', 'rework', 'compose')
+
 
 
 
diff --git a/assistants/Kalli/backend/components/prompt_engineer.py b/assistants/Kalli/backend/components/prompt_engineer.py
index 179c9dd..69dea87 100644
--- a/assistants/Kalli/backend/components/prompt_engineer.py
+++ b/assistants/Kalli/backend/components/prompt_engineer.py
@@ -52,7 +52,7 @@ class PromptEngineer:
         self.config = config
         self._models = config.get('models', {})
         self._persona = config.get('persona', {})
-        self._resilience = config.get('resilience', {})
+        self._limits = config.get('limits', {})
         self._api_key = os.getenv('ANTHROPIC_API_KEY')
         self._client: anthropic.Anthropic | None = None
 
@@ -94,7 +94,7 @@ class PromptEngineer:
         return self._get_model_param(call_site, 'provider', 'anthropic')
 
     def _get_retry_config(self) -> tuple[int, float, float]:
-        llm_cfg = self._resilience.get('llm_retries', {})
+        llm_cfg = self._limits.get('llm_retries', {})
         max_attempts = llm_cfg.get('max_attempts', 2)
         backoff_base = llm_cfg.get('backoff_base_ms', 500) / 1000
         backoff_max = llm_cfg.get('backoff_max_ms', 10000) / 1000
diff --git a/assistants/Kalli/schemas/config.py b/assistants/Kalli/schemas/config.py
index 8421921..41cdbf7 100644
--- a/assistants/Kalli/schemas/config.py
+++ b/assistants/Kalli/schemas/config.py
@@ -13,7 +13,7 @@ _DOMAIN = Path(__file__).resolve().parent / 'tools.yaml'
 
 _REQUIRED_SECTIONS = frozenset({
     'environment', 'models', 'persona', 'guardrails', 'session',
-    'memory', 'resilience', 'context_window', 'logging', 'display',
+    'memory', 'limits', 'context_window', 'logging', 'display',
     'thresholds', 'response_constraints', 'human_in_the_loop',
 })
 
diff --git a/shared/shared_defaults.yaml b/shared/shared_defaults.yaml
index 440e14a..e63183e 100644
--- a/shared/shared_defaults.yaml
+++ b/shared/shared_defaults.yaml
@@ -76,7 +76,7 @@ memory:
     similarity_threshold: 0.5       # 0.0–1.0, minimum score to include
     embedding_model: null           # embedding model ID; null = provider default
 
-resilience:
+limits:
   tool_retries:
     max_attempts: 3                 # total attempts (1 = no retry)
     backoff_strategy: exponential   # none | linear | exponential
@@ -89,9 +89,11 @@ resilience:
     retriable_errors: [rate_limit, timeout, server_error]
   fallback_model: null              # model_id to try if primary fails; null = none
   max_recovery_attempts: 2          # max times Agent tries re-route before escalate
-
-recovery:
-  max_repair_attempts: 2            # 1 original + 1 retry = 2 total attempts
+  max_rounds: 8                     # orchestrator acting-loop rounds per turn
+  max_corrective: 3                 # consecutive failed tool calls before wrap-up
+  max_tool_calls: 8                 # per-flow tool-call cap in tool_call
+  extended_tool_calls: 16           # cap for the heavy Hugo flows below
+  extended_call_flows: [audit, refine, rework, compose]   # Hugo-specific; other domains ignore

## self_review

WHAT CHANGED (exactly the 11 pre-justified files, per D1-D4 as amended):

1. shared/shared_defaults.yaml — `resilience:` renamed `limits:`; the five promoted keys added flat (max_rounds 8, max_corrective 3, max_tool_calls 8, extended_tool_calls 16, extended_call_flows [audit, refine, rework, compose]); the orphan `recovery:` section deleted (D3-A: max_recovery_attempts survives under limits).
2. Hugo schemas/config.py — 'resilience' -> 'limits' in _REQUIRED_SECTIONS.
3. Hugo backend/modules/pex.py — _MAX_ROUNDS/_MAX_CORRECTIVE module constants (and their comment) deleted; PEX.__init__ reads config['limits'] once by direct indexing into public attributes self.max_rounds / self.max_corrective (D4-A); the loop at _run_loop and the corrective cap use the attributes. Message strings stay code constants (R4).
4. Hugo backend/components/prompt_engineer.py — self._resilience -> self._limits, now a direct index config['limits'] (required section, no .get); the llm_retries reader keeps its inner .get chain (partial-override tolerance per spec caveat); the hardcoded call cap + inline flow list replaced by the two-line D2-C config pick (extended_call_flows tuple membership + extended_tool_calls/max_tool_calls). The base 8 no longer exists in code (R5).
5. Hugo utils/tests/conftest.py — minimal_config 'resilience': {} -> 'limits': {the five promoted keys}.
6. Hugo utils/tests/pex_unit_tests.py — three new tests in TestOrchestratorLoop per spec 4.5.8: T1 test_max_rounds_read_from_config (max_rounds=1 override, scripted one tool round -> wrap-up; proves the wire is live), T2 test_call_cap_read_from_config (captures max_num_calls: audit=16, find=8), T3 test_recovery_keys_collapsed (no 'recovery'/'resilience' sections; limits carries 2/8/3/8/16 and the frozen flow tuple). One import added (load_config). Existing corrective-cap test at :484 untouched and passing against the config-fed 3. Prune bar respected: no attribute-equality test.
7-9. Dana — surgical rename only: _REQUIRED_SECTIONS, self._resilience -> self._limits (keeping the .get read style), test fixture 'resilience': {} -> 'limits': {}.
10-11. Kalli — same rename in schemas/config.py and prompt_engineer.py (two lines). No Kalli fixture references the section.

WHY: E10 — each loop bound declared exactly once, in config; the dead recovery keys collapse to one; the section renamed 'limits' outright per Derek's amendment. Behavior-preserving: values 8/3/8/16 and the four-flow list unchanged.

SCOPE ADHERENCE: zero files beyond the 11; no new config keys beyond the five promoted; no multiplier key (D2); no code-side defaults on the promoted keys (D4/R5); self._limits keeps the underscore per the amendment wording (DoE-settled). Greps confirm: no _MAX_ROUNDS/_MAX_CORRECTIVE in Hugo *.py; no 'resilience' or 'recovery:' in any code/yaml (sole survivor is the pre-existing English-prose comment at Hugo utils/evals/e2e_agent_evals.py:1043 and my T3's own assertions); the inline flow list is gone from Hugo backend (lives in yaml + test fixture only).

TESTS EACH CHANGE SATISFIES: T1 covers pex.py max_rounds wiring; the existing test_consecutive_failures_cap_breaks_to_wrap_up covers max_corrective; T2 covers the prompt_engineer call-cap read; T3 covers the yaml collapse + single declaration; the Dana/Kalli config-load smokes cover the required-section rename fan-out.

VERIFICATION: Hugo free suite (run_evaluation_suite.py, cwd assistants/Hugo): baseline 208 passed / 0 skipped -> after edits 211 passed / 0 skipped / 0 failed. Dana and Kalli `load_config()` smokes both pass. Live eval gate (4.5.6) not run — no .env in this worktree, per instructions.

NOTES FOR DoE:
- The worktree was created 7 commits behind master (fa49a89); I fast-forwarded its branch to the true master HEAD cfe2040 (where the spec's line refs and pex_unit_tests.py live) before editing. The diff above is against cfe2040.
- Pre-existing sibling failures, verified unrelated: Dana tests/test_ensemble.py::test_disagreement_weighted fails identically with my rename reverted (confidence 1.0 vs 0.8 — a vote-weighting issue); Dana tests/test_flows.py hits the live API with a stale model id (404 claude-sonnet-4-5-latest); Kalli tests/test_flows.py fails on `flow['intent'].value` AttributeError inside Kalli's own NLU/FLOW_CATALOG handling — no config involvement in that code path. All out of this round's rename-only scope for Dana/Kalli; flagging rather than fixing per the diff-size guard.

## test_results

===== tests (deterministic) =====
........................................................................ [ 34%]
........................................................................ [ 68%]
...................................................................      [100%]
=============================== warnings summary ===============================
../../../../../../../../../../opt/miniconda3/envs/env314/lib/python3.14/site-packages/google/genai/types.py:42
  /opt/miniconda3/envs/env314/lib/python3.14/site-packages/google/genai/types.py:42: DeprecationWarning: '_UnionGenericAlias' is deprecated and slated for removal in Python 3.17
    VersionedUnionType = Union[builtin_types.UnionType, _UnionGenericAlias]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
211 passed, 1 warning in 1.89s
----- tests (deterministic): PASS (exit 0) -----

all requested levels passed

[sibling smokes]
Dana config OK
Kalli config OK
