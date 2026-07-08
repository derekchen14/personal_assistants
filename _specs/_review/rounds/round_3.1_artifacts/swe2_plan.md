# SWE2 Implementation Plan — Round 3.1 (Intent model rework)

Base commit `a2445f6`. Scope is only §3.1 with the signed-off decisions **D1-A, D2-A, D3-A**.
SWE2 mandate: build the clean end-state, flag where the literal spec text would accrue debt.

## Required call-outs

**New concepts.** One new private method `NLU._intent_split(detection)` (a boolean test over data
that already exists). One new prompt constant pair in `backend/prompts/for_experts.py`
(`GENERIC_FLOW_INSTRUCTIONS`, `GENERIC_FLOW_EXAMPLES`) plus an empty-`intent` branch in
`build_flow_prompt`. No new classes, config keys, state fields, or files.

**Big decisions.** All three are already signed off: D1-A (empty hint -> full catalog + a generic
flow prompt), D2-A (tie-break condition verbatim), D3-A (thread `hint` only on the detection methods
that consume it). I add nothing to those.

**One normative deviation from the spec's literal draft (flag for DoE).** The spec D1-A draft puts
`GENERIC_FLOW_PROMPT` inside `backend/prompts/experts/__init__.py` and has `get_prompt` return it.
That path forces a **circular import**: `__init__.py` would need `PRECEDENCE_NOTE`, which lives in
`for_experts.py`, and `for_experts.py` already imports `get_prompt` from `experts/__init__.py` at
module top. Importing `experts` mid-initialization would fail. Clean fix: keep the generic branch in
`for_experts.py`, next to the other shared constants (`BACKGROUND_STATIC`, `PRECEDENCE_NOTE`,
`INTENT_INSTRUCTIONS`, `INTENT_EXAMPLES`), and leave `get_prompt` as a pure registry lookup. Same
behavior, no dead default in `get_prompt`, no import cycle. This is the SWE1/SWE2 divergence point I
expect; SWE1 likely follows the literal draft.

## Change order

### 1. `backend/prompts/for_experts.py` — generic empty-hint flow prompt (D1)

Add two module-level constants after `INTENT_EXAMPLES` (near line 301):

```python
GENERIC_FLOW_INSTRUCTIONS = (
    'Choose the single flow that best matches what the user wants across ALL intents. The '
    'candidate list spans every flow; the detected flow fixes the intent, so do not pre-commit '
    'to one intent family.'
)
GENERIC_FLOW_EXAMPLES = '''<positive_example> ... </positive_example>'''
# 6 cross-intent <positive_example> blocks, one per flow-owning intent
# (Research/Draft/Revise/Publish/Converse/Plan). Same shape as INTENT_EXAMPLES blocks but the
# Output is a flow_name+confidence object, e.g.
#   {"reasoning": "...", "flow_name": "release", "confidence": 0.82}
# Utterances mimic datasets/train.jsonl phrasing (short, implicit); no Kitty Hawk topic.
```

Edit `build_flow_prompt` (line 375) so an empty `intent` skips `get_prompt`:

```python
def build_flow_prompt(user_text, intent, convo_history, candidate_catalog, active_post=None):
    if intent:
        prompt_fields = get_prompt(intent)
        instructions = prompt_fields['instructions'].strip()
        rules = prompt_fields['rules'].strip() or PRECEDENCE_NOTE
        examples = prompt_fields['examples'].strip()
    else:
        instructions, rules, examples = (
            GENERIC_FLOW_INSTRUCTIONS, PRECEDENCE_NOTE, GENERIC_FLOW_EXAMPLES)
    task_body = f'{BACKGROUND_STATIC}\n\n## Instructions\n\n{instructions}\n\n## Rules\n\n{rules}'
    ...  # rest unchanged
```

`_render_input` already omits the `Predicted intent:` line when `intent` is falsy — no change there.
`get_prompt` and `experts/__init__.py` are left untouched. Satisfies test 4
(`test_generic_flow_prompt_used_when_no_hint`) and acceptance §4.

### 2. `backend/modules/nlu.py` — detect-first `predict`, tie-break, `hint` rename (3.1.1 + 3.1.3)

- **`predict`** (line 261) — detect first; classify only on a low-confidence cross-intent split:

```python
def predict(self, user_text:str, hint:str='') -> dict:
    detection = self._detect_flow(user_text, hint)
    if self._intent_split(detection):
        intent = self._classify_intent(user_text)
        detection = self._detect_flow(user_text, hint=intent)
    return {'flow_name': detection['flow_name'], 'confidence': detection['confidence'],
            'pred_flows': detection.get('pred_flows', [])}
```

- **`_intent_split`** — new method right after `predict`. Reads existing data only, direct indexing
  (every pred_flows name is guaranteed in FLOW_CATALOG by `_detect_flow`/`_tally_votes`), no `.get`:

```python
def _intent_split(self, detection:dict) -> bool:
    """True only when the ranked flows span >1 intent AND top-1 sits under the confidence floor —
    the single case where a coarse-intent tie-break earns its extra call. Under D1-A the span
    clause is almost always true, so the confidence floor is the real trigger."""
    intents = {FLOW_CATALOG[f['flow_name']]['intent'] for f in detection['pred_flows']}
    return len(intents) > 1 and detection['confidence'] < self.ambiguity.confidence_min
```

- **`_detect_flow`** (line 323) — signature `intent:str|None=None` -> `hint:str=''`; pass `hint`
  into `_detect_flow_prompt` and `_flow_candidate_names`. Body logic otherwise unchanged.
- **`_detect_flow_prompt`** (line 270) — signature `intent:str` -> `hint:str`; pass `hint` to
  `_flow_candidate_names(hint)` and `build_flow_prompt(user_text, hint, ...)`.
- **`_flow_candidate_names`** (line 362) — signature `intent:str|None` -> `hint:str=''`; change the
  empty test from `if intent is None` to `if not hint`; the non-empty branch is byte-identical:

```python
def _flow_candidate_names(self, hint:str='') -> list[str]:
    if not hint:
        return list(FLOW_CATALOG)
    edges = _get_edge_flows_for_intent(hint)
    return [name for name, cat in FLOW_CATALOG.items() if cat['intent'] == hint or name in edges]
```

- **Keep** `_classify_intent`, `build_intent_prompt`, `_intent_schema` as-is (tie-break +
  contemplate still use them). **`think`/`understand` unchanged** (D3-A) — `think` calls
  `self.predict(user_text)`, defaulting `hint=''`.

Satisfies acceptance §1, §2, §3, §5, §9 and tests
`test_predict_skips_classify_on_confident_detection`,
`test_predict_escalates_on_low_conf_cross_intent`, the three `test_intent_split_*`,
`test_classify_intent_still_callable`, `test_candidate_names_empty_hint_is_full_catalog`,
`test_candidate_names_hint_narrows_to_intent`.

### 3. `backend/prompts/for_orchestrator.py` — PEX System-1 guidance (3.1.2, prose only)

- Header comment (lines 26-27): replace with a note that NLU detects the flow and the flow fixes the
  intent; PEX reads it from belief.
- `INTENT_TAXONOMY` (lines 31-36): replace the "NLU ... has ALREADY classified ... ACT on that
  detection, not to re-classify it" sentence with the spec's draft — PEX forms a quick intent sense
  while reasoning, never writes belief, reads NLU's authoritative intent, and leans Plan/Clarify when
  unsure.
- `TOOL_POLICY` (line 52): change "the classified `intent`" to "the detected `intent`". No other
  edit.

Satisfies acceptance §6 (grep finds no `ALREADY classified`; finds the new bias text).

### 4. `utils/evaluation_suite/_tests/nlu_unit_tests.py` — rename + new tests

- Mechanical rename at lines 81, 94, 109: `_detect_flow('...', intent='...')` ->
  `_detect_flow('...', hint='...')`.
- Add the 8 model unit tests from the spec table near `TestEnsembleVoting`, plus the one prompt test
  `test_generic_flow_prompt_used_when_no_hint`. Patterns: spy `_classify_intent`
  (`MagicMock`), mock `_detect_flow` return values, assert call counts and the escalation
  re-detect uses `hint='Draft'`. `_intent_split` tests build a `detection` dict directly and assert
  the boolean.

## Verification (I run offline only; live evals belong to the orchestrator post-build)

- `cd assistants/Hugo && python -m pytest utils/evaluation_suite/_tests/nlu_unit_tests.py
  utils/evaluation_suite/_tests/model_tests.py utils/evaluation_suite/_tests/pex_unit_tests.py
  utils/evaluation_suite/_tests/mem_unit_tests.py` — all green, zero skips (acceptance §8).
- Grep `for_orchestrator.py` for `ALREADY classified` (expect none) and the new bias text.
- Trace + E2E eval checks (`run_traces.py --ids B01.C01,B03.C05,B01.C08`; the 8 sampled scenarios
  before/after) are the orchestrator's to run — noted for the handoff, not run by me.

## Files touched

1. `assistants/Hugo/backend/prompts/for_experts.py`
2. `assistants/Hugo/backend/modules/nlu.py`
3. `assistants/Hugo/backend/prompts/for_orchestrator.py`
4. `assistants/Hugo/utils/evaluation_suite/_tests/nlu_unit_tests.py`

`experts/__init__.py` deliberately NOT touched (see the normative deviation above).
