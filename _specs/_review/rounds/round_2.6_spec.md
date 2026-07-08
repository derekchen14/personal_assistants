# Round 2.6 Spec — Per-call skill tier

**Master Plan step:** round_2_pex.md §2.6 (`_specs/_review/round_2_pex.md:161-172`).

## What changes

`PromptEngineer.skill_call` hardcodes the `'med'` tier at `prompt_engineer.py:190-191`, while its sibling
`tool_call` already takes `model:str='med'` (`:202`) and resolves per call. Give `skill_call` the same
per-call `model` arg (default `'med'`), so a policy can request `'high'` for a hard skill. Behavior is
unchanged for every current caller because the default matches today's hardcoded value.

Exact edit (from the plan, verified against source):

```python
def skill_call(self, flow, convo_history:str, scratchpad:dict, skill_name:str|None=None,
               skill_prompt:str|None=None, resolved:dict|None=None, max_tokens:int=1024,
               user_text:str|None=None, model:str='med') -> str:
    ...
    model_id = self._resolve_model(model)      # was _resolve_model('med')
    match self._model_family(model):           # was _model_family('med')
```

Both the `_resolve_model` and the `_model_family` call on lines 190-191 take `model`. `model` is the last
positional arg, matching `tool_call`'s signature order, so no existing keyword call breaks.

## Required call-outs (README §"Presenting a plan")

1. **New concepts:** none. `model` (`'low'`/`'med'`/`'high'`) already exists as a public arg on `tool_call`
   and `__call__`; this reuses it. No new field, class, config key, or term.
2. **Big decisions:** none. The plan pins the signature and the default. The only judgment call is the one
   below, and it resolves to "no code change beyond the capability."
3. **Alternatives:** the one open question (below) is stated with two fleshed options and a recommendation.

## Decision: does any current flow get `'high'` this round?

**Question:** the plan hints "a policy can request `'high'` for a hard skill." The two hard skills the roadmap
names — `audit` and `rework` — already run through `llm_execute` → `tool_call`, which already accepts `model=`
(revise.py:191, :234, :269). The only two `skill_call` sites are `research.find_policy` (research.py:46) and
`research.summarize_policy` (research.py:73) — a tag lookup blurb and a post summary, neither a hard skill.

- **Option A — ship capability only (recommended).** Add the arg; touch no call site. Zero behavior change,
  zero eval movement, smallest diff. Pro: matches the plan's "so a policy *can* request `'high'`" wording;
  no risk to existing evals. Con: the new arg has no in-repo user yet, so it is unexercised by real traffic.
- **Option B — also set `summarize_policy` to `model='high'`.** Pro: gives the arg a live user; longer posts
  might summarize better on the high tier. Con: this is a behavior change with cost/latency impact that the
  plan did not ask for and no eval currently measures; it turns a no-op round into one needing the live gate.
  It also contradicts "surgical changes — every changed line traces to the request."

**Recommendation: Option A.** The two `skill_call` sites are not hard skills; the hard skills already have the
knob via `tool_call`. Shipping capability only keeps this a no-behavior-change round. If a skill_call site
later proves it needs `'high'`, that is a separate, measurable change.

## Scope

- Edit: `prompt_engineer.py:181-191` — signature + the two resolution lines. One method, ~3 lines.
- Do **not** touch: any policy, `tool_call`, `_resolve_model`, `_model_family`, config, or docstrings beyond
  what the signature demands.

## Acceptance criteria → tests

All in `utils/evaluation_suite/_tests/pex_unit_tests.py` (free suite, no LLM).

| # | Criterion | Test | Expected |
|---|---|---|---|
| AC1 | `skill_call` accepts `model=` and routes it to `_resolve_model` | new `test_skill_call_honors_model_tier`: monkeypatch `_resolve_model` to record its arg, call `skill_call(..., model='high')` (stub the family branch), assert recorded arg is `'high'` | passes |
| AC2 | Default is unchanged | same test, call `skill_call(...)` with no `model`, assert recorded arg is `'med'` | passes |
| AC3 | No caller regressed | existing suite: `pex_unit_tests.py` + `model_tests.py` | all green, no new skips |

`skill_call`'s branch bodies call live providers, so AC1/AC2 stub or monkeypatch `_resolve_model` (and short
the `match` family branch) rather than hitting a model — same isolation style as the existing tool-cap test at
`pex_unit_tests.py:558`.

## Verification plan

- **Free suite only.** Run `pex_unit_tests.py` and `model_tests.py` from the `assistants/Hugo` cwd (imports
  resolve to the wrong backend otherwise — see MEMORY test-cwd note).
- **Live gate: not needed.** With Option A the default is `'med'`, identical to the current hardcoded tier, so
  no prompt, model, or output changes. There is nothing for an E2E eval to detect. A no-behavior-change round
  does not warrant a paid live run.

## Notes / risks

- The plan's `'high'` hint is satisfied for the actual hard skills (audit/rework) by `tool_call`'s existing
  `model=` — no `skill_call` site needs the upgrade today. Flagging this as agreement with the plan, not a
  deviation: the round ships the capability, exactly as §2.6 states.
- `model` is positional-last to match `tool_call`; every current `skill_call` invocation uses only the earlier
  args, so ordering is safe.
