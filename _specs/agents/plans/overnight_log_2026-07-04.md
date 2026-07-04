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
  two-speed model, message pairing, Pending lifecycle coherence, prompt/code drift) — still
  running; findings will be triaged per instruction 1 when it reports.
- 00:0x — Round 4.3 team workflow LAUNCHED (PM → SWE plans → DoE approve → builds → adjudicate).
  Scope handed to the PM: step_4_pex.md §4.3 exemplar raise (priority propose → 2-count → 3-count
  group) PLUS the read-storm cap (find_posts ×3-9/turn observed in every recent gate) PLUS a
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

DEFERRED to master_plan.md "Deferred register" (questionable / design-level, per instruction 1):
- One-source-of-truth flow stack (the mirror fix treats the symptom; two writers remain).
- read_state's unconditional blocking join serializes most parallel-think turns because the
  prompt sends every intent to read belief first — needs the user's explicit ruling (keep vs
  conditional join vs prompt change). THE MOST IMPORTANT OPEN QUESTION for the two-speed design.
- Smaller: execute() 7 params; dead _llm_quality_check; dead keep_going writes (Batch-2b); a
  carrier-A message-shape test; forced fallback on the loop's final round waits a turn;
  scratchpad in-memory crash; eval runs mutate checked-in content seeds.
