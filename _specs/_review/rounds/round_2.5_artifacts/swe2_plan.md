# Round 4.5 handoff artifact — swe2 plan

# Implementation Plan — Round 4.5: promote PEX loop bounds + call caps to config, rename `resilience` → `limits`

Verified against current source (all line refs checked today). Grep confirms the complete reader set of `resilience` is exactly the 11 expected files (plus one prose comment in `e2e_agent_evals.py:1043` — the English word, not a config read; untouched). No domain `tools.yaml` defines `resilience`; no existing `limits` key anywhere; the two dead recovery keys have zero Python readers. `pex_unit_tests.py` imports message constants only, never `_MAX_ROUNDS`/`_MAX_CORRECTIVE`.

## Edits (11 files)

**1. `shared/shared_defaults.yaml`** (:79-94)
- Rename section header `resilience:` → `limits:` (:79). Contents `tool_retries`, `llm_retries`, `fallback_model`, `max_recovery_attempts` unchanged.
- Append five flat keys to the section:
  ```yaml
  max_rounds: 8                     # orchestrator acting-loop rounds (was pex.py _MAX_ROUNDS)
  max_corrective: 3                 # consecutive failed tool calls before wrap-up (was _MAX_CORRECTIVE)
  max_tool_calls: 8                 # per-flow tool-call cap (was prompt_engineer.py:215)
  extended_tool_calls: 16           # cap for the heavy flows below
  extended_call_flows: [audit, refine, rework, compose]   # Hugo-specific flow names
  ```
- Delete lines 93-94 (`recovery:` / `max_repair_attempts: 2`) outright.

**2. `assistants/Hugo/backend/modules/pex.py`**
- Delete :19-22 (both comment lines + `_MAX_ROUNDS` + `_MAX_CORRECTIVE`). Keep :23-27 (three message constants, R4).
- In `__init__` after `self.config = config` (:93), add two public attributes, direct indexing (D4-A):
  ```python
  self.max_rounds = config['limits']['max_rounds']
  self.max_corrective = config['limits']['max_corrective']
  ```
- :332 `range(_MAX_ROUNDS)` → `range(self.max_rounds)`; :374 `errors >= _MAX_CORRECTIVE` → `errors >= self.max_corrective`.

**3. `assistants/Hugo/backend/components/prompt_engineer.py`**
- :86 `self._resilience = config.get('resilience', {})` → `self._limits = config['limits']` (required section, no `.get` per D1 amendment).
- :135 `self._resilience.get('llm_retries', {})` → `self._limits.get('llm_retries', {})` (inner `.get` chain kept — rename only).
- :215-217 replaced by the D2-C two-liner (config is deep-frozen so the yaml list is a tuple; `in` works):
  ```python
  extended = flow.name() in self._limits['extended_call_flows']
  max_num_calls = self._limits['extended_tool_calls' if extended else 'max_tool_calls']
  ```

**4. `assistants/Hugo/schemas/config.py`** — :21 `'resilience'` → `'limits'` in `_REQUIRED_SECTIONS`. Nothing else.

**5. `assistants/Hugo/utils/tests/conftest.py`** — :27 `'resilience': {}` → the five promoted keys (line-wrapped under 100 chars):
```python
'limits': {'max_rounds': 8, 'max_corrective': 3, 'max_tool_calls': 8,
           'extended_tool_calls': 16, 'extended_call_flows': ['audit', 'refine', 'rework', 'compose']},
```

**6. `assistants/Hugo/utils/tests/pex_unit_tests.py`** — three new tests (below); no edits to existing tests. `test_consecutive_failures_cap_breaks_to_wrap_up` (:483) untouched — it becomes the config-fed regression alarm for `max_corrective`.

**7-8. Dana** — `schemas/config.py:16` `'resilience'` → `'limits'`; `backend/components/prompt_engineer.py:57` → `self._limits = config.get('limits', {})` (keep `.get` — existing style), `:114` `self._resilience` → `self._limits`. Nothing else.

**9. Dana `tests/test_ensemble.py:52`** — `'resilience': {}` → `'limits': {}` (stays empty; Dana only reads `llm_retries` via `.get` chains).

**10-11. Kalli** — same surgical rename: `schemas/config.py:16`, `prompt_engineer.py:55` and `:97`.

## New tests (`pex_unit_tests.py`, class `TestOrchestratorLoop` per spec)

- **T1 `test_max_rounds_read_from_config`** — `orch_agent` pattern but with `monkeypatch.setattr('backend.agent.load_config', lambda: load_config(overrides={'debug': True, 'limits': {'max_rounds': 1, 'max_corrective': 3, 'max_tool_calls': 8, 'extended_tool_calls': 16, 'extended_call_flows': ['audit', 'refine', 'rework', 'compose']}}))` (full section — `overrides` replaces whole top-level keys; `llm_retries` readers survive via `.get`). Script: one successful tool round, then a text response for the forced wrap-up. Assert the reply is the wrap-up text and `messages[-2] == {'role': 'user', 'content': _WRAP_UP_MESSAGE}` — proves the loop stopped after 1 round. A dead config wire silently keeps 8 and the test fails (queue not drained to wrap-up).
- **T2 `test_call_cap_read_from_config`** — `engineer` fixture (`PromptEngineer(minimal_config)`, anthropic default → claude family). Monkeypatch `_call_claude_with_tools` to capture its `max_num_calls` arg and return `('', [])`. Call `tool_call` with a real `AuditFlow` (extended) then a real `FindFlow` (base), passing `skill_prompt='test'` to bypass template loading. Assert captured caps are 16 then 8.
- **T3 `test_recovery_keys_collapsed`** — `cfg = load_config()`; assert `'recovery' not in cfg` and `'resilience' not in cfg`; `cfg['limits']['max_recovery_attempts'] == 2`; the four numeric keys carry 8/3/8/16 and `cfg['limits']['extended_call_flows'] == ('audit', 'refine', 'rework', 'compose')` (tuple — frozen).

No test asserts `agent.pex.max_rounds == 8` (prune bar: T3 pins the yaml, T1/T2 pin the wiring by behavior).

## Verification

1. Baseline: `python -m pytest utils/tests/nlu_unit_tests.py utils/tests/pex_unit_tests.py utils/tests/mem_unit_tests.py -q` (cwd = `assistants/Hugo`) — confirm 208/0/0 before touching anything.
2. Apply edits; rerun — expect 211 passed / 0 skipped / 0 failed.
3. Greps (all expected zero hits): `_MAX_ROUNDS|_MAX_CORRECTIVE` in Hugo `*.py`; `resilience` in any `*.py` under `assistants/` + `shared/` (except the e2e_agent_evals prose comment); `recovery:|max_repair_attempts` in `shared_defaults.yaml`; `'audit', 'refine', 'rework', 'compose'` in `assistants/Hugo/backend`.
4. Dana/Kalli import smoke: `python -c "from schemas.config import load_config; load_config()"` with cwd set to each assistant dir (validates the renamed required section against the renamed yaml).
5. E2E gate (live, QA co-reads): `python utils/evals/run_evals.py --ids B01.C01,B01.C14,B02.C02,B02.C06,B02.C14,B03.C03,B03.C07,B03.C11` from `assistants/Hugo` — exit 0, `completion_rate` ≥ 0.36 baseline; then the same ids at `--level traces` — `tool_match_rate` unchanged.

Scope notes: 11 files exactly; behavior-preserving (values 8/3/8/16, retry semantics untouched); no new concepts beyond the `limits` rename; message strings stay code constants; no `.get` defaults on any promoted key.
