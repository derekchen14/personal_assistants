# Round 5.3 — DoE Adjudication

Winner: **SWE2**, shipped verbatim. No hunks swapped from SWE1.
Final diff: `scratchpad/round53_final.diff` (identical to `round53_swe2.diff`).
`git apply --check` from repo root passes at HEAD `1615be4`.

## Summary

Both builds implement round 5.3 correctly and pass every gate. They are functionally
identical: same 16 file renames (skills/ -> flows/), same frontmatter removal, same loader
rewrite, same method renames, same four content edits, same audit preload, same test edits.
Both builders report 223 passed / 0 skips on the free suite and both acceptance greps clean.

The diffs differ only in cosmetic and spec-fidelity details. On the details that matter to
the adjudication criteria, SWE2 is at or above SWE1 everywhere, so it ships as-is.

## Where SWE2 wins

1. **Rename completeness (test name).** SWE1 keeps the test named
   `test_skill_call_honors_model_tier` — its body now calls `flow_reply`, so the name is a
   stale `skill_call` reference. SWE2 renames it to `test_flow_reply_honors_model_tier`, so no
   `skill_call` substring survives anywhere in `backend/` or the tests. Acceptance criterion 2
   greps only `backend/` + `for_orchestrator.py`, so both technically pass, but SWE2 is the
   clean rename.
2. **Docstring fidelity to 5.3.5.1.** The spec asks the `for_pex.py` module docstring's
   user-message line to read "filled starter (runtime parameters + preloaded content) + recent
   conversation". SWE2 rewrote that line; SWE1 left the base wording. Minor, but SWE2 is the
   fuller execution of 5.3.5.1.
3. **cite / compare / summarize templates.** The spec (5.3.6) says "keep both templates" for
   these three flows. SWE2 keeps the named `TEMPLATE_*` constants and only strips the `<task>`
   block, matching that wording literally. SWE1 deletes the constants and rebuilds the same
   output with inline f-strings — same rendered text, but a looser reading of "keep both
   templates". SWE2's literal fidelity is the safer choice.
4. **rework.py hoist.** SWE2 hoists `post_preview = render_section_preview(...)` onto its own
   line; SWE1 inlines it inside an f-string with nested double quotes. SWE2 matches the
   CLAUDE.md preference for hoisting a named subexpression over a denser literal.

## Where SWE1 was arguably ahead

- Leaner diff (656 deletions vs 616; 107 insertions vs 114) because it collapses the
  cite/compare/summarize template constants into f-strings. This is the only axis on which
  SWE1 leads. Because 5.3.6 explicitly says "keep both templates", the extra deletion trades
  against spec fidelity, so it does not outweigh SWE2's edges.

## Ponytail review

- Net score: **+3** (favoring SWE2, on a small scale — both are already lean, near-pure
  deletion builds).
- Neither build adds an abstraction, a dependency, or dead flexibility. Both delete three
  loader helpers, one drift test, 16 frontmatter blocks, and 13 `<task>` blocks. The
  `_yaml_tools` / `_few_shot_tool_calls` / `_COMPONENT_TOOLS` helpers are correctly kept
  (still used by `test_flow_tools_are_registered` / `test_few_shot_tools_are_allowlisted`),
  not orphaned.
- SWE1's f-string collapse is the more "delete-y" move and a ponytail would normally reward
  it, but here the spec names the shape ("keep both templates"), so the named-constant form is
  the correct target and SWE2's small extra lines are not bloat.
- No `ponytail:` comments needed; the change is a mechanical consolidation with a check
  already present (the repurposed loader smoke test + the kept allowlist test).

## Verification performed

- Read both diffs in full and the spec in full.
- Grepped the base tree for all eight stale symbols; confirmed the winner removes every
  occurrence in `backend/` and `for_orchestrator.py`. Remaining hits are `utils/helper_ref.md`
  lines 20/21/31/200 only — doc prose the DoE direction deliberately left for a later pass
  (builders touched line 36 only, as directed).
- `git apply --check round53_final.diff` from the repo root: passes.
- Did not run the suite myself (applying the diff is the orchestrator's job per the orders);
  relied on both builders' matching 223-passed/0-skip reports plus a static read confirming
  every test edit (renamed imports, renamed calls, deleted `test_skill_tools_match_flow` and
  its `_PEX_AGENT_SKILLS` helper, repurposed loader smoke test) is internally consistent.

## Flagged divergences (not defects)

- **Spec 5.3.5.1 helper-name wording.** The spec says replace "Skill-rendering helpers" with
  "starter render helpers", but the base text is actually "Slot-rendering helpers" (there is no
  "Skill-rendering helpers" string). SWE2 changed it to "Slot render helpers", which stays
  accurate (they are slot render helpers used by starters) rather than adopting the spec's
  mis-derived "starter render helpers". Correct call; the spec instruction rested on a misread.

## Hand-work for the orchestrator after applying

1. Apply `round53_final.diff` and commit (builders make no commits/branches).
2. `helper_ref.md` lines 20, 21, 31, 200 still name `skill_call` / `tool_call` /
   `load_skill_template` in prose. Out of scope this round by direction; queue a doc-only
   follow-up to rename them to `flow_reply` / `flow_execute` / `load_flow_prompt`.
3. Pre-existing, not created here: `starters/outline.py` imports `render_freetext` which is now
   unused after the `<task>` deletion (the import predates this round; CLAUDE.md says leave
   pre-existing dead code). Worth a cleanup pass but not a blocker.
4. Run the 8-scenario eval gate after ship, per 5.3.10.4.
