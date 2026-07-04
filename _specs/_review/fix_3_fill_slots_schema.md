# Fix 3 — fill_slots schema violations on the gemini family

Status: FIXED 2026-07-03 (retry guardrail; PR #5 branch). Discovered live during fix_1/fix_2
verification. Owner module: **NLU** (slot-fill call path) + **PromptEngineer** (schema handling).

## What happened

On B03.C01 turn 1 the slot-fill call for `outline` returned `{'post': 'observability for LLM
apps'}` — a bare entity dict instead of the required `{reasoning, slots{...}}` shape. NLU's
guard caught it (`nlu.py` `[fill_slots] schema violation`) and dropped the payload, so the turn
survived but every slot value NLU extracted was silently lost; the policy then re-asks or guesses.

## Root cause

`_fill_slots` calls `self.engineer(prompt, 'fill_slots', ...)` with the default `model='med'`.
`ACTIVE_FAMILY = 'gemini'` (`prompt_engineer.py:41`), so `med` resolves to Gemini Flash preview,
and `_call_gemini` passes the schema as `config.response_json_schema`. The preview model does not
strictly enforce that field — it can emit JSON of a different shape. The anthropic path
(`output_config` json_schema) enforces; the gemini path is best-effort.

## The fix (shipped)

A one-retry guardrail in `nlu.py::_fill_slots`: on a shape violation, retry the same call once
before giving up (LLM output is exactly what guardrails are for — the violation is rare and a
second sample almost always conforms). The give-up path keeps the loud warnings.

## Follow-up options (not built)

- Route `fill_slots` to an enforcing family/model (e.g. the anthropic `nlu` override in
  `tools.yaml` — note `models.overrides.*.model_id` is currently NOT consulted by
  `PromptEngineer.__call__`, which resolves tiers only; wiring overrides into call sites is its
  own small design question).
- Re-check enforcement when `gemini-3-flash` leaves preview.

## Verify

Free suite green; live rerun of B03.C01 shows either no violation or a recovered retry
(`attempt=1` warning followed by a filled flow, not a dropped payload).
