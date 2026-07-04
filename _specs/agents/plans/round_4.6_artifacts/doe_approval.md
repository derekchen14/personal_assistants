# DoE approval — round 4.6 (per-call skill tier)

Orders echo: 1 Spec at _specs/agents/plans/round_4.6_spec.md is authoritative; implement exactly,
flag disagreements only in notes. 2 Plain language ban list applies. 3 One short StructuredOutput;
work product in files; string fields under 150 words. 4 CLAUDE.md rules: simplicity first,
surgical changes, no defensive programming, trimmed param style, 100-char lines, no new concepts.
5 No branches, no PRs, never git commit/push — orchestrator commits to master.

## Verdict

Both plans APPROVED; they match the spec and each other in substance. All line references verified
against source: skill_call 181-183, hardcoded 'med' 190-191, tool_call model= 202, sole call sites
research.py:46/:73 (no model passed, positional-last is safe), engineer fixture conftest.py:116,
flow_classes import line 20. Both adopt Option A (capability only, no policy edits) — agreement
with spec, not deviation. SWE2 is the build basis: its test code is concrete, verified runnable,
and covers AC1+AC2 in one assert (seen == ['high','med']). Minor harmless detail: SWE2's
_resolve_model stub returns None as model_id; fine since _call_gemini is stubbed. No banned
language, no placeholders, no live eval needed.

## Ponytail review

- +1 signature arg model:str='med' — spec-required, reuses tool_call's existing public tier arg,
  no new concept
- +1 two resolution lines pass model through — that is the entire feature
- +1 single test covers AC1+AC2 with one seen==['high','med'] assert — lazier than two tests
- +1 Option A: zero policy edits; hard skills already reach the tier knob via tool_call, so wiring
  'high' now would be speculative
- +1 no live eval: default equals the old hardcoded tier, so there is nothing for a paid E2E run
  to detect
- 0 nothing to delete in the touched method; no bloat introduced anywhere
- Net: +5 — a 3-line code diff plus one ~8-line test; minimal and complete

## Direction to builders

Build SWE2's plan. Edit only skill_call in assistants/Hugo/backend/components/prompt_engineer.py:
line 183 append `, model:str='med'` after `user_text:str|None=None`; line 190
`self._resolve_model(model)`; line 191 `self._model_family(model)`. Touch nothing else — no
tool_call, _resolve_model, _model_family, config, docstrings, or policies (Option A). Add
test_skill_call_honors_model_tier to TestOrchestratorLoop in
assistants/Hugo/utils/evaluation_suite/_tests/pex_unit_tests.py, inserted after line 560. Verify:
run pex_unit_tests.py and model_tests.py with cwd assistants/Hugo; all green, no new skips; no
live eval.
