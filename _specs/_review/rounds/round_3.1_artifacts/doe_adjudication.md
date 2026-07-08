# Round 3.1 — DoE adjudication

## Divergence class: minor

## What I compared

- **nlu.py** — the two diffs are the same code. `predict` detect-first + `_intent_split` guard +
  the `hint=''` rename are byte-identical. Only the `_intent_split` docstring wording differs;
  SWE2's says the tie-break "earns its extra call", a phrase on Derek's banned list. SWE1's
  docstring is clean.
- **for_orchestrator.py** — identical except the two-line header comment; both versions are
  accurate. INTENT_TAXONOMY and TOOL_POLICY rewrites are byte-identical.
- **Generic flow prompt (D1-A)** — the one real difference:
  - SWE1 put `GENERIC_FLOW_PROMPT` + `GENERIC_FLOW_EXAMPLES` in `experts/__init__.py` and made
    `get_prompt('')` return it, with `rules=''` so `build_flow_prompt`'s existing PRECEDENCE_NOTE
    fallback fills the rules. `build_flow_prompt`'s body is untouched. This is the spec's named
    location and mechanism (D1-A snippet).
  - SWE2 put `GENERIC_FLOW_INSTRUCTIONS`/`GENERIC_FLOW_EXAMPLES` in `for_experts.py` and added an
    if/else branch inside `build_flow_prompt`, a flagged deviation to dodge an import cycle. But
    there is no cycle in SWE1's version: the constants in `experts/__init__.py` import nothing from
    `for_experts.py` (`rules=''` avoids needing PRECEDENCE_NOTE there). SWE2's branch also rewrites
    the working `rules_body` fallback for no behavior change.
  - Both example sets use only real FLOW_CATALOG flows (verified against `schemas/ontology.py`).
    SWE2 adds a sixth example (`plan`); nice but not worth the placement deviation.
- **Tests** — same 9 cases, different helper style. SWE1 factors the detection dict into a
  3-arg `_detection` helper reused 6 times; SWE2 writes the dicts inline. SWE1's is shorter.
  SWE2's class docstring uses "gates", a banned word this round. One SWE2 win: its
  `test_generic_flow_prompt_used_when_no_hint` takes no unused `nlu` fixture; SWE1's version
  requests the fixture and never uses it.

## What I picked

SWE1's change set, with two trims:

1. **Dropped SWE1's `for_experts.py` hunk entirely.** It only added `=''` defaults to
   `build_flow_prompt`'s params. No caller omits any argument (the sole production caller is
   `_detect_flow_prompt`, which passes all five; SWE1's own test calls positionally), so the
   defaults are unused surface. With the hunk dropped, `for_experts.py` is untouched this round.
2. **Took SWE2's fixture-free signature** for `test_generic_flow_prompt_used_when_no_hint`
   (drop the unused `nlu` fixture param).

## Why

- SWE1 matches the spec's D1-A placement (`experts/__init__.py`, `get_prompt('')`) and reuses the
  existing PRECEDENCE_NOTE fallback instead of duplicating it in a new branch. Net: one file fewer
  touched, no `build_flow_prompt` body change.
- SWE1's prose avoids the banned phrases SWE2's docstrings use.
- The merge is smaller than either original: 4 files (nlu.py, experts/__init__.py,
  for_orchestrator.py, nlu_unit_tests.py).

## Result

Merged diff applied to the real tree; deterministic suites (pex/nlu/mem unit tests) run from
`assistants/Hugo` — result recorded in the round summary.
