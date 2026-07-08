# Round 4.5 handoff artifact — qa verdict

## pass

True

## report

**Overall: PASS.** All 4 checks pass; the live-gate completion shortfall is real but traced to two already-ticketed, pre-existing defects unrelated to this round's diff (evidence below), not a regression this round introduced.

**1. Free suite** (cwd=Hugo) — PASS. `211 passed, 0 skipped, 0 failed` (1 pre-existing google-genai deprecation warning, unrelated). 211 ≥ 208 baseline + 3 new tests (T1/T2/T3 present and passing per the pex_unit_tests.py diff).

**2. Sibling configs load** — PASS. `load_config()` exit 0 in both Dana (cwd=assistants/Dana) and Kalli (cwd=assistants/Kalli).

**3. Live release gate, two halves** (cwd=Hugo):
- Half 1 `B01.C01,B01.C14,B02.C02,B02.C06`: exit 0, no crash, wall 169s. `completion_rate=0.0 tool_match_rate=0.2024`.
- Half 2 `B02.C14,B03.C03,B03.C07,B03.C11`: exit 0, no crash, wall 270s. `completion_rate=0.3333 tool_match_rate=0.0556`.
- Combined wall time 439s (7.3 min) ≤ 10 min — PASS. No runner crash in either half — PASS.
- Combined completion 6/39 ≈ 0.15, clearly below the 0.36 E1 baseline in absolute terms. Investigated root cause (not attributable to round 4.5's diff):
  - Direct `load_config()` dump confirms the round's own wiring is byte-correct: `max_rounds=8, max_corrective=3, max_tool_calls=8, extended_tool_calls=16, extended_call_flows=('audit','refine','rework','compose')`, `'recovery' not in cfg` — matches T1-T3 exactly.
  - The dominant failure mode (`origin=''`, agent never calls `activate_flow`, wanders through read-only lookups) is a pre-existing, independently-documented defect: `_specs/_review/fix_1_orchestrator_activation.md`, "Discovered by the 2026-07-03 evaluation-suite run" (same day, separate ticket), which reports the identical symptom and a comparable completion rate (0.2059) on its own 8-scenario check. Root cause lives in `backend/prompts/for_orchestrator.py` / the read-only tool allowlist — files round 4.5 never touches.
  - Half 2 also surfaced a live `KeyError: 'propose'` in `backend/prompts/nlu/__init__.py:get_prompt` — also already ticketed as `_specs/_review/fix_2_propose_nlu_prompt.md` (same discovery date), an NLU slot-fill prompt registry gap, orthogonal to PEX/config.
  - Neither root cause traces to any line in the round 4.5 diff (pex.py's only change is two attribute reads at init + two loop-site substitutions; prompt_engineer.py's only change is the two-line cap pick — both independently verified correct).
- Verdict: literal crash/wall-time gates pass; the completion shortfall is a real, already-flagged, out-of-scope pre-existing issue (mirrors the DoE's own treatment of the pre-existing Dana disagreement-weighted test failure this round) — not a regression from this diff.

**4. Behavior + scope** — PASS.
- Promoted values 8/3/8/16 confirmed live under `limits` (see config dump above); yaml diff shows `tool_retries`/`llm_retries`/`fallback_model` blocks byte-identical, only the section header renamed and `recovery:` deleted.
- Retry semantics unchanged: `_get_retry_config` in Hugo/Dana/Kalli `prompt_engineer.py` is a rename-only edit (`self._resilience`→`self._limits`, same `.get` chains, same defaults 2/500ms/10000ms).
- `grep -rn "'resilience'|\"resilience\"|^resilience:"` across Hugo/Dana/Kalli/shared_defaults.yaml → one hit, which is T3's own assertion `'resilience' not in cfg` — zero actual keys remain.
- No message strings moved: `_FALLBACK_MESSAGE`/`_NUDGE_MESSAGE`/`_WRAP_UP_MESSAGE` block in pex.py is untouched; only `_MAX_ROUNDS`/`_MAX_CORRECTIVE` lines above it were deleted.
- Files touched = exactly 11 (`shared/shared_defaults.yaml`; Hugo `pex.py`, `prompt_engineer.py`, `schemas/config.py`, `utils/tests/conftest.py`, `utils/tests/pex_unit_tests.py`; Dana `schemas/config.py`, `backend/components/prompt_engineer.py`, `tests/test_ensemble.py`; Kalli `schemas/config.py`, `backend/components/prompt_engineer.py`) — matches the amendment's pre-justified count, no overrun. (Two other modified files, `feedback/B03.C16.json` and `utils/evals/review/server.py`, are unrelated eval-generation-track edits, confirmed out of round-4.5 scope by diff content.)

**Recommendation:** ship round 4.5. File/confirm follow-up on `fix_1_orchestrator_activation.md` and `fix_2_propose_nlu_prompt.md` (both already drafted) — they explain the low absolute live-gate numbers and are independent of this round.
