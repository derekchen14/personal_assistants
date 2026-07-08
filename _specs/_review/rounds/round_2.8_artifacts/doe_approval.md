# Round 5.2 — DoE review and build direction

Base: 0f27939. Spec: `_specs/agents/plans/round_5.2_spec.md` (authoritative).
Plans reviewed: `round_5.2_swe1_plan.md` and `round_5.2_artifacts/swe2_plan.md`.

## Verification result

I checked every file and line reference both plans cite against the live source at 0f27939.
All references are correct:

- dialogue_state.py: import at 4, docstring word at 15, rehydrate_flow 35-47, line 74,
  write_state 160-178, _update_flow 194-205, _run_stack_op + _rehydrate_stack 207-221.
- pex.py: import at 7, docstring word at 429, read_state 596-598, _dispatch_write_state 600-631
  (repeat block exactly 613-623), _apply_belief_slots 633-642, inject_belief_state 644-672
  (write at 666, second fallback at 668), prestack 674-688, activate_flow call site at 698,
  copy refresh at 723, _stack_flow 735-763.
- agent.py: prestack call at 81, POST-HOOK 108-117, save at 114 (carries a trailing comment).
- world.py: import at 4, open_session 49-59 (docstring 50-52), reset's direct `_stack` use at 73.
- base.py: banned words at 12, 15, 106; complete_flow 224-237 (pre-write copy 230, status
  repeat 235).
- for_orchestrator.py: PRE-STACKED bullet at 97-99; 100-103 unchanged.
- stack.py: find_by_name 61-68, stackon dedupe at 25, comment naming `_stack_flow` at 109.
- Tests: pex_unit_tests 96-102, 104-117, 194-212 (write_state calls 197-199, assert 209),
  Hypothesis machine 1454-1600 (all rule and invariant line ranges match), header 1739,
  docstring 1744-1746, line 1765, prestack tests 1778-1797, belief-injection blocks 1876-1878
  and 1890-1892, TestPlanLifecycle 1899-1929; nlu_unit_tests TestWriteStateOps 498-595
  (direct-stack lines 534, 537-540, 542, 544, 547, 549 as listed); mem_unit_tests messages
  test 486-492, FlowStack import at 500, DialogueState imported near 274, World at 13;
  conftest sessions_dir fixture patches `world._SESSIONS_DIR` (conftest.py:121-125).
- All five production `write_state` callers are covered by a spec section (pex.py:612, 642,
  666, 685-deleted, base.py:234). No stragglers.
- `_without_ids` in nlu_unit_tests.py (483-485) is used ONLY by the op-sequence test being
  rewritten — see amendment A4.

Both plans confirmed the same two spec gaps (stack.py:109 comment; world.py:50 wording) and
proposed the same stack.py fix. Verdicts: SWE1 APPROVED WITH AMENDMENTS, SWE2 APPROVED WITH
AMENDMENTS. SWE2 is the basis (finer line-by-line placements, catches the missing blank lines
before TestCheckNlu); SWE1 supplies the world.py docstring wording and the agent.py:114
trailing-comment handling.

## Ponytail review (minimality — this round is a deletion round)

- +1 both: no new classes, methods, or attributes anywhere; the only new surface is the
  `stack=` parameter the spec mandates.
- +1 both: prestack, _stack_flow, _run_stack_op, _rehydrate_stack, and the pex repeat block
  are deleted with nothing added in their place; net deletion holds.
- +1 both: stack.py:109 fixed by removing three words from a comment — the smallest edit that
  makes acceptance grep 2 pass.
- +1 SWE2: caught that deleting tests 1778-1797 leaves `class TestCheckNlu` with no blank
  lines above it (1797 runs straight into 1798 today).
- +1 SWE1: world.py docstring keeps the true messages.jsonl fact while containing the spec's
  exact target sentence — accuracy at zero structural cost.
- -1 SWE2: drops the messages.jsonl fact from the open_session docstring even though
  attach_messages still runs on line 55.
- -1 both: neither deletes nlu_unit_tests' `_without_ids` helper, which their own edit
  orphans (CLAUDE.md: remove what your changes made unused).
- +1 both: dead local `before_completed` (pex 1557) and pre-existing banned words outside the
  sweep list are left alone — correctly surgical, flagged not fixed.

Net: +4. Both plans are minimal; nothing adds speculative structure. SWE2 edges out on
precision, SWE1 on two wording calls. No rejections.

## Build direction

Basis: **SWE2's plan** (`round_5.2_artifacts/swe2_plan.md`), applied exactly as written —
its 10-step order, every before/after, and its verification section — with these amendments:

- **A1 (world.py:50-52 docstring)** — use SWE1's wording, not the spec-quote-only version:
  `"""Bind this World to a session. An existing dir reloads its state.json as the current
  state and rebuilds the flow stack from it; messages.jsonl is attached as the persistent
  message list; a fresh id defers dir creation to session_dir() (lazy, first turn)."""`
  It contains the spec's exact target sentence and keeps the docstring true to attach_messages.
- **A2 (agent.py:114)** — the save line keeps its existing trailing comment
  `# _ensure_session guarantees a bound session`; insert ONLY the new refresh line above it:
  `state.flow_stack = self.pex.flow_stack.to_list()  # refresh the saved copy, then save`
- **A3 (stack.py:109)** — as both plans wrote:
  `# (activate_flow, or pop_completed surfacing the next top).`
- **A4 (nlu_unit_tests.py)** — after the op-sequence test moves to exact equality, delete the
  now-unused `_without_ids` helper (lines 483-485 plus its surrounding blank lines). Do NOT
  touch pex_unit_tests' own `_without_ids` — the Hypothesis invariant still uses it.
- **A5 (pex_unit_tests.py:209)** — the flipped assert carries no trailing comment:
  `assert pex.flow_stack.find_by_name('outline') is not None`
- **A6 (pex_unit_tests.py after deleting 1778-1797)** — leave exactly two blank lines between
  the end of `test_stackon_without_active_only_stacks` and `class TestCheckNlu`.
- **A7 (TestSingleCallStackon docstring)** — final text, one sentence:
  `"""\`write_state op=stackon active=true\` stacks on, folds belief slots, and runs the
  policy in one call."""`

Accepted flags (no action): R4 validation-order change has no observable difference; R5
always-true identity assert implemented as spec'd; R6 dead `before_completed` stays
(pre-existing); R7/SWE1-risk-7 pre-existing banned words outside the sweep list stay
(agent.py post-hook method name and nearby comments, pex_unit_tests.py:149 stub docstring,
nlu/mem unused rehydrate_flow imports) — orchestrator may queue a later sweep; R8 empty-stack
error shape change accepted (crash-loud rule, `_dispatch_tool` converts either way); R9
exact-equality assert is correct — flow_ids round-trip through save/load.

Everything else: spec verbatim. Run SWE2's verification section from the assistants/Hugo cwd.
