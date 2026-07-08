# SWE2 plan — round 4.6 (per-call skill tier)

Orders echo: 1 Spec authoritative: implementing exactly, Option A. 2 Plain language: no banned
terms. 3 One short StructuredOutput call. 4 Surgical, no new concepts. 5 No branches/commits.

## Summary

Round 4.6 gives PromptEngineer.skill_call a per-call `model` arg (default 'med'), matching
tool_call. Three-line change in one method plus one new test. Verified against source: skill_call
hardcodes 'med' at prompt_engineer.py:190-191; tool_call already takes model:str='med' at :202.
The only two skill_call sites (research.py:46, :73) pass no model and use only earlier positional
args plus keyword skill_prompt, so a positional-last model arg breaks nothing. Adopting spec's
Option A: ship the capability only, touch no policy. Both named hard skills (audit/rework) already
route through tool_call, which already has the knob. Zero behavior change since default equals
today's hardcoded tier, so no live eval needed. Agrees with spec on every point.

## Placement

Edit prompt_engineer.py, method skill_call. Line 183: append `, model:str='med'` before
`) -> str:`. Line 190: `self._resolve_model('med')` to `self._resolve_model(model)`. Line 191:
`self._model_family('med')` to `self._model_family(model)`. Nothing else in the method changes.

Add one test to pex_unit_tests.py in class TestOrchestratorLoop, right after
test_call_cap_read_from_config (line 561), covering AC1+AC2:

```python
def test_skill_call_honors_model_tier(self, engineer, monkeypatch):
    seen = []
    monkeypatch.setattr(engineer, '_resolve_model', lambda model: seen.append(model))
    monkeypatch.setattr(engineer, '_model_family', lambda model: 'gemini')
    monkeypatch.setattr(engineer, '_call_gemini', lambda *a, **k: '')
    engineer.skill_call(flow_classes['find'](), '', {}, skill_prompt='', model='high')
    engineer.skill_call(flow_classes['find'](), '', {}, skill_prompt='')
    assert seen == ['high', 'med']
```

Fixtures exist: engineer at conftest.py:116, flow_classes imported at line 20. AC3: run
pex_unit_tests.py + model_tests.py from assistants/Hugo cwd.

## Risks

None material. Default 'med' preserves current behavior for both research.py callers;
positional-last placement is call-safe. No new concept: `model` tier already public on
tool_call/__call__/stream. One flag on the spec, as agreement not deviation: no skill_call site
needs 'high' this round, so the arg ships unexercised by real traffic; the actual hard skills
already have the knob via tool_call. If a live eval is wanted despite no behavior change, that is
extra cost with nothing to detect.
