# SWE1 build — round 4.6 (per-call skill tier)

Orders echo: Base dbc2b00 checked out; spec followed exactly (Option A); only skill_call
signature + 2 resolution lines edited; test added; plain language + surgical + no branches/commits
honored.

Diff stat:

```
 assistants/Hugo/backend/components/prompt_engineer.py          |  6 +++---
 .../Hugo/utils/evaluation_suite/_tests/pex_unit_tests.py       | 10 ++++++++++
 2 files changed, 13 insertions(+), 3 deletions(-)
```

Notes: skill_call now takes model:str='med' (last positional, mirroring tool_call); lines 190-191
resolve via `model` instead of hardcoded 'med'. No policy/tool_call/config/docstring touched
(Option A). Added test_skill_call_honors_model_tier to TestOrchestratorLoop asserting
seen==['high','med']. Ran pex_unit_tests.py + model_tests.py from assistants/Hugo cwd: 139
passed, 0 skips, no live eval. Both edited files parse. Note: DoE directed the test into
utils/evaluation_suite/_tests/, which is outside the backend-only line; followed DoE/spec as
authoritative. No behavior change for current callers since default matches prior hardcoded tier.
