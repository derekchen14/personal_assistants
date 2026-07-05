# Overnight run log — 2026-07-04 (user AFK)

Queue given by the user before stepping away:
1. Review code-review findings (fix good ones; questionable ones → master plan as a potential plan).
2. Full sub-agent workflow for round 4.3, execute.
3. Pick up the next sub-plan (4.6 per-call skill tier) with the team as well.

Standing instructions for this run: verbose logging (this file + chat messages); on hitting ~95%
of a token/session limit, pause at a clean point and set a 2-hour recurring check until limits
reset.

## Timeline

- 23:5x — Name sweep committed (8865f7d, 25 files): all "Derek" mentions in docs/comments/fixtures
  → "the user"; test fixture username 'derek' → 'writer'; suite 222/0 after. First attempt
  accidentally committed the untracked utils/trash_suite/ (via `git add -A`); reset --soft and
  recommitted without it — trash_suite is untracked again, contents untouched.
- 23:5x — New git workflow committed (2069b58): no PRs; plan → code → commit → push after a few
  commits; the user reviews live after each step. `_specs/agents/README.md` updated.
- Code-review agent (dispatched earlier over fa49a89..23d515c, focus: thread-safety of the
  parallel NLU/PEX model, message pairing, Pending lifecycle coherence, prompt/code drift) — still
  running; findings will be triaged per instruction 1 when it reports.
- 00:0x — Round 4.3 team workflow LAUNCHED (PM → SWE plans → DoE approve → builds → adjudicate).
  Scope handed to the PM: step_4_pex.md §4.3 exemplar raise (priority propose → 2-count → 3-count
  group) PLUS the repeated read actions cap (find_posts ×3-9/turn observed in every recent gate) PLUS a
  decision on whether NLU detection prompts also need exemplars (the gate's binding constraint is
  DETECTION accuracy, while §4.3 as written targets PEX skill exemplars — the PM must reconcile).

## Code review triage (instruction 1) — review returned 00:1x, verdict "safe to build on WITH fixes"

APPLIED (committed on master):
1. CRITICAL — plan wipe: `write_state op=stackon/fallback` wrote only the file-backed stack;
   `complete_flow`/`activate_flow` overwrite that file FROM the live stack, so a plan's Pending
   flows vanished on the first completion (reviewer reproduced it). Fix: mirror stackon/fallback
   (and `prestack`) onto the live stack exactly as pop_completed already did. Verified two ways:
   new `TestPlanLifecycle` regression test (stack 3 → complete top → survivors Pending →
   pop_completed surfaces next as Active) and the reviewer's own repro script now prints
   PLAN SURVIVED with file/live stacks identical at every step.
2. Contemplate re-arm race: a still-running think thread could overwrite contemplate's narrowed
   detection. Fix: blocking `_check_nlu()` before the contemplate call (orders the two belief
   writers).
3. Torn belief read in the stackon-active fold: PEX could fold LAST turn's pred_slots against
   THIS turn's pred_flows mid-write. Fix: fold only when the think thread has fully landed
   (`_nlu_thread is None` guard — same as inject_belief_state).
4. Prompt named a tool that does not exist: `append_scratchpad` → `append_to_scratchpad` (first
   use cost a corrective round every session).
5. Language/doc sweep the review caught: staging words in test names + tolerance_rules.md, a
   stale plan_id note, a stale "not built yet" comment in run_suite.py, `read_from_scratchpad` →
   `read_scratchpad` in pex.md.
6. New regression test added (the gap that let the Critical ship green).
   Suite after all fixes: 137 pex + 86 nlu/mem = 223 passed, 0 skipped.

## Round 4.3 progress

- 00:07 — PM finished the spec sheet at `round_4.3_spec.md` (216 lines, high quality): Decision 1
  = uniform exemplar floor of 5 for the 13 thinnest PEX skills (34 new exemplars; argued against
  the style guide's 7-10 as gold-plating while detection is the bottleneck); Decision 2 =
  per-turn read counter, `limits.max_reads: 3`, corrective 'read_cap' error in _guarded_call,
  only successful reads count; Decision 3 = YES fold NLU detection exemplars in (the load-bearing
  part): 13 contrastive boundary exemplars, floor 6 per intent, priority on the write/rework
  boundary that keeps failing in the gate. Verification: 7 acceptance criteria incl. gate deltas
  vs 0.5152 / 0.0864 / 12.4s.
- 00:13 — PM AGENT DIED reporting (StructuredOutput retry cap; 3rd such death) AFTER writing the
  spec — work survived. Workflow edited and resumed: PM phase removed (spec exists), and the
  output-death fix applied everywhere: builders now write diffs to FILES in the scratchpad and
  return only the path + --stat (structured output stays small); explicit output discipline
  order added. Resumed as task wtud3pdxm.

- 00:2x — SWE plans + DoE approval completed (all order echoes present). DoE verdict: both plans
  approved, no placeholder output; adopted SWE1's refinements (init `_reads` in __init__ beside
  `_injected`; increment AFTER the _success normalization — deletes a KeyError class) and SWE1's
  path correction (detection files are backend/prompts/experts/*_flows.py, NOT nlu/experts/ as
  the PM spec said). Ponytail net +4 ("plans are lean; nothing to strip"), one -1: extend the
  existing dedupe-test class instead of new test scaffolding. Sample propose exemplars from both
  SWEs passed authoring review (19-21 word utterances, correct house shape); both picked
  beekeeping as the topic, so builders were told to rotate. Direction persisted by the DoE itself
  at round_4.3_direction.md.
- 00:3x — SESSION LIMIT hit mid-round: both SWE builders died ("resets 3am"). The user manually
  resumed at ~3am ("session limit reset, continue"); workflow resumed from cache (plans+approval
  replay, builds re-run) as task wzumtlkli. If another limit hits while AFK, the standing
  instruction applies: set a 2-hour recurring check instead of dying.

- 03:1x — Round 4.3 builds + adjudication COMPLETE (the file-based diff transport worked — zero
  output-cap deaths this run). Adjudication: SWE2 base with targeted SWE1 swaps. Decisive defect
  caught: SWE1 authored 2 detection exemplars whose flow_name sits OUTSIDE the JSON schema enum
  (Converse→summarize, Publish→promote — promote is a PEX-agent skill, not a flow); they would
  train outputs the schema rejects. Also caught: one banned-tic use in SWE1's chat.md; SWE2's 4
  converse additions were all chat (no adjacent-intent contrast) — DoE dropped 3 and authored 1
  proper contrastive case itself. Ship diff: 20 files, +613/-5, apply-check pre-verified.
  Compliance: order-by-order pass after merge fixes. Ponytail net +5/-0.
- 03:2x — Applied. Orchestrator-owned pieces done per DoE MUST-FLAG: max_reads added to the two
  fixture limits overrides (conftest.py, pex_unit_tests.py); AC-3 read-cap test written into the
  existing guard-test class (4 varied-args find_posts calls → first 3 dispatch, 4th returns
  read_cap). Suite: 224 passed, 0 skipped. AC-4 (detection boundary) is measured by the live
  gate rather than a dedicated model test — deltas below are the verdict. Artifacts persisted to
  round_4.3_artifacts/ incl. ship.diff. Live gate launched.

- 03:3x — Round 4.3 GATE VERDICT (standard 8): completion 0.5152 (AC-6 met: no regression, but
  flat), tool_match 0.0826 (AC-5 NOT met: flat vs 0.0864), mean turn 14.4s (worse than 12.4 —
  within run-to-run variance; earlier identical-config runs spanned 12.4-15.5s). KEY FINDING from
  transcript forensics: `read_cap` fired ZERO times across all 8 live sessions, yet B06.C01 turn
  1 emitted 7 read-only calls — because those repeated reads ran INSIDE the flow's own tool loop
  (llm_execute → _dispatch_tool), which never routes through _guarded_call. The orchestrator-level
  cap is live and unit-verified but targets the smaller half of the observed repeated reads; the flow-
  internal repeated reads sit under max_tool_calls (8/16) and are the real latency sink. Follow-up
  candidate recorded below. Detection exemplars: no visible movement this run — B06.C01's
  turn-2-4 failures are stale-flow origins (the flow-switch behavior), not detection errors, so
  the exemplars' effect needs the write/rework-specific scenarios to show. Committing the round:
  content and cap are correct and tested; gate is flat-not-worse; single-run deltas at this
  variance are not decisive.
- FOLLOW-UP added to the deferred register: bounding too many read actions inside a flow
  (per-flow read budget inside llm_execute, or skill-prompt discipline for browse/audit) — the
  cap that would actually move tool_match and latency.

- 03:4x — Round 4.3 COMMITTED (dbc2b00, 33 files: 34 PEX exemplars, 13 detection exemplars, the
  read cap, tests, artifacts incl. ship.diff). Gate-run seed mutations restored again (same
  draft file — the eval-sandbox issue in the register keeps proving itself).
- 03:4x — Round 4.6 (per-call skill tier, instruction 3) LAUNCHED through the full pipeline
  (PM spec → SWE plans → DoE approve → worktree builds → adjudicate), task w2zoic924, base
  dbc2b00. Small round: skill_call gains model:str='med' for symmetry with tool_call; the PM
  decides whether any policy requests 'high' now or the round ships capability only.

## Round 4.6 progress

- 03:5x — Round 4.6 pipeline COMPLETE, 7/7 agents clean (no output-cap deaths, file-based diffs
  again). PM spec at `round_4.6_spec.md` resolved the round's one decision as Option A: ship the
  capability only, upgrade no call site — the only two skill_call sites (research find/summarize)
  are not hard skills, and the named hard skills (audit/rework) already reach the tier knob via
  tool_call's existing model= arg. Both SWE builds produced IDENTICAL code hunks (they differed
  only in test docstring wording); DoE picked SWE2 (its reading of the test-location rule was
  correct). Ponytail net +4/-0.
- 03:5x — Ship diff applied to master: `skill_call` gains `model:str='med'` (last positional,
  mirroring tool_call), the two hardcoded 'med' resolution calls now pass it through; one new
  test (test_skill_call_honors_model_tier, asserts seen==['high','med']). 3 changed source lines
  + 10 test lines. Free suite: 225 passed, 0 skipped (pex+nlu+mem+model). No live gate — default
  'med' equals the old hardcoded tier, zero behavior change, nothing for a paid E2E run to
  detect (per spec + both SWEs + DoE, unanimous). Artifacts persisted to round_4.6_artifacts/
  incl. ship.diff. Committed.
- With 4.6 done, instruction 3 is complete — the whole AFK queue (1: code-review triage,
  2: round 4.3, 3: round 4.6) is finished. Stopping the round queue here: no further rounds were
  sanctioned, and the next Master Plan work (step 2 MEM) is a major step that needs a plan
  developed with the user first. Commits dbc2b00 + the 4.6 commit remain unpushed pending the
  morning review, per the workflow (push after a few commits, HITL review first).

DEFERRED to master_plan.md "Deferred register" (questionable / design-level, per instruction 1):
- One-source-of-truth flow stack (the mirror fix treats the symptom; two writers remain).
- read_state's unconditional blocking join serializes most parallel-think turns because the
  prompt sends every intent to read belief first — needs the user's explicit ruling (keep vs
  conditional join vs prompt change). THE MOST IMPORTANT OPEN QUESTION for the parallel NLU/PEX processing.
- Smaller: execute() 7 params; dead _llm_quality_check; dead keep_going writes (Batch-2b); a
  carrier-A message-shape test; forced fallback on the loop's final round waits a turn;
  scratchpad in-memory crash; eval runs mutate checked-in content seeds.
