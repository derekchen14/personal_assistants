# SWE2 build — round 4.6 (per-call skill tier)

Orders echo: Base reset to dbc2b00 (was 8875217); spec implemented exactly (Option A, capability
only); only Hugo backend + Hugo-own utils test touched; plain language respected; no
branch/commit/PR.

Diff stat:

```
 assistants/Hugo/backend/components/prompt_engineer.py          |  6 +++---
 .../Hugo/utils/evaluation_suite/_tests/pex_unit_tests.py       | 10 ++++++++++
 2 files changed, 13 insertions(+), 3 deletions(-)
```

Notes: skill_call now takes model:str='med' as last positional arg (matches tool_call order);
lines 190-191 pass `model` to _resolve_model/_model_family instead of hardcoded 'med'. Default
preserves current behavior for both call sites (research.find/summarize). No policy, tool_call,
config, or docstring changes (Option A per spec). Added test_skill_call_honors_model_tier to
TestOrchestratorLoop, monkeypatching _resolve_model/_model_family/_call_gemini; asserts
seen==['high','med']. Ran pex_unit_tests.py + model_tests.py from assistants/Hugo cwd: 139
passed, no skips. One flag: the DoE said "NEVER utils/" yet also directed the test into
assistants/Hugo/utils/... — read that ban as the top-level repo utils/, not Hugo's own utils/,
matching the spec's stated test location.
