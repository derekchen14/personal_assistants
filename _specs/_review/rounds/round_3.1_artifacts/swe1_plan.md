# SWE1 Implementation Plan — Round 3.1 (Intent model rework)

Base commit `a2445f6`. Decisions: D1-A, D2-A, D3-A. Scope is only §3.1. Optimize for smallest diff and
maximal reuse.

## New concepts (required call-out)

- **No new components, classes, config keys, or state fields.**
- One new private method `NLU._intent_split(detection)` — a boolean tie-break test over existing data.
- One renamed parameter `intent`/`intent=None` → `hint=''` on `_detect_flow`, `_flow_candidate_names`,
  `_detect_flow_prompt`; new `hint:str=''` on `predict`.
- One new module-level prompt constant `GENERIC_FLOW_PROMPT` (+ `GENERIC_FLOW_EXAMPLES`) in
  `backend/prompts/experts/__init__.py`. New prompt text, not a new concept — signed off under D1.

## Big decisions / alternatives

Already resolved in the signed-off spec (D1-A full catalog + generic prompt; D2-A ship the plan's
tie-break verbatim; D3-A add `hint` only on the methods that consume it — `understand`/`think`
untouched). One deviation I am flagging below (the `PRECEDENCE_NOTE` circular-import fix); no other
open decisions.

### Deviation from the spec's literal D1-A snippet (circular import)

The spec shows `GENERIC_FLOW_PROMPT = {..., 'rules': PRECEDENCE_NOTE, ...}` inside
`experts/__init__.py`. But `PRECEDENCE_NOTE` lives in `for_experts.py`, and `for_experts.py` already
imports `get_prompt` from `backend.prompts.experts` (for_experts.py:32). Importing `PRECEDENCE_NOTE`
back into `experts/__init__.py` is a circular import.

Fix with the reuse already in the code: `build_flow_prompt` sets
`rules_body = rules if rules else PRECEDENCE_NOTE` (for_experts.py:382). So `GENERIC_FLOW_PROMPT` sets
`'rules': ''` and the existing fallback supplies `PRECEDENCE_NOTE`. Same rendered prompt, no new
import, no cycle.

---

## Files and order of change

### 1. `backend/prompts/experts/__init__.py` — generic flow prompt (D1-A)

Add a cross-intent examples constant and the generic prompt, then let `get_prompt` fall back to it on
an empty key. `PROMPTS[intent]` stays the path for every real intent.

```python
GENERIC_FLOW_EXAMPLES = '''<positive_example>
## Conversation History

User: "find my posts about onboarding"
## Output

```json
{"reasoning": "Locating existing posts.", "flow_name": "find", "confidence": 0.92}
```
</positive_example>
... one <positive_example> per flow-owning intent (find / outline / rework / release / chat),
matching the format in draft_flows.py:14-45 ...'''

GENERIC_FLOW_PROMPT = {
    'instructions': ('Choose the single flow that best matches what the user wants across ALL '
                     'intents. The candidate list spans every flow; the detected flow fixes the '
                     'intent, so do not pre-commit to one intent family.'),
    'rules': '',                       # build_flow_prompt falls back to PRECEDENCE_NOTE (for_experts.py:382)
    'examples': GENERIC_FLOW_EXAMPLES,
}

def get_prompt(intent:str) -> dict[str, str]:
    return PROMPTS[intent] if intent else GENERIC_FLOW_PROMPT
```

One block per flow-owning intent — five blocks, one real flow each, every name checked against
`FLOW_CATALOG` (schemas/ontology.py:48): `find` (Research), `outline` (Draft), `rework` (Revise),
`release` (Publish), `chat` (Converse). One positive example each, so detection sees every intent
family represented. (Clarify and Plan own no detectable flow — their entries have `policy_path: None`
and are run by the Ambiguity Handler / Workflow Planner, so they get no block.)

Satisfies: acceptance §4 (no `get_prompt('')` crash) → `test_generic_flow_prompt_used_when_no_hint`,
`test_candidate_names_empty_hint_is_full_catalog`.

### 2. `backend/prompts/for_experts.py` — accept an empty intent

One-token change: `build_flow_prompt(user_text:str, intent:str='', ...)` (was `intent:str`). No branch
inside the body — `get_prompt('')` (step 1) returns the generic block, and `_render_current_scenario`
(for_experts.py:388) already skips the "Predicted intent" line when `intent` is falsy (line 342). The
default just states that an empty intent is a valid call.

Satisfies: acceptance §4.

### 3. `backend/modules/nlu.py` — detect-first + tie-break, param rename (3.1.1, 3.1.3)

**3a. `predict` (nlu.py:261-268)** — detect first; classify only to break a low-confidence
cross-intent tie. Add `hint:str=''`.

```python
def predict(self, user_text:str, hint:str='') -> dict:
    detection = self._detect_flow(user_text, hint)
    if self._intent_split(detection):
        intent = self._classify_intent(user_text)
        detection = self._detect_flow(user_text, hint=intent)
    return {'flow_name': detection['flow_name'],
            'confidence': detection['confidence'],
            'pred_flows': detection.get('pred_flows', [])}
```

**3b. new `_intent_split`** — place right after `predict`. D2-A condition verbatim.

```python
def _intent_split(self, detection:dict) -> bool:
    """True only when the ranked flows span >1 intent AND top-1 is under the confidence floor —
    the one case a coarse-intent tie-break is worth a call. Under D1-A the span clause is almost
    always true, so the confidence clause is the real trigger. At most one extra classify + one
    extra detect per turn."""
    intents = {FLOW_CATALOG[f['flow_name']]['intent'] for f in detection['pred_flows']}
    return len(intents) > 1 and detection['confidence'] < self.ambiguity.confidence_min
```

`detection['pred_flows']` is always present (both `_tally_votes` and the no-votes fallback set it), so
no `.get` guard.

**3c. `_detect_flow_prompt` (nlu.py:270)** — rename `intent` → `hint`; pass `hint` to
`_flow_candidate_names(hint)` and `build_flow_prompt(user_text, hint, ...)`.

**3d. `_detect_flow` (nlu.py:323, 325-326)** — signature `intent:str|None=None` → `hint:str=''`; pass
`hint` into `_detect_flow_prompt(user_text, hint, ...)` and `_flow_candidate_names(hint)`. No other body
change.

**3e. `_flow_candidate_names` (nlu.py:362-366)** — param → `hint:str=''`; guard `if intent is None`
→ `if not hint`; the hint-set branch is byte-identical to today (D1-A only revives the empty branch).

```python
def _flow_candidate_names(self, hint:str='') -> list[str]:
    if not hint:
        return list(FLOW_CATALOG)
    edges = _get_edge_flows_for_intent(hint)
    return [name for name, cat in FLOW_CATALOG.items() if cat['intent'] == hint or name in edges]
```

**Untouched (D3-A):** `understand` (85-97) and `think` (101-116) keep today's signatures; `think`
line 102 stays `self.predict(user_text)` (hint defaults ''). `_classify_intent`, `build_intent_prompt`,
`_intent_schema` all kept — the only removal is the unconditional call site inside `predict`.
No `_intent_candidates` helper (Simplifications §1).

Satisfies: acceptance §1 (pre-pass removed), §2 (tie-break + split logic), §3 (`_classify_intent`
callable), §5 (hint narrows), §9 (net simplification).

### 4. `backend/prompts/for_orchestrator.py` — PEX guidance (3.1.2, prose only)

- **Header comment (26-27)** — replace "NLU classifies the coarse intent and detects the flow …" with
  "NLU detects the flow before the loop runs; that detection fixes the intent, which the orchestrator
  reads from belief and acts on."
- **`INTENT_TAXONOMY` (32-36)** — replace the "ALREADY classified … ACT, don't re-classify … bias
  toward Plan or Clarify only when …" sentence with the spec's draft: PEX forms a quick intent sense
  in its own reasoning, never classifies on the record, reads NLU's authoritative intent from belief
  with `read_state`, and leans Plan/Clarify when the request is multi-step, vague, or spans intents.
- **`TOOL_POLICY` (53)** — change "the classified `intent`" to "the detected `intent`". No other
  `TOOL_POLICY` edit.

Satisfies: acceptance §6 (grep finds no "ALREADY classified"; finds the Plan/Clarify bias text).

### 5. `utils/evaluation_suite/_tests/nlu_unit_tests.py` — rename + new tests

**Mechanical rename:** lines 81, 94, 109 `_detect_flow('...', intent='...')` → `hint='...'`.

**New tests** (new class `TestPredictDispatch` near `TestEnsembleVoting`). Mock `_detect_flow` and
`_classify_intent` as `MagicMock` on the `nlu` fixture so no live LLM runs.

- `test_predict_skips_classify_on_confident_detection`: `_detect_flow` → single-intent conf 0.9;
  `predict(...)`; assert `_classify_intent` not called and returned `flow_name` matches. → §1.
- `test_predict_escalates_on_low_conf_cross_intent`: `_detect_flow` side_effect = [low-conf
  outline(Draft)+find(Research) conf 0.4, then compose(Draft) conf 0.8]; `_classify_intent` → 'Draft';
  assert classify called once, `_detect_flow` called twice with second `hint='Draft'`, result is the
  second detection. → §2.
- `test_intent_split_true_when_flows_span_intents_and_low_conf`: outline+find, conf 0.4 → True. → §2.
- `test_intent_split_false_when_confident`: outline+find, conf 0.9 → False. → §2.
- `test_intent_split_false_when_single_intent`: outline+compose (both Draft), conf 0.4 → False. → §2.
- `test_classify_intent_still_callable`: mock engineer → `{'reasoning':..,'intent':'Revise'}`;
  `_classify_intent('polish the intro') == 'Revise'`. → §3.
- `test_candidate_names_empty_hint_is_full_catalog`: `_flow_candidate_names('') == list(FLOW_CATALOG)`.
  → §4.
- `test_candidate_names_hint_narrows_to_intent`: `set(_flow_candidate_names('Draft'))` ⊇ {outline,
  compose, refine, brainstorm}, excludes `release`. → §5.
- `test_generic_flow_prompt_used_when_no_hint`: `build_flow_prompt('publish it', '', history, catalog)`
  does not raise and the rendered string contains the generic instruction text. → §4.

Satisfies: acceptance §8 (free suite green, zero skips).

---

## Verification order

1. `pytest utils/evaluation_suite/_tests/nlu_unit_tests.py` from cwd `assistants/Hugo` — the rename +
   new tests. Then `model_tests.py`, `pex_unit_tests.py`, `mem_unit_tests.py` for zero skips (§8).
2. Trace + E2E eval checks (§7) are run by the orchestrator after build, not by me (builders run no
   live evals).

## What I am NOT changing

`understand`/`think` signatures (D3-A), the belief path (`_write_belief`/`validate` already derive
`pred_intent` from the flow), `_get_edge_flows_for_intent`, and anything in §3.2/§3.3/§3.4. No
`_intent_candidates` helper.
