# Round 4.5 handoff artifact — swe1 plan

Implementation plan verified against current source (all line numbers checked today).

# SWE2 Implementation Plan — Round 4.5: promote loop bounds to config, rename `resilience` → `limits`

## Edits (11 files, in build order)

**1. `shared/shared_defaults.yaml`** (:79-94)
- Rename section header `resilience:` → `limits:` (:79). Contents :80-91 unchanged.
- After `max_recovery_attempts: 2` (:91) append five flat keys:
  ```yaml
  max_rounds: 8                     # orchestrator acting-loop rounds per turn
  max_corrective: 3                 # consecutive failed tool calls before wrap-up
  max_tool_calls: 8                 # per-flow tool-call cap in tool_call
  extended_tool_calls: 16           # cap for the heavy Hugo flows below
  extended_call_flows: [audit, refine, rework, compose]   # Hugo-specific; other domains ignore
  ```
- Delete the `recovery:` section (:93-94) entirely.

**2. `assistants/Hugo/schemas/config.py`** (:21) — in `_REQUIRED_SECTIONS`, `'resilience'` → `'limits'`. Nothing else.

**3. `assistants/Hugo/backend/modules/pex.py`**
- Delete :19-22 (the two-line comment + `_MAX_ROUNDS = 8` + `_MAX_CORRECTIVE = 3`). Keep :23-27 messages.
- In `__init__` after `self.config = config` (:93), add:
  ```python
  self.max_rounds = config['limits']['max_rounds']
  self.max_corrective = config['limits']['max_corrective']
  ```
- :332 `range(_MAX_ROUNDS)` → `range(self.max_rounds)`; :374 `errors >= _MAX_CORRECTIVE` → `errors >= self.max_corrective`.

**4. `assistants/Hugo/backend/components/prompt_engineer.py`**
- :86 `self._resilience = config.get('resilience', {})` → `self._limits = config['limits']` (required section, direct index per D4).
- :135 `self._resilience.get('llm_retries', {})` → `self._limits.get('llm_retries', {})` (the inner `.get` stays — spec caveat: partial `limits` overrides must survive for llm_retries readers).
- :215-217 replaced by the D2-C two-liner:
  ```python
  extended = flow.name() in self._limits['extended_call_flows']
  max_num_calls = self._limits['extended_tool_calls' if extended else 'max_tool_calls']
  ```
  (Frozen config makes the flow list a tuple; `in` is unaffected.)

**5. `assistants/Hugo/utils/tests/conftest.py`** (:27) — `'resilience': {}` →
```python
'limits': {'max_rounds': 8, 'max_corrective': 3, 'max_tool_calls': 8,
           'extended_tool_calls': 16, 'extended_call_flows': ['audit', 'refine',
           'rework', 'compose']},
```

**6. `assistants/Hugo/utils/tests/pex_unit_tests.py`** — three new tests in `TestOrchestratorLoop` (details below). `test_consecutive_failures_cap_breaks_to_wrap_up` (:483) untouched — it now exercises the config-fed 3.

**7-9. Dana** — surgical rename only, keep existing `.get` style:
- `schemas/config.py:16` — `'resilience'` → `'limits'` in `_REQUIRED_SECTIONS`.
- `backend/components/prompt_engineer.py:57` — `self._resilience = config.get('resilience', {})` → `self._limits = config.get('limits', {})`; `:114` — `self._resilience.get(...)` → `self._limits.get(...)`.
- `tests/test_ensemble.py:52` — `'resilience': {}` → `'limits': {}`.

**10-11. Kalli** — same rename: `schemas/config.py:16`; `prompt_engineer.py:55` and `:97`. No Kalli test fixture references the section (grep-verified).

No other `resilience` readers exist repo-wide (grep-verified; `e2e_agent_evals.py:1043` is an English-prose comment, untouched).

## New tests (spec §4.5.8 T1-T3)

- **T1 `test_max_rounds_read_from_config`** — build an agent inline per the `orch_agent` pattern (monkeypatch `backend.agent.load_config` with `overrides={'debug': True, 'limits': {'max_rounds': 1, 'max_corrective': 3, 'max_tool_calls': 8, 'extended_tool_calls': 16, 'extended_call_flows': ['audit','refine','rework','compose']}}` — overrides replace whole sections, so the full five keys ride along); stub `nlu.understand`; script `[_response(_tool_block('read_state', {})), _response(_text_block('wrapped up'))]`. Assert message == 'wrapped up', `messages[-2]['content'] == _WRAP_UP_MESSAGE`, queue drained — proves the loop stopped after 1 round instead of the yaml 8.
- **T2 `test_call_cap_read_from_config`** — use the `engineer` fixture; monkeypatch `engineer._model_family` → `'claude'` and `engineer._call_claude_with_tools` → capture `max_num_calls`, return `('', [])`; call `tool_call` with `skill_prompt=''` and a real `audit` flow → captured 16, then a `find` flow → captured 8.
- **T3 `test_recovery_keys_collapsed`** — `cfg = load_config()`; assert `'recovery' not in cfg`, `'resilience' not in cfg`, `cfg['limits']['max_recovery_attempts'] == 2`, and the four promoted values are 8/3/8/16 with `extended_call_flows == ('audit','refine','rework','compose')`.

Per the prune bar: no attribute-equality test (`self.max_rounds == 8`) — T3 pins the yaml, T1/T2 test the wiring behaviorally.

## Verification (goal-driven)

1. Baseline (already stamped in spec): 208 passed / 0 skipped / 0 failed.
2. After edits — cwd `assistants/Hugo`: `python -m pytest utils/tests/nlu_unit_tests.py utils/tests/pex_unit_tests.py utils/tests/mem_unit_tests.py -q` → 211 passed / 0 skipped / 0 failed.
3. Dana and Kalli suites (cwd per assistant): `python -m pytest tests -q` each → green, proving the required-section rename + shared-yaml rename hold for both.
4. Greps, expecting zero hits: `_MAX_ROUNDS|_MAX_CORRECTIVE` in Hugo `*.py`; `resilience` anywhere in `assistants/` + `shared/` code/yaml (except the prose comment in `e2e_agent_evals.py`); `max_repair_attempts|recovery:` in `shared_defaults.yaml`; `'audit', 'refine', 'rework', 'compose'` in `assistants/Hugo/backend`.
5. Eval gate (§4.5.6, live, ≤10 min, cwd `assistants/Hugo`): `python utils/evals/run_evals.py --ids B01.C01,B01.C14,B02.C02,B02.C06,B02.C14,B03.C03,B03.C07,B03.C11` — exit 0, `completion_rate` ≥ 0.36 baseline; then the same ids at `--level traces` with `tool_match_rate` unchanged (identical budgets at temp 0 must reproduce dispatch trajectories).

## Scope notes

- Behavior-preserving: values 8/3/8/16 and the four-flow list unchanged; message strings stay code constants (R4); no `.get` defaults on the promoted keys (D4 — yaml is the sole declaration).
- Exactly the 11 pre-justified files; no new concepts beyond the `limits` rename; no config keys added beyond the five promoted ones.
- One design flag for DoE (SWE2 mandate): the Hugo handle `self._limits` keeps its underscore to match the sibling `self._models` style in the same `__init__`; the public-attribute rule is applied where the spec directs it (PEX's `max_rounds`/`max_corrective`). If DoE wants `self.limits` public too, it is a one-word change in file 4 only.
