# DoE Plan Review — Round 3.1

Reviewed against `round_3.1_spec.md` (D1-A, D2-A, D3-A) and the code at base commit `a2445f6`.
Verified claims directly: `for_experts.py:32` imports `get_prompt` from `experts/__init__.py`,
`PRECEDENCE_NOTE` lives in `for_experts.py`, `build_flow_prompt` falls back to `PRECEDENCE_NOTE`
when `rules` is empty (for_experts.py:382), `_render_input` skips the "Predicted intent" line when
`intent` is falsy (for_experts.py:342), and all cited nlu.py / nlu_unit_tests.py line numbers match.

## SWE1 — RETURNED

One concrete defect:

- **Step 1 names a flow that does not exist.** The generic exemplar list is
  "`find` (Research), `outline` / `compose` (Draft), `edit` (Revise), `release` (Publish),
  `chat` (Converse)", and the plan says these names "come from the catalog defaults". There is no
  `edit` flow in `FLOW_CATALOG` (schemas/ontology.py:48) — the Revise flows are `rework`, `write`,
  `audit`, `propose`. Built as written, the generic prompt would teach detection a `flow_name` the
  candidate schema never allows, and no offline test catches it (the prompt test only checks that
  the build does not raise). Fix: pick a real Revise flow (e.g. `rework`) and re-check every
  exemplar `flow_name` against the catalog. While there, note the list is two Draft flows across
  five intents; the spec asks for one block per intent — cover Revise once correctly instead of
  Draft twice.

Everything else in SWE1 is sound. The circular-import fix (constant in `experts/__init__.py` with
`'rules': ''` riding the existing PRECEDENCE_NOTE fallback) is verified workable and matches the
registry docstring, which already documents the empty-rules fallback.

## SWE2 — APPROVED

Matches the spec, decisions, tests, and acceptance criteria. The flagged deviation — generic
constants in `for_experts.py` with an empty-`intent` branch in `build_flow_prompt`, leaving
`get_prompt` a pure lookup — is accepted: the spec's literal D1-A snippet would create a circular
import, and the spec's own "New concepts" line already describes "an `intent=''` branch in
`build_flow_prompt`". Exemplar flows cited (`release`, one per flow-owning intent) all exist in
the catalog.

Non-blocking notes for build:

- The `_intent_split` docstring draft says a tie-break "earns its extra call" — banned phrasing;
  write "is worth the extra call".
- The verification section chains `cd ... && python -m pytest` — run as separate commands per the
  repo bash rules.

## Divergence forecast

The expected SWE1/SWE2 divergence is where the generic prompt content lives (`experts/__init__.py`
+ `get_prompt` fallback vs `for_experts.py` + `build_flow_prompt` branch). Both avoid the import
cycle and render the same prompt. Adjudication happens at change-set review, not here.
