# Round 2.14 — Basic Editing Path Correctness

Maps to **Master Plan · Round 2 (PEX)**. Proposal spec — evidence comes from the 2026-07-18 eval run
(report `evals_20260718_095728.json`, 8 editing-focused conversations: B01.C13, B03.C14, B04.C09,
B09.C02, B02.C06, B11.C08, B02.C16, B06.C04; completion=0.496, correctness=0.052). The goal of this
round is direct: make the basic editing path (find → outline/compose → rework/write/audit) work
end-to-end so Hugo is usable in live conversation. Three defects account for nearly every failed
turn; each has a code-verified root cause. The post-reference resolution defect (B02.C16) is split
into its own spec, `round_2.15_spec.md`, because it lives in a different layer (the content service
and the fuzzy resolver, not the flow/stack machinery).

Rulings recorded up front (Derek, 2026-07-18):

- **Audit is report-and-fix.** `AuditFlow` keeps `revise_content` and its goal line "fixes the
  drift directly" (`flows.py:268,276`). This gives more power to the single flow. The eval
  scenario references that treat audit as report-only are wrong and get realigned (T5); the flow
  does not change.
- **Revise policies parse the skill's JSON and store its `summary` line** as the completion
  summary — never the raw JSON blob (2.14.4).
- **PEX decides the mid-turn announcement from NLU's actions plus the live stack**, rendered into
  its prompt — not from a one-line note with a decline recipe (2.14.2).

---

## 2.14.1 — The entity part is a refinement, not a requirement (the biggest win)

### Problem

Evidence: B01.C13 (all 6 turns), B11.C08 (turns 2-7), B02.C06 (turns 3, 8-11), B06.C04 (turns
5-8), B09.C02 (turn 5 on). Roughly 60% of all failed turns are one loop: the user names a post
("Rework the July-gardens structure"), the post is grounded in `grounding.entities` with
`ver: true`, and the policy still asks "Which post should I rework?" every turn until the
conversation dies. The user answers the question correctly and nothing changes — the confirmation
can never satisfy the check that produced it.

### Root cause

A four-step chain, each step verified in code:

1. Three Revise flows declare a sub-post entity part on their source slot: `ReworkFlow` =
   `SourceSlot(1, 'sec')` (`flows.py:215`), `WriteFlow` = `SourceSlot(1, 'snip')`
   (`flows.py:246`), `ProposeFlow` = `SourceSlot(1, 'sec')` (`flows.py:298`).
2. `SourceSlot.check_if_filled` (`slots.py:141-147`) treats the part as a hard requirement:
   `valid = [e for e in self.values if e['post'] and e[self.entity_part]]`. A post-level request
   carries no `sec`, so the slot can never become filled — even with the right post present.
3. `_guard_entity` (`policies/base.py:169-177`) fires on the unfilled slot and declares a
   `partial` ambiguity with `entity: 'post'`.
4. `_partial_ask` (`ambiguity_handler.py:82-93`) therefore asks about the POST — the one piece the
   user already gave. The answer re-fills the post, the part stays empty, the guard fires again.

The declarations themselves are not wrong: `sec`/`snip` express the granularity the flow prefers,
and `resolve_source_ids` (`base.py:127`) uses the part to pick the best entity. The defect is that
`check_if_filled` promotes a preference into a prerequisite. A rework, write, or propose on a whole
post is a legitimate task — the policy narrows to sections itself via `read_metadata` +
`read_section`.

### Target changes

1. **`check_if_filled` requires the post only** (`slots.py:141-147`). The part, when present,
   refines; it never gates:

   ```python
   def check_if_filled(self):
       valid = [e for e in self.values if e['post']]
       self.filled = len(valid) >= self.size
       return self.filled
   ```

   `entity_part` stays on the slot — `resolve_source_ids` still prefers an entity carrying the
   part, and the fill schema still names it so NLU extracts a section when the user gives one.
2. **Purpose strings stop claiming the part is required** (`slots.py:116-119`). New wording:
   `f"at least {min_size} post" + (f", with the {entity_part} when one is named" if entity_part
   else "")` — adjust for plural `min_size` as today.
3. **No change to `_guard_entity` or `_partial_ask`.** With the post as the requirement, the
   guard's `entity: 'post'` metadata and the ask wording become accurate: they now fire only when
   the post itself is missing.

### Verification

- Isolated component check first (before any eval run): a `ReworkFlow` whose source holds
  `{post: 'x', sec: ''}` reports filled; empty source still reports unfilled and asks once.
- `resolve_source_ids` on a slot holding one post-only entity and one post+sec entity still picks
  the post+sec entity.
- A `write` request on a post with no snip runs the policy at section/post level instead of
  looping.
- Replay B01.C13: turn 1's rework runs; the six-turn clarification loop is gone.

## 2.14.2 — PEX decides the announcement from NLU's actions and the live stack

### Problem

Three related defects in how PEX handles the mid-turn `[nlu]` announcement and its run mechanics:

1. **The decision usually declines the user's newest request.** B02.C06 declined compose, write,
   and audit on consecutive turns; B03.C14 turn 3 declined the plan's own `find` step; B01.C13
   turn 4 declined the user's correction. The note (`pex.py:682-684`) offers exactly two moves and
   spells out only the decline recipe; the prompt paragraph (`for_orchestrator.py:87-91`) is
   neutral on which side should win. Declining silently drops what the user just asked for.
2. **The note's flow names go stale.** The note is built from the scratchpad entry's names, not
   the stack. B06.C04 turn 3: the note said run/decline `write` when no live `write` remained —
   the decline attempt raised `ValueError` and the turn ended in `server_error`. B02.C06 turn 9
   announced "added audit before completing audit" while the live pair was write/audit.
3. **The run button is blocked on legal retries.** The only way to re-run an Active flow is
   `manage_flows op='update' fields={'status': 'Active'}`; `_guarded_call`'s dedupe
   (`pex.py:415-422`) keys on tool name + args alone, so the identical retry is rejected even
   after NLU's fill landed new slot values in between (B01.C13 turn 2, B03.C14 turn 1). Starved of
   the legal move, the agent invents fields (`stage: "post:c7717b30"`, B09.C02 turn 5).

### Target changes

Ruling (Derek, 2026-07-18): PEX gets NLU's prior actions AND the live view of the stack in its
prompt, then makes the decision.

1. **Rebuild `_read_nlu_entry`** (`pex.py:671-684`). The note renders at read time from the live
   stack, so it can never name a dead flow, and it carries NLU's actions instead of a recipe:

   ```python
   stack = ' | '.join(f"{entry['flow_type']}·{entry['status']}"
                      for entry in self.flow_stack.to_list())
   return (f"[nlu] {entry['summary']}. Rationale: {entry['rationale']}. "
           f"Live stack (top first): {stack}. Decide with manage_flows against this stack: "
           f"the newest user message usually wins.")
   ```

2. **Rewrite the announcement paragraph** (`for_orchestrator.py:87-91`): the flow NLU stacked
   represents the user's newest message and wins by default; declining it means dropping the
   user's request this turn, so decline only when the request was already served or the
   announcement contradicts the live stack. Keep the mechanics (status='Invalid', then pop) but
   as the exception path, not the featured move.
3. **The dedupe key for `manage_flows` includes the live stack** (`pex.py:415`): append
   `json.dumps(self.flow_stack.to_list(), sort_keys=True, default=str)` to `call` when
   `tool_use.name == 'manage_flows'`. An identical retry after NLU changed the stack or filled
   slots is a new call; a true no-change repeat stays blocked.

### Verification

- The note never names a flow absent from the live stack (deterministic: announce, invalidate the
  new flow, read — the note reflects the post-invalidate stack).
- Replay B02.C06: the compose/write/audit requests run instead of being declined.
- Replay B01.C13 turn 2: the update-Active retry after NLU's fill goes through; an immediate
  identical retry with an unchanged stack is still rejected.

## 2.14.3 — Every flow is grounded before its policy runs (plan steps included)

### Problem

Evidence: B03.C14 turn 1 (summarize step), B09.C02 (refine step), B06.C04 turn 1 (refine step).
think's plan branch (`nlu.py:104-118`) stacks the marker and every step with empty slots and
returns — no `ground_flow`, no `fill_slots`, for any step including the first one it sets Active.
Each step therefore opens with an entity clarification ("Which post did you mean?") even when the
session's active post is sitting in `grounding.entities`, turning every plan into a chain of
questions the user already answered.

### Root cause

The single-flow path grounds then fills (`nlu.py:150-151`); the plan branch skips both. Later
steps have a second gap: they are promoted by `pop` inside PEX, where nothing grounds them either
— `activate_flow` (`pex.py:686-695`) sets the flow Active and runs the policy directly.

### Target changes

1. **think's plan branch grounds and fills the first step** (`nlu.py:114-116`), matching the
   single-flow path — the utterance that produced the plan is live, so the LLM fill is worth one
   call:

   ```python
   curr_flow = self.world.flows.get_flow()
   curr_flow.status = 'Active'
   state.ground_flow(curr_flow)
   state.fill_slots(self.engineer, context, curr_flow, payload, self.ambiguity_handler)
   ```

2. **`activate_flow` grounds every flow it is about to run** (`pex.py:695`), one line after the
   status write: `state.ground_flow(flow)`. This is the single choke point every run passes
   through — promoted plan steps, agent stackons, and the run button all land here.
   `ground_flow` (`dialogue_state.py:278-289`) already gates on empty `slot.values`, so a flow
   NLU filled is untouched and repeat calls are harmless. No fill for later steps: their
   originating utterance is turns old by promotion time, and `fill_slots_by_label` inside the
   policies covers step-specific gaps.

### Verification

- Deterministic: stack a two-step plan with an active post grounded → the first step's source
  holds the post before its policy runs; completing it promotes the second step, which is
  grounded at `activate_flow` without an extra LLM call.
- Replay B03.C14: turn 1's summarize runs against the active post instead of asking.

## 2.14.4 — Revise completions store the parsed summary line

### Problem

Evidence: B11.C08 turn 1, B02.C06 turn 7. The rework and write policies complete with
`text[:200]` (`revise.py:67,217,238`) where `text` is the skill's whole JSON output — so the
completion entry, the scratchpad, and downstream replies carry a truncated JSON blob instead of
the one-line summary the skill contract already requires (`pex/flows/rework.md:43,49`).

### Target change

At each of the three sites, prefer the skill's own `summary` field; the raw text stays as the
fallback for a non-JSON reply (audit's contract is a plain line — `pex/flows/audit.md:15`):

```python
parsed = self.engineer.parse(text)
summary = parsed['summary'] if parsed and parsed.get('summary') else text[:200]
self.complete_flow(flow, state, context, summary, metadata={'post_id': post_id})
```

The `.get` is legitimate here: skill output is LLM output. `revise.py:59` already parses the same
text for `done`, so the rework site reuses that `parsed` instead of parsing twice.

### Verification

- Deterministic: a skill reply that is valid JSON stores its `summary` string; a plain-text reply
  stores the first 200 characters as today.
- Replay B11.C08 turn 1: the completion summary is a sentence, not a JSON prefix.

## Out of scope (recorded, not taken)

- **Post-reference resolution** (B02.C16's missing_reference loop) — split into
  `round_2.15_spec.md`.
- **Audit behavior** — ruled report-and-fix; no flow change. Only the eval references move (T5).
- **B03.C14 turn 2's direct tool calls** (PEX answered with `find_posts`/`search_notes` without a
  flow) — re-measure after this round; the read cap and prompt already push toward flows.
- **Grounding choices with empty labels** (B03.C14) — cosmetic; re-check on the T6 rerun.
- Langfuse observability layer (deferred since round 1).

## Unresolved Issues

- **U1 — PEX's first run racing NLU's belief.** B09.C02 turns 3-4 opened with a clarification
  from a policy run that fired before NLU's detection landed (the parallel window is by design —
  round 3.4). Options: (a) the pre-loop run waits on `nlu_done` whenever an in-flight flow
  already tops the stack, keeping the parallel start only for fresh intents; (b) hold a
  clarification produced before the belief landed, re-run once at hook 3, and only then surface
  it; (c) measure first — most observed instances were the 2.14.1 entity guard, which this round
  removes. **Recommendation: (c)** — decide from the T6 rerun's traces.

## Verification

1. `run_suite.py --tests` green throughout; the suites' existing cases updated where the contract
   changed (no new tests under the moratorium — isolated component checks instead).
2. Rerun the same 8 conversations (`--ids B01.C13,B03.C14,B04.C09,B09.C02,B02.C06,B11.C08,
   B02.C16,B06.C04`) for a like-for-like read against `evals_20260718_095728.json`. Expect
   B01.C13, B11.C08, and B06.C04 to flip on 2.14.1 alone; B03.C14 and B09.C02 improve on 2.14.2
   + 2.14.3. B02.C16 stays broken until round 2.15.
3. Commit before the run; restore `database/content` after (standing eval hygiene).

## Todo List

- [ ] **T1 — 2.14.1 entity part as refinement.** `check_if_filled` requires the post only
  (`slots.py:141-147`); purpose strings reworded (`slots.py:116-119`). Isolated check: rework
  post-only fills, write without snip runs, `resolve_source_ids` still prefers the part-bearing
  entity.
- [ ] **T2 — 2.14.2 announcement + run mechanics.** `_read_nlu_entry` renders NLU's summary +
  rationale + the live stack at read time (`pex.py:671-684`); the orchestrator prompt's
  announcement paragraph flips the default to the user's newest message
  (`for_orchestrator.py:87-91`); `manage_flows` dedupe key includes the serialized live stack
  (`pex.py:415`).
- [ ] **T3 — 2.14.3 grounding at the run choke point.** think's plan branch grounds and fills the
  first step (`nlu.py:114-116`); `activate_flow` calls `state.ground_flow(flow)` before every
  policy run (`pex.py:695`).
- [ ] **T4 — 2.14.4 parsed completion summaries.** `revise.py:67,217,238` store the skill's
  `summary` field, raw-text fallback for non-JSON replies; the rework site reuses the existing
  `parsed`.
- [ ] **T5 — align audit eval references.** Update the scenario reference answers that treat
  audit as report-only to the report-and-fix ruling (agent turns are the scorer's ground truth,
  so they must reflect the ruled behavior).
- [ ] **T6 — measurement rerun + U1 decision.** Rerun the 8 ids, compare against
  `evals_20260718_095728.json`, and decide U1 from the fresh traces (build the wait/hold gate
  only if the racing clarification still appears).
