# Round 3.1 QA verdict

Base for the diff: `a2445f6`. All deterministic tests run from `assistants/Hugo` with pytest.

## Verdict table

| # | Criterion | Pass/fail | Evidence |
|---|---|---|---|
| 1 | Pre-pass removed: `predict` skips `_classify_intent` on a confident single-intent detection | PASS | `nlu.py` `predict` now runs `_detect_flow` first and only calls `_classify_intent` inside the `_intent_split` branch. `test_predict_skips_classify_on_confident_detection` passes. |
| 2 | Tie-break retained: low-confidence cross-intent detection escalates to classify + narrowed re-detect | PASS | `test_predict_escalates_on_low_conf_cross_intent`, `test_intent_split_true_when_flows_span_intents_and_low_conf`, `test_intent_split_false_when_confident`, `test_intent_split_false_when_single_intent` all pass. |
| 3 | `_classify_intent` still callable | PASS | `test_classify_intent_still_callable` passes; method body untouched. |
| 4 | Empty-hint detection works, no crash from `get_prompt('')` | PASS | `test_candidate_names_empty_hint_is_full_catalog` and `test_generic_flow_prompt_used_when_no_hint` pass. `get_prompt` in `experts/__init__.py` returns `GENERIC_FLOW_PROMPT` when `intent` is falsy. |
| 5 | Hint narrows candidate list to one intent + edges | PASS | `test_candidate_names_hint_narrows_to_intent` passes. |
| 6 | Prompt guidance rewritten: no "ALREADY classified", new Plan/Clarify bias text present | PASS | `grep -n "ALREADY classified" backend/prompts/for_orchestrator.py` returns nothing (exit 1). The replacement sentence with "bias toward Plan or Clarify" is present at `for_orchestrator.py:36`. `TOOL_POLICY` changed "classified `intent`" to "detected `intent`". |
| 7 | No detection regression on the 8 sampled scenarios (`state`/`correctness`/`completion`/`planning`/`ambiguity`) | NEEDS LIVE | `run_evals.py` runs the live orchestrator Agent (paid). Not run per task instructions. See needs_live. |
| 8 | Free suite green, zero skips: `nlu_unit_tests.py`, `model_tests.py`, `pex_unit_tests.py`, `mem_unit_tests.py` | PARTIAL PASS | `nlu_unit_tests.py`: 57 passed, 0 skipped. `pex_unit_tests.py` + `mem_unit_tests.py`: 179 passed, 0 skipped (236 total across the three, 0 skips). `model_tests.py` is a live-call accuracy script (its own docstring: "makes live model calls (paid), so it is not part of the free default run") — it has no pytest cases to collect and was not run per task instructions. See needs_live. |
| 9 | Net simplification: one fewer LLM call on the default path, no `_intent_candidates` helper added | PASS | `grep -rn "_intent_candidates" backend/ utils/` returns no matches. `predict` diff shows the unconditional classify call replaced by a conditional one inside `_intent_split`. |

## Test plan cross-check

- `nlu_unit_tests.py:71-112` — the three existing detection tests renamed `intent=` to `hint=`, confirmed
  in the diff.
- New `TestPredictDispatch` class added directly after `TestEnsembleVoting`, containing all 8 named
  tests from the spec's test plan table, matching the table's setup and expected results.
- No `_intent_candidates` helper, no belief-path rewrite, no new edge-flow helper — all confirmed by
  reading the diffs (`nlu.py`, `experts/__init__.py`, `for_orchestrator.py`).
- `understand`/`think` signatures unchanged (D3-A) — confirmed by reading `nlu.py:85` and `nlu.py:101`;
  neither takes a `hint` parameter.
- `build_flow_prompt` needed no code change: it already had `rules_body = rules if rules else
  PRECEDENCE_NOTE` before this round, and `GENERIC_FLOW_PROMPT['rules'] = ''` uses that existing
  fallback rather than adding new logic.

## Test runs

```
python -m pytest utils/evaluation_suite/_tests/nlu_unit_tests.py -q
57 passed, 1 warning in 0.11s

python -m pytest utils/evaluation_suite/_tests/pex_unit_tests.py utils/evaluation_suite/_tests/mem_unit_tests.py -q
179 passed, 1 warning in 2.13s

python -m pytest utils/evaluation_suite/_tests/nlu_unit_tests.py utils/evaluation_suite/_tests/pex_unit_tests.py utils/evaluation_suite/_tests/mem_unit_tests.py -q -rs
236 passed, 1 warning in 2.26s, 0 skipped
```

The one warning in each run is an unrelated third-party deprecation warning from
`google/genai/types.py` (Python 3.14 vs an older `_UnionGenericAlias` use), not related to this
change.

## needs_live

- Criterion 7 (8-scenario before/after eval check via `run_evals.py`) — makes live orchestrator
  Agent calls, not run.
- Criterion 8's `model_tests.py` portion — the script itself makes live model calls to score
  flow-detection accuracy against the corpus; it has no offline pytest path, not run.
- Trace check (`run_traces.py --ids B01.C01,B03.C05,B01.C08`) — makes live orchestrator Agent
  calls, not run.

## Summary

Every deterministic criterion in scope (1, 2, 3, 4, 5, 6, 8's non-live suites, 9) passes. The code
matches the spec's D1-A/D2-A/D3-A decisions exactly: `_intent_split` tie-break, `hint` rename across
`predict`/`_detect_flow`/`_flow_candidate_names`/`_detect_flow_prompt`, `GENERIC_FLOW_PROMPT` reusing
the existing `PRECEDENCE_NOTE` fallback, the orchestrator prompt rewrite, no `_intent_candidates`
helper, no `understand`/`think` signature change. The two criteria that need a live LLM (7, and the
`model_tests.py` half of 8) are not evaluated here.
