# Round 5.3 — DoE Approval and Build Direction

Verified against live source at tip `1615be4`. Every file:line in both SWE plans was re-read at the
tip. All references are correct. Both plans are complete: a repo-wide grep for the nine renamed/deleted
symbols returns exactly the sites both plans enumerate, with no missed occurrence.

## Verdict

**APPROVED with two amendments and three tie-breaks.** Both SWE plans are faithful to the spec and to
each other on the structural core (moves, frontmatter strip, loader rewrite, method renames, starter
shrink, test retire). Where they diverge, this document is the deciding call so both builders produce
one identical diff.

Both plans independently found the one real spec gap the spec's "exhaustive" grep missed:
`utils/evaluation_suite/_tests/conftest.py:76` (`a.engineer.tool_call = _stub_tool_call`). Confirmed
real — after the rename, the `mock_agent` fixture would stub a dead attribute and the live tool loop
would run, breaking acceptance criterion 4 (zero skips). This fix is MANDATORY.

## Tie-breaks (where the two plans disagreed)

1. **Method parameter `skill_prompt` → rename to `flow_prompt`** on both `flow_reply` and
   `flow_execute` (SWE2's choice; spec 5.3.9's recommendation). Keep `skill_name`. Reason: this round
   removes "skill" naming where it means "flow"; a method named `flow_reply` with a `skill_prompt`
   param is exactly the half-named debt the round exists to remove, and `build_flow_system`'s param is
   already mandated to rename. Cost is six one-token keyword edits: `research.py:75`
   (`skill_prompt=` → `flow_prompt=`, plus rename the local at :72 to `flow_prompt`) and tests
   `556,557,566,567` (`skill_prompt=''` → `flow_prompt=''`). SWE1's keep-the-param plan is rejected on
   this point only.

2. **`compose.py` fallback string: keep the existing wording verbatim** (SWE2). Do NOT shorten it to
   the spec's compressed illustration in 5.3.6. Keep:
   `'(section previews not preloaded — call read_metadata with include_preview=True before composing)'`.
   The fallback text is not part of this change; rewriting it is unrelated churn.

3. **`helper_ref.md`: update line 36 ONLY** (SWE1 / spec scope). Do NOT expand to the other five stale
   references (lines 20, 21, 31, 40, 200). See flagged item below.

## Amendments to the spec (flagged, not silent)

- **A1 — Defer 5.3.7.5 (Tools trim): make ZERO cuts this round.** Both SWEs flagged it as
  judgment-based and non-deterministic, and both leaned toward zero cuts. A trim that "may cut
  different bullets between the two builders" guarantees a divergent diff for near-zero value; the spec
  itself says "when unsure, keep," and `test_few_shot_tools_are_allowlisted` still guards tool names.
  Skipping it entirely is the only way to keep one identical diff. Recommend the PM drop 5.3.7.5 or
  respec it as an explicit per-line list if the restatement really must go.
- **A2 — `helper_ref.md` under-scope (flag only, no action).** Lines 20, 21, 31, and 200 still name
  `skill_call`, `tool_call`, and `load_skill_template`, which this round renames; line 40 and part of
  200 name `_build_skill_prompt` / `build_skill_prompt`, which do not exist in live source (pre-existing
  dead refs). The spec scoped only line 36. I hold to spec scope for a deterministic diff and to respect
  the authoritative spec, but the doc will read half-updated. Recommend a one-line follow-up to fix
  lines 20/21/31/200 (rename tokens only; leave the dead `_build_skill_prompt` mentions).

## Mandatory build direction (both builders, identical diff)

1. `git mv` the 16 flow `.md` from `pex/skills/` → `pex/flows/`; `plan.md` stays in `pex/skills/`.
2. Strip the leading `---`…`---` block plus the one trailing blank line from all 16 moved files. No
   body-prose sweep (5.3.2).
3. `prompt_engineer.py`: replace `_SKILL_DIRS` (70-73) with `_FLOW_DIR` + `_SKILL_DIR`; delete the four
   helpers (686-719) and add `load_flow_prompt` + `load_skill` (one-liners, no `None`/`or ''` guard,
   missing file raises `FileNotFoundError`); remove the now-orphan `import yaml` (line 12). Rename
   `skill_call`→`flow_reply` (181) and `tool_call`→`flow_execute` (199), param `skill_prompt`→
   `flow_prompt`, body calls to `load_flow_prompt`/`build_flow_system`/`build_flow_messages`, import 16
   to `build_flow_system, build_flow_messages`.
4. `for_pex.py`: `build_skill_system`→`build_flow_system` (param `skill_prompt`→`flow_prompt`; line 61
   guard `if flow_prompt:`; line 63 divider `--- {flow_name} Flow Instructions ---`);
   `build_skill_messages`→`build_flow_messages`; rewrite module + function docstrings (no banned words);
   `_default_starter` drops the `<task>` synthesis (delete 101-107, 122-124), keeps the slot loop, the
   `resolved` param, and `_summarize_entity`.
5. 13 starters: delete every `<task>…</task>` block and the `tool_sequence`/`verb`/`end_condition`/
   `_DIFF_CLAUSE` logic; keep content blocks + `<resolved_details>` + `_format_parameters` + render
   helpers; signature stays `build(flow, resolved, user_text)`. `audit.py` adds a `<post_content>`
   block from `resolved['post_prose']` (5.3.7.1). Delete only the helpers your own deletions orphan:
   `_snippet_text` (brainstorm), `_topic_text` (outline), `_post_label` (compare), `_length_clause`
   (summarize), `_DIFF_CLAUSE` (compare) — re-grep each before deleting. Leave pre-existing dead
   imports untouched.
6. Four `.md` content edits, exact text per spec 5.3.7.1–.4: `audit.md` step 1a, `compose.md`
   `read_section` no-re-read, `outline.md` propose forbidden-tools, `write.md` image bullet.
7. `revise.py::audit_policy` (before line 234): add
   `pre = self._read_post_content(post_id, tools)` and pass
   `extra_resolved={'post_prose': pre.get('content', '')}` to `llm_execute`. Leave line 244.
   (`llm_execute` accepts and merges `extra_resolved` — verified base.py:62,77.)
8. `base.py:15` comment and `:83` → `flow_execute`. `research.py:46/72/73` → `flow_reply` /
   `load_flow_prompt` / `flow_reply` with `flow_prompt=`. `for_orchestrator.py:233` → `load_skill("plan")`.
   `conftest.py:76` → `flow_execute` (A0 mandatory).
9. `pex_unit_tests.py`: retire `test_skill_tools_match_flow` (1669-1684) and delete `_PEX_AGENT_SKILLS`
   (1651); rename `_SKILL_DIR`→`_FLOW_DIR` pointing at `pex/flows` (1649) and `_skill_files`→
   `_flow_files` (1656); repurpose `test_loader_strips_frontmatter`→`test_loader_reads_flow_prompt`;
   keep `test_few_shot_tools_are_allowlisted` (1695 `load_flow_prompt`, drop `or ''`),
   `test_flow_tools_are_registered`, `test_skill_system_ends_with_reminder` (import 1647 + call 1718 →
   `build_flow_system`), `test_reminder_is_agentic`; update `tool_call`→`flow_execute` (556/557) and
   `skill_call`→`flow_reply` (566/567) with `flow_prompt=''`. Keep all other test-function and loop-var
   names as-is (only the one repurpose rename) to hold the diff deterministic.
10. `helper_ref.md`: line 36 only.

## Verification gate (both builders, before reporting done)

- `grep -rn` for `skill_call`, `\btool_call\b` (method), `build_skill_system`, `build_skill_messages`,
  `load_skill_template`, `load_skill_meta`, `_split_frontmatter`, `_resolve_skill_path`, `_SKILL_DIRS`
  in `backend/` + `for_orchestrator.py` → nothing (excluding `_openai_streaming_tool_call`,
  `tool_call_id`, `tool_calls`).
- `grep -rn '<task>'` in `starters/*.py` and `for_pex._default_starter` → nothing.
- Free suite green, ZERO skips, from `assistants/Hugo` cwd (cwd + sys.path[0] per the test-cwd note):
  `pex_unit_tests.py nlu_unit_tests.py mem_unit_tests.py model_unit_tests.py`.
- Composition eyeball (5.3.10.1) for audit/outline/write: `<task>` gone from the user message; the same
  task/tool guidance present under `--- {Flow} Flow Instructions ---` in the system prompt; audit's user
  message carries a `<post_content>` block; nothing else vanished.
- Net diff is deletion-heavy (16 frontmatter blocks, the `<task>` blocks, one test, four loader
  members) against four one-line `.md` adds, two loader one-liners, and one `extra_resolved` line.

## Ponytail review (consolidation round — flag added structure / kept duplication)

- +1 `git mv` 16 files + strip frontmatter: pure move/deletion, no new structure.
- +1 delete four loader helpers + `import yaml`: deletion.
- +1 two one-liner loaders replace the fuzzy two-dir search: right altitude, no shared helper for two
  one-liners.
- +1 `_default_starter` + 13 starters drop `<task>` synthesis: removes the task/tool-order duplication
  that lived in both the starter and the flow `.md`.
- +1 retire `test_skill_tools_match_flow` + `_PEX_AGENT_SKILLS`: deletion of a test that only policed
  the now-deleted frontmatter.
- +1 A1 skip 5.3.7.5 Tools trim: avoids a non-deterministic, low-value edit; the allowlist test still
  guards names.
- +1 keep `compose.py` fallback verbatim: surgical, no unrelated rewrite.
- +1 two directories (`pex/flows/` + `pex/skills/`) with exact globs: the lazier option — it removes
  any exclusion list for `plan.md`, so it deletes logic rather than adding it, despite `pex/skills/`
  holding one file.
- -1 param `skill_prompt`→`flow_prompt` touches six extra call sites vs leaving it: minor churn, but it
  finishes the rename and removes a permanent half-named method — worth it.

**Net: +7.** Deletion-dominant, no speculative structure, no duplication kept alive. Ship it.
