# SWE1 plan — round 4.6 (per-call skill tier)

Orders echo: Spec authoritative: implement §4.6 exactly. Plain language kept. One short
StructuredOutput. No new concepts. No branches/commits.

## Summary

Plan only, nothing edited. Round 4.6 gives PromptEngineer.skill_call a per-call model:str='med'
arg matching tool_call, so a policy can request 'high' for a hard skill. Default 'med' equals
today's hardcoded tier, so behavior is unchanged for every current caller. Confirmed the only two
skill_call sites (research.py:46 and :73) pass just the earlier args, so appending model as the
last positional arg is safe. Agrees with the spec's Option A: ship the capability, touch no policy
this round. Both named hard skills (audit, rework) already reach the tier knob through tool_call;
neither skill_call site (tag-lookup blurb, post summary) is a hard skill. One isolated test plus
the existing free suite covers the acceptance criteria without a live model call.

## Placement

prompt_engineer.py, skill_call signature (lines 181-183): append model:str='med' as the last
param, after user_text:str|None=None. Line 190: _resolve_model('med') → _resolve_model(model).
Line 191: _model_family('med') → _model_family(model). No other lines in that method change; do
not touch tool_call, _resolve_model, _model_family, config, or docstrings. Test: add
test_skill_call_honors_model_tier in TestOrchestratorLoop right after
test_call_cap_read_from_config (~line 560) in pex_unit_tests.py, using the engineer fixture +
monkeypatch. Monkeypatch _resolve_model to record its arg (return dummy id), _model_family to
return 'gemini', _call_gemini to return ''. Assert recorded=='high' when model='high';
recorded=='med' with no model arg. Run pex_unit_tests.py + model_tests.py from assistants/Hugo cwd.

## Risks

Low risk. model is positional-last, so no keyword call reorders. The two skill_call sites use only
earlier args; verified. No behavior change since default matches the old hardcoded 'med', so no
live eval needed. Only judgment call (does any flow get 'high' now) resolves to no, matching the
spec.
