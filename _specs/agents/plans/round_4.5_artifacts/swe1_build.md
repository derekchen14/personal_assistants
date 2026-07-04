# Round 4.5 handoff artifact — swe1 build

## diff

diff --git a/assistants/Dana/backend/components/prompt_engineer.py b/assistants/Dana/backend/components/prompt_engineer.py
index 468a384..f4e047d 100644
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
@@ -108,10 +108,10 @@ class PromptEngineer:
     def _get_provider(self, call_site:str='default') -> str:
         return self._get_model_param(call_site, 'provider', 'anthropic')
 
-    # ── Resilience config ────────────────────────────────────────────
+    # ── Limits config ────────────────────────────────────────────────
 
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
index 6dd9a59..c519f80 100644
--- a/assistants/Hugo/utils/tests/conftest.py
+++ b/assistants/Hugo/utils/tests/conftest.py
@@ -24,7 +24,9 @@ def minimal_config():
             },
             'overrides': {},
         },
-        'resilience': {},
+        'limits': {'max_rounds': 8, 'max_corrective': 3, 'max_tool_calls': 8,
+                   'extended_tool_calls': 16,
+                   'extended_call_flows': ['audit', 'refine', 'rework', 'compose']},
     })
 
 
diff --git a/assistants/Hugo/utils/tests/pex_unit_tests.py b/assistants/Hugo/utils/tests/pex_unit_tests.py
index 9c13ebc..ec0d913 100644
--- a/assistants/Hugo/utils/tests/pex_unit_tests.py
+++ b/assistants/Hugo/utils/tests/pex_unit_tests.py
@@ -23,6 +23,7 @@ from backend.components.user_preferences import UserPreferences
 from backend.components.prompt_engineer import PromptEngineer
 from backend.components.session_scratchpad import SessionScratchpad
 from backend.prompts.for_orchestrator import build_orchestrator_prompt
+from schemas.config import load_config
 from schemas.ontology import FLOW_CATALOG
 
 _HOT_PATH_TOOLS = ('read_state', 'write_state', 'activate_flow',
@@ -511,6 +512,45 @@ class TestOrchestratorLoop:
         lines = (session / 'messages.jsonl').read_text().splitlines()
         assert len(lines) == 2  # user message + assistant text, mirrored to disk
 
+    def test_max_rounds_read_from_config(self, sessions_dir, monkeypatch):
+        """A dead config wire silently keeps 8 rounds; with max_rounds=1 the queue would then
+        underflow instead of draining exactly to the forced wrap-up."""
+        limits = {'max_rounds': 1, 'max_corrective': 3, 'max_tool_calls': 8,
+                  'extended_tool_calls': 16,
+                  'extended_call_flows': ['audit', 'refine', 'rework', 'compose']}
+        monkeypatch.setattr('backend.agent.load_config',
+                            lambda: load_config(overrides={'debug': True, 'limits': limits}))
+        agent = Agent(username='test_user')
+        agent.nlu.understand = lambda *args, **kwargs: None
+        queue = _script(agent, [_response(_tool_block('read_state', {})),
+                                _response(_text_block('Wrapped up after one round.'))])
+        result = agent.take_turn('walk the whole backlog')
+        assert result['message'] == 'Wrapped up after one round.'
+        assert queue == []  # one tool round + the forced no-tools wrap-up, nothing more
+        assert agent.world.context.messages[-2] == {'role': 'user',
+                                                    'content': _WRAP_UP_MESSAGE}
+        agent.close()
+
+    def test_call_cap_read_from_config(self, engineer, monkeypatch):
+        captured = []
+        def _capture(system, msgs, model_id, tool_defs, tool_dispatcher, max_tokens, max_num_calls):
+            captured.append(max_num_calls)
+            return ('', [])
+        monkeypatch.setattr(PromptEngineer, '_model_family', staticmethod(lambda model: 'claude'))
+        monkeypatch.setattr(engineer, '_call_claude_with_tools', _capture)
+        engineer.tool_call(flow_classes['audit'](), '', {}, [], None, skill_prompt='test')
+        engineer.tool_call(flow_classes['find'](), '', {}, [], None, skill_prompt='test')
+        assert captured == [16, 8]  # extended cap for audit, base cap for find
+
+    def test_recovery_keys_collapsed(self):
+        cfg = load_config()
+        assert 'recovery' not in cfg and 'resilience' not in cfg
+        limits = cfg['limits']
+        assert limits['max_recovery_attempts'] == 2  # the ONE surviving recovery key
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
index 440e14a..d35a5ec 100644
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
+  max_rounds: 8                     # orchestrator acting-loop rounds (was pex.py _MAX_ROUNDS)
+  max_corrective: 3                 # consecutive failed tool calls before wrap-up
+  max_tool_calls: 8                 # per-flow tool-call cap inside tool_call
+  extended_tool_calls: 16           # cap for the heavy flows below
+  extended_call_flows: [audit, refine, rework, compose]   # Hugo-specific flow names
 
 context_window:
   max_input_tokens: 128000          # total input budget (model-dependent)

## self_review

WHAT CHANGED (exactly the 11 pre-justified files):

1. shared/shared_defaults.yaml — section header `resilience:` renamed `limits:`; five promoted keys appended flat (max_rounds 8, max_corrective 3, max_tool_calls 8, extended_tool_calls 16, extended_call_flows [audit, refine, rework, compose]); the orphan `recovery:` section (max_repair_attempts) deleted. Satisfies D1/D2/D3, R1-R3.
2. Hugo backend/modules/pex.py — `_MAX_ROUNDS`/`_MAX_CORRECTIVE` constants and their comment deleted; two public attributes read once in `__init__` via direct indexing (`config['limits']['max_rounds']` / `['max_corrective']`, D4-A, no .get defaults per R5); loop reads switched to `self.max_rounds` / `self.max_corrective`. Message constants untouched (R4).
3. Hugo backend/components/prompt_engineer.py — `self._resilience = config.get('resilience', {})` -> `self._limits = config['limits']` (required section, no .get per the D1 amendment); llm_retries read renamed (inner .get chain kept, rename only); the 3-line hardcoded call cap replaced by the D2-C two-liner reading both caps and the flow list from config (frozen yaml list is a tuple, `in` works).
4. Hugo schemas/config.py — `'resilience'` -> `'limits'` in _REQUIRED_SECTIONS.
5. Hugo utils/tests/conftest.py — minimal_config `'resilience': {}` -> `'limits': {five promoted keys}` so PromptEngineer's direct indexing works under the fixture.
6. Hugo utils/tests/pex_unit_tests.py — three new tests in TestOrchestratorLoop per the plan: T1 test_max_rounds_read_from_config (max_rounds=1 override, full limits section per the override-semantics caveat; proves the wire by draining the queue exactly to the forced wrap-up), T2 test_call_cap_read_from_config (captures max_num_calls: 16 for audit, 8 for find; also patches _model_family to 'claude' as the approved plan specified, needed because ACTIVE_FAMILY routes 'med' to gemini in this build), T3 test_recovery_keys_collapsed (pins the yaml: no recovery/resilience sections, values 2/8/3/8/16, tuple flow list). Plus one `load_config` import. Existing corrective-cap test at :483 untouched and passing — now exercises the config-fed value.
7-9. Dana — schemas/config.py required-section rename; prompt_engineer.py handle rename (`.get` style kept per amendment) at :57 and :114 plus the one-word section-divider comment ("Resilience config" -> "Limits config") that named the old section; test_ensemble.py fixture `'resilience': {}` -> `'limits': {}`.
10-11. Kalli — same surgical rename: schemas/config.py, prompt_engineer.py :55 and :97.

SCOPE ADHERENCE: 11 files exactly, matching the expected list. Behavior-preserving: values 8/3/8/16 unchanged, retry semantics untouched, no multiplier key, no code-side defaults on any promoted key, public attributes on PEX, messages stay code constants. Greps verified: zero `_MAX_ROUNDS|_MAX_CORRECTIVE` in Hugo *.py; zero `resilience` config references anywhere (survivors: the e2e_agent_evals.py prose comment and T3's own assertion string); zero `recovery:|max_repair_attempts` in the yaml; zero inline 'audit','refine','rework','compose' list in Hugo backend (lives in yaml + test fixtures only).

WORKTREE BASE NOTE: the worktree branch was created at fa49a89, four commits behind the main repo's HEAD cfe2040 (which contains round 4.2 + the eval-suite restructure the spec is written against). The worktree was clean, so I fast-forwarded it to cfe2040 (`merge --ff-only`, non-destructive) before editing; the diff above is against cfe2040.

TEST MAPPING: R1 -> T1 + T-existing(:483); R2 -> T2; R3/R5/R6-values -> T3; R6-suite -> full free suite 208 baseline -> 211 passed / 0 skipped / 0 failed. Dana + Kalli `load_config()` smoke checks pass ('Dana config OK' / 'Kalli config OK'), validating the renamed required section against the renamed yaml. No live/paid runs (no .env in the worktree) — the 8-scenario live E2E gate and trace check from spec §4.5.6-4.5.7 remain for QA.

PRE-EXISTING FAILURE FLAGGED (not dismissed — verified against baseline): Dana tests/test_ensemble.py::TestDetectFlow::test_disagreement_weighted fails identically (confidence 1.0 vs expected 0.80) in the UNTOUCHED main repo at cfe2040, so it predates this change set and is unrelated to it (it tests NLU vote weighting; my Dana edits touch only the retry-config handle, a fixture dict key, and a comment). Fixing Dana's NLU voting is outside the 11-file scope of this config round and would trip the diff-size guard; it needs its own ticket. All 19 other Dana ensemble tests pass, including the two that consume the renamed fixture.

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
211 passed, 1 warning in 1.86s
----- tests (deterministic): PASS (exit 0) -----

all requested levels passed
