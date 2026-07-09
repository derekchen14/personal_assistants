# Round 2.10 (was fix 1) — The orchestrator must reliably call the terminal flow tool

**2026-07-06 update (commit `169419e`):** the create-on-missing helper (`BasePolicy.resolve_or_create`,
shipped in `a2445f6`) was REMOVED — outline/compose/write call plain `resolve_source_ids` again. Its
replacement is the `understand` dispatch tool in `pex.py`: when a flow stalls on a missing entity (a
partial ambiguity), the orchestrator calls `understand(op='contemplate')`, NLU re-routes over the failed
flow, and the corrected flow is stacked. The 32-post library's generator scripts were retired (trashed);
the seeded posts themselves stay committed in `database/content`.

Status: Options A+B SHIPPED 2026-07-03 (PR #5) with single-call staging (stackon active=true, the user amendment) — completion 0.21 -> 0.39 -> 0.52 on the 8. **2026-07-04 transcript review (B01.C01, B06.C01): the earlier "stale/misdetected flows" description did NOT reproduce** — NLU detection and orchestrator routing were correct on every turn. The remaining failures are all `missing_reference`: the eval database lacks the posts the scenarios assume (6 of the 8 gate scenarios seed zero posts), and no flow can create a post (`create_post` is in the PEX dispatch table but unused by any flow — only frontend routes call it). Next lever is eval-world seeding (draft posts for the data_aug_guide topics) + commit-then-restore around suite runs, per the user's 2026-07-04 direction. The DEFAULT_SCENARIOS prerequisite was resolved separately (fresh ~8 sample doctrine).
Owner module: **PEX** (acting loop + orchestrator prompt). See also [[round_2_pex.md]], [[round_1_evals.md]].

---

## Shared prerequisite — the standard 8-scenario run

**RESOLVED (2026-07-03): there is NO fixed 8, and no `DEFAULT_SCENARIOS` constant.** Each build samples a
**fresh ~8** scenarios, chosen closest to the feature under construction — pass them explicitly via `--ids`,
or take any n with `harness.sample(n)` (`utils/evaluation_suite/harness.py`). Keep the *count* doctrine
(~8 per judgement round); drop the *fixed list*. The "curated, frozen DEFAULT_SCENARIOS" plan in the rest of
this section is **superseded** — kept below only for the history of why the model/traces flags were
misaligned. The wiring also moved: every runner now lives under `utils/evaluation_suite/` and shares
`harness.SCENARIOS` + `harness.sample()` (see `_specs/utilities/evaluation_suite.md` for the final layout).

Why a fixed 8 (doctrine: `feedback_coverage_doctrine`, `feedback_eval_speed_doctrine`):
- A round of judgement needs ~8 scenarios, picked to span the arcs, not the whole corpus.
- The full 96-scenario traces sweep took **449s** for just 8 scenarios extrapolated — the whole corpus
  would be ~90 min of live calls. That is a release-gate activity, not an iteration loop.

### The problem this also fixes (answers "why is the NLU pass 12 but traces 8?")

Today the two paid tiers select scenarios with **different, unlinked flags**:
- `model_tests.py` selects with `--limit N` → the **first N by filename sort** (`--limit 12` = B01.C01…C12).
- `run_evals.py` selects with `--ids a,b,c` → an **explicit id list**, and with no `--ids` it runs the
  **entire corpus**.

So a "12" model pass and an "8" traces pass are not the same 8 conversations, are not chosen the same
way, and one of them silently defaults to all-96. That mismatch is an accident of the flags, not a design.

### The change

Add one shared constant and wire all three runners to it.

`utils/evals/scenarios.py` (new 6-line module, or a constant in `utils/evals/__init__.py` — reuse, do
not scatter):
```python
# The standard iteration set: one representative conversation per arc, spanning all batches.
# Curated, not first-N — keep it stable so metrics are comparable across runs.
DEFAULT_SCENARIOS = ('B01.C01', 'B01.C04', 'B02.C01', 'B02.C02',
                     'B03.C01', 'B04.C01', 'B05.C01', 'B06.C01')
```
Selection criteria for the 8 (the curator confirms coverage, then freezes the list):
straight-build, an ambiguity beat (general/partial/specific/confirmation across the set), a planning
turn, and at least one conversation from each batch B01–B06.

Then:
- `utils/evals/run_evals.py:157` — `metrics = _score_corpus(ids or None)` → default to `DEFAULT_SCENARIOS`
  when neither `--ids` nor a new `--all` flag is given. Add `--all` (`action='store_true'`) for the full
  corpus. `--ids` still overrides.
- `utils/tests/model_tests.py` — replace the first-N `--limit` default with the same id set. Keep `--limit`
  for ad-hoc sampling, but the DEFAULT (no flag) is `DEFAULT_SCENARIOS`, selected by `convo_id`, not sort
  position. Add `--all`. `_load_cases` gains an `ids` filter mirroring `run_evals._score_corpus`.
- `utils/evals/run_evaluation_suite.py:50-54` — `--traces` / `--evals` inherit the 8-default (no argv
  change needed); add a top-level `--all-scenarios` that appends `--all` to the traces/model/evals argv so
  the full corpus is one explicit opt-in.

Verification for this prerequisite: `python utils/evals/run_evals.py` (no flags) prints
`... | 8 scenarios`; `python utils/tests/model_tests.py --module nlu` scores the same 8 ids; `--all`
restores 96. Note in `round_1_evals.md` run-cadence that the default is 8.

New concept check: none. `DEFAULT_SCENARIOS` is a constant, not a concept; it reuses the existing
`--ids` / `SCENARIOS.glob` machinery.

---

## What is being changed

Make the orchestrator loop reliably **stage and activate the flow NLU already detected**, instead of
wandering through read-only domain lookups and ending the turn with plain text and no flow run.

Two coupled symptoms, one lever:
1. **The terminal flow tool never fires.** On most turns the orchestrator calls `read_metadata` /
   `read_section` / `find_posts` (the read-only allowlist) and then emits a text reply WITHOUT ever
   calling `activate_flow`. No policy runs → the artifact has no `origin` → the completion scorer reports
   `expected 'outline', got ''`.
2. **Too many read actions precede activation when it does happen.** Even on turns that eventually activate a
   flow, the orchestrator first fires 7–18 `read_metadata`/`read_section` calls. That tanks `tool_match`
   and blows the per-turn latency budget (worst turn 52.1s vs a 10s target).

The scope is: the orchestrator system prompt (`backend/prompts/for_orchestrator.py`) and, if the prompt
change is not enough on its own, a small deterministic pre-stage of the detected flow in
`backend/modules/pex.py` / `backend/agent.py`. No new components.

## Background and motivation

### Evidence (traces tier, 8-scenario subset, 2026-07-03)

```
completion_rate = 0.2059   tool_match_rate = 0.0515
B01.C01 turn 1: expected 'find', got ''   | tools 0.50 (exp [find_posts] got [find_posts, search_notes])
B01.C01 turn 2: expected 'outline', got '' | tools 0.00 (exp [generate_outline] got [])
B02.C01 turn 1: ok | tools 0.00 (exp [write_text] got [find_posts, read_metadata ×6, read_section])
B02.C01 turn 2: ok | tools 0.06 (exp [editor_review] got [read_metadata ×5, read_section ×5, inspect_post, editor_review, revise_content ×5, read_metadata])
```
- `got ''` is `artifact['origin']` (`utils/evals/scorers/completion.py:53`). Origin is set to
  `flow.name()` inside a policy run (`policies/base.py`). Empty origin ⇒ **no policy ran this turn**.
- 2 of 8 conversations completed at all (B02.C01 4/4, B01.C04 2/4); the other six went 0/n.

### Why it happens (design trace)

- NLU runs before PEX and writes the detected flow to belief (`state.pred_flows`, `state.pred_slots`) —
  `backend/agent.py:70-80`. This is correct: the standalone NLU tier detects flows at 87% (`model_tests.py`).
- The orchestrator system prompt already documents the right recipe — `read_state` → `write_state`
  op=stackon → op=update_flow (slots) → `activate_flow` (`backend/prompts/for_orchestrator.py:74-83`).
- BUT the same prompt hands the model a **read-only domain allowlist** it may call "for trivial lookups"
  (`for_orchestrator.py:92-95`; enforced by `READ_ONLY_DOMAIN_TOOLS`, `backend/modules/pex.py:46-47`, and
  `get_tools_for_orchestrator`, `pex.py:873-885`). Those tools return data, which reads as progress, so
  the model keeps pulling metadata and never commits to `activate_flow`. The loop is bounded to
  `_MAX_ROUNDS = 8` (`pex.py:21`); it burns the budget reading, then `_final_emit` forces a plain-text
  wrap-up (`pex.py:378`) — a reply with no flow behind it.
- Net: the one path that runs a policy and fires the terminal tool (`activate_flow` →
  `policy.execute(..., self._dispatch_tool)`, `pex.py:597`) is optional and under-used, while the
  exploration path is always available.

### Why it matters

`completion_rate` and `tool_match_rate` are the two headline Traces metrics (`round_1_evals.md`). At 0.21 /
0.05 the agent is, in eval terms, mostly not doing the work the user asked for. This single behavior
dominates both metrics, so it is the highest-leverage fix in the suite.

## Connected files

| File | Role |
|---|---|
| `backend/prompts/for_orchestrator.py:50-129` | `TOOL_POLICY` + `LOOP_DISCIPLINE` — the staging recipe and the read-only allowlist text |
| `backend/modules/pex.py:46-47` | `READ_ONLY_DOMAIN_TOOLS` — the allowlist the orchestrator can call directly |
| `backend/modules/pex.py:319-390` | `_run_loop` / `_final_emit` — the bounded acting loop |
| `backend/modules/pex.py:580-620` | `activate_flow` — the only path that runs a policy + fires terminal tools |
| `backend/modules/pex.py:873-885` | `get_tools_for_orchestrator` — assembles the orchestrator tool list |
| `backend/agent.py:70-85` | `_orchestrate` — NLU writes belief, then PEX runs |
| `utils/evals/scorers/completion.py:49-56` | why `origin=''` scores as a miss |
| `utils/evals/run_evals.py:88-120` | the traces harness that logs tools + scores completion |

## Decision: prompt-only vs. deterministic pre-stage

The lever is "make `activate_flow` the default action, not an option." Two ways to get there.

### Option A — Prompt-only (recommended first step)

Tighten `for_orchestrator.py`:
1. Reframe the read-only allowlist as an **exception**, not a menu: "You may call at most ONE read-only
   lookup, and only when belief lacks the entity you need. Otherwise go straight to the staging recipe.
   Reading metadata is not doing the task — `activate_flow` is."
2. Add an explicit anti-pattern line: "Never call `read_metadata`/`read_section` more than once per turn;
   if you've read once, stage and activate."
3. State the commit rule up front: "For any Research/Draft/Revise/Publish turn, the turn is not done until
   you have called `activate_flow` (or declared ambiguity). A plain-text reply with no `activate_flow` and
   no ambiguity is a failure."

- **Pros:** zero code change; reversible; keeps NLU/PEX contract untouched; the prompt already carries the
  recipe so this is a nudge, not a rewrite; byte-stable prompt preserves prefix caching.
- **Cons:** probabilistic — depends on the model obeying; may reduce but not eliminate the repeated read actions;
  needs an eval loop to confirm.

### Option B — Deterministic pre-stage of the detected flow

In the pre-hook, when NLU detected a confident single flow, stage it before the loop runs so the
orchestrator starts from an already-staged flow and its first useful move is `activate_flow`. Reuses
existing machinery only: `flow_stack.stackon(flow_name)` + `state.write_state(op='update_flow', slots=
pred_slots)` — the exact calls the orchestrator makes today, moved into code at `agent.py:_orchestrate`
(after the `understand` call, before `pex.execute`) or the top of `pex.execute`.

- **Pros:** removes the "will it commit?" coin-flip for the common case; the loop's job shrinks to
  "activate and reply"; cuts rounds → cuts latency; deterministic and testable without live calls.
- **Cons:** moves a decision NLU→PEX handled by the LLM into code — a **behavior change at the module
  boundary**, so it needs sign-off (see new-concepts below); must NOT pre-stage on Plan/Clarify turns or
  low-confidence detections (guard on `ambiguity.needs_clarification` / confidence, already available on
  state); risks masking genuine NLU misdetection by committing to it early.

### Alternatives considered

- **Remove the read-only allowlist entirely** (drop `READ_ONLY_DOMAIN_TOOLS`). Simplest possible; forces
  every domain touch through a flow. Rejected as the first move because some turns legitimately need a
  cheap lookup (find a post by title before staging) and the read-only flows exist for that; revisit if
  A+B don't land.
- **Lower `_MAX_ROUNDS`** to starve the repeated read actions. Rejected: it caps the symptom, not the cause, and
  would truncate legitimately multi-step turns.
- **Change the scorer** to credit read-only lookups. Rejected as a fix for this problem — the dominant
  signal (`origin=''`) is real; the metric is right that no work happened. (There is a *separate,
  smaller* scorer nuance below.)

### Recommendation

Ship **A first**, measure on the 8 scenarios. If completion clears ~0.6 and the repeated reads are gone, stop.
If completion improves but the repeated reads persist, add **B** (guarded to confident single-flow turns).
Both reuse existing calls; neither adds a component.

## New concepts introduced

- **Option A: none.** Pure prompt wording.
- **Option B: no new *component* or attribute**, but it introduces a new *behavior*: NLU's detection is
  auto-committed to the stack by code rather than by the orchestrator LLM. Justification: it is the same
  `stackon` + `update_flow` the orchestrator already performs, relocated for reliability; it stores nothing
  new and adds no field. Because it shifts work across the NLU/PEX boundary, it needs explicit approval per
  the "no new concepts / respect module contracts" rules (`feedback_no_new_concepts`,
  `feedback_hook_philosophy`). Flagged here; do not build B without sign-off.

## 2026-07-04 resolution — the premise was stale; the block was the empty database

Transcript review of the eight gate conversations (B01.C01, B06.C01 dumped in full; the other six
match) showed the "prompt-only Option A" premise no longer holds. On every turn NLU detected the
right flow and the orchestrator dispatched it. There is no wandering read loop to tighten. Every
remaining failure is a `missing_reference`: the flow resolves a source post, the post does not
exist, and the turn dies. Six of the eight gate scenarios seed zero posts, and no flow could create
one (`create_post` sat in the dispatch table but only the frontend routes called it). So Option A
would have moved nothing.

Two fixes shipped instead, per the user's 2026-07-04 direction:

1. **create-on-missing for the drafting flows.** A `resolve_or_create` helper on `BasePolicy`: when
   a filled source names a post that does not exist, it calls `create_post` once and re-resolves.
   Wired into `outline`, `compose`, and `write` (the flows the user sanctioned to birth a post; a
   new post is otherwise an orchestrator/UI job). Deterministic in the policy, not a sub-agent tool
   call, so there is no double-create. Covered by `TestResolveOrCreate` (two offline cases).
2. **A standing 32-post library.** `utils/evaluation_suite/library_spec.py` +
   `library_prose.py` + `seed_library.py`: 16 topics from the generating-evals guide x 2 titles,
   one outline-only draft and one full-prose draft each. Tags carry the query keywords (find_posts
   is a substring match) so scenario openers like "posts about sleeper trains" resolve. Committed
   into `database/content`; live runs mutate it, then `git restore database/content` after the gate.

## Secondary note — a real but smaller scorer nuance

`run_evals.py:109` counts every domain tool (including read-only reads) into `actual`, while the corpus
`expected_tools` lists only the terminal tool (e.g. `[generate_outline]`). So even a clean turn that reads
once then activates scores below 1.0. This is worth a follow-up decision (allow a bounded read in
`expected_tools`, or weight terminal-tool presence), but it is NOT the cause of the 0.05 rate — the
repeated reads and the missing terminal tool are. Keep it out of this fix; log it in `round_1_evals.md`.

## How to verify

1. **Baseline is captured** (already run 2026-07-03): completion 0.21, tool_match 0.05 on the 8 scenarios.
2. Apply Option A. Run the standard set:
   `python utils/evals/run_evals.py` (defaults to the 8 per the prerequisite above).
3. **Pass bar (first cut):** `completion_rate ≥ 0.60` AND no turn shows more than **one**
   `read_metadata`/`read_section` before an `activate_flow` (inspect the per-turn `got [...]` lines).
4. **Terminal-tool presence:** for each non-ambiguous, non-plan turn, the expected terminal tool appears in
   `got [...]` (e.g. an `outline` turn shows `generate_outline`). Spot-check all 8.
5. **Latency moved the right way:** worst-turn seconds drop materially from 52.1s (reads are the main cost);
   printed by the runner, not gated.
6. If B is added: a deterministic unit test in `pex_unit_tests.py` — construct a state with a confident
   single-flow belief, call the pre-stage, assert the flow is on the stack with `pred_slots` applied and
   status Active; assert Plan/Clarify/low-confidence beliefs are NOT auto-staged. No LLM.
7. Regression: `python utils/evals/run_evaluation_suite.py --tests` stays green (208).
