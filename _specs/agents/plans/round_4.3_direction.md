# Round 4.3 Build Direction (DoE)

AUTHORITATIVE SPEC: `_specs/agents/plans/round_4.3_spec.md` — read it in full and implement it
exactly (Decision 1, 2, and 3 recommendations). Flag disagreements in notes; never silently
deviate. All paths below are relative to `assistants/Hugo/` unless they start with `shared/` or
`_specs/`.

## Non-negotiable orders (repeat of the round orders)
1. The spec is authoritative: D1 floor of 5 for the 13 priority PEX skills (34 exemplars);
   D2 per-turn read counter, `limits.max_reads: 3`, corrective error `read_cap` in
   `_guarded_call`, count only successes; D3 13 contrastive NLU flow-detection exemplars,
   floor 6 per intent, write/rework boundary priority.
2. Exemplar authorship: NO "Kitty Hawk"; multi-word realistic post titles; short realistic user
   utterances (10-40 words, implicit, anaphora); no em-dashes in utterances; agentic shape
   (tool call or prose reply), never a JSON blob — EXCEPT the detection exemplars, whose house
   shape ends in the existing ```json output block (`reasoning`/`flow_name`/`confidence`); keep
   that. Rotate topics: no topic reuse within a skill file. Match `write.md` block shape for PEX
   skills; match the `<positive_example>`/`<edge_case>` block shape for detection exemplars.
3. Plain language: never write seam, envelope, steward/stewardship, hydrate (the
   `rehydrate_flow` identifier is exempt), sentinel, byte-identical, genuinely, honestly,
   load-bearing, delve, tighten, "staging" a flow (say stacking on), or "catalog flows" (say
   existing flows).
4. Structured output: call StructuredOutput ONCE, short payload; work product goes in files
   (write your diff summary to a file); every string field under 150 words.
5. Project rules per repo CLAUDE.md: simplicity first, surgical changes, no defensive
   programming, 100-char lines.
6. Git: no branches, no PRs, never run git commit/push.

## Path corrections (the round orders contain two stale labels)
- Detection exemplar files live at `backend/prompts/experts/*_flows.py` — NOT
  `backend/prompts/nlu/experts/`. (`backend/prompts/nlu/` holds only `*_slots.py`.)
- The spec's pseudo-code says reset in `_orchestrate`; no such method exists. The per-turn reset
  home is `execute()` (see below), matching the `self._injected` pattern the spec itself cites.

## Part B — read cap, exact placements (adjudicated; both SWE plans agreed)
File: `backend/modules/pex.py`
1. `__init__` after line 91 (`self.max_corrective = ...`):
   `self.max_reads = config['limits']['max_reads']`
2. `__init__` beside line 151 (`self._injected = False`): initialize `self._reads = 0`.
3. `execute()` after line 291 (`self._injected = False`): reset `self._reads = 0` — this is the
   per-turn reset.
4. `_guarded_call`: insert a third branch between the duplicate-call `elif` (line 437-440) and
   the final `else` (line 441):
   ```python
   elif tool_use.name in READ_ONLY_DOMAIN_TOOLS and self._reads >= self.max_reads:
       result = {'_success': False, '_error': 'read_cap',
                 '_message': f'Already used {self.max_reads} read-only lookups this turn. '
                             'Stack on and activate a flow, or respond to the user.'}
   ```
5. In the existing `else`, increment AFTER the `_success` normalization lines (443-444), not
   before (deviation from spec pseudo-code order, flagged and adopted: same behavior for every
   real tool, and no KeyError if a result ever lacks `_success`):
   ```python
   if tool_use.name in READ_ONLY_DOMAIN_TOOLS and result['_success']:
       self._reads += 1
   ```
   Count only successful read-only calls; a failed lookup stays retryable (D2).

File: `shared/shared_defaults.yaml` — add inside the existing `limits:` block, after
`max_corrective` (line 93):
`max_reads: 3                     # per-turn cap on direct read-only domain-tool calls`

Known and accepted: `read_cap` sets `_success: False`, so it feeds the `errors` counter
(pex.py:395) toward `max_corrective`; any success resets that counter, and steering the model to
stack-and-activate is the intended behavior.

## Part A — PEX skill exemplars (34 new)
Files: `backend/prompts/pex/skills/*.md`. Raise to floor 5:
- `propose.md` 1→5 (+4); `chat/cite/compose/promote/release/schedule.md` 2→5 (+3 each);
  `audit/brainstorm/browse/find/outline/summarize.md` 3→5 (+2 each).
- Do NOT touch `compare/rework/refine/write.md`. `plan.md` (0 exemplars) is out of scope — leave
  it alone.
- Shape per `write.md`: `### Example N: <descriptor>` → `Resolved Details:` (Source line with
  post/section ids + `User asked:`) → numbered `Trajectory:` of real tool calls → optional
  `Final reply:`. The 5 slots per skill should span: direct act, soft direction →
  `handle_ambiguity(level='confirmation')`, ambiguity/error fallback, sibling fallback via
  `call_flow_stack(action='fallback')`, and (where relevant) a scratchpad-informed act.
- Only use tools declared in each skill's frontmatter/tool list
  (`test_few_shot_tools_are_allowlisted` will catch violations).
- Keep the Source line in house format (`Source: post=<id>, section=<sec_id>`); if the section
  is unresolved, say so in the `User asked:` line, not the Source line.

## Part C — detection exemplars (13 new)
Files: `backend/prompts/experts/{research,draft,revise,publish,converse}_flows.py`, `EXAMPLES`
string. Raise to floor 6: research 4→6, draft 4→6, revise 4→6, publish 3→6, converse 2→6.
- Author contrastive boundary cases, not filler: pin `write` (single-section/sentence-level) vs
  `rework` (multi-section/post-level argument), and the `refine`/`compose`/`write` boundary,
  with medium-scope utterances that force the call. Publish/converse: in-intent + edge cases
  into adjacent intents.
- Keep the existing block shape: `<positive_example>` (or `<edge_case>` for boundary cases —
  both tags are in the contract, see `backend/prompts/experts/__init__.py`) → `## Conversation
  History` → `## Output` → ```json with `reasoning`, `flow_name`, `confidence`.
- Existing exemplars contain em-dashes; do not edit them (surgical changes). New utterances must
  not contain em-dashes.

## Verification (spec's plan, mapped to existing homes)
- Run `pytest` with cwd + `sys.path[0]` = `assistants/Hugo` (test-cwd note). All green; a skip
  counts as a failure.
- Grep the touched files: 0 hits for "Kitty Hawk" and for em-dashes in new utterances (AC-1).
- AC-2/AC-3: extend `utils/evaluation_suite/_tests/pex_unit_tests.py` — put the read-cap test
  beside `test_identical_consecutive_call_is_deduped` (line 452, reuse the `orch_agent`
  fixture): 4 varied-arg successful read-only calls → calls 1-3 dispatch, call 4 returns
  `{'_success': False, '_error': 'read_cap'}` without dispatching; a failed read-only call does
  not increment. Config assertion follows `test_call_cap_read_from_config` (line 534). No new
  test files.
- AC-4: a small labeled-utterance detection check over the new write/rework contrastive cases,
  beside the existing flow-detection harness in `utils/evaluation_suite/_tests/model_tests.py`.
- AC-5..7: the live 8-scenario gate (B01.C01, B01.C04, B02.C01, B02.C02, B03.C01, B04.C01,
  B05.C01, B06.C01) is run by the orchestrator after the build; report deltas vs completion
  0.5152 / tool_match 0.0864 / mean turn 12.4 s.

Write your diff summary to `_specs/agents/plans/round_4.3_build_<your-role>.md`; keep the
StructuredOutput payload short.
