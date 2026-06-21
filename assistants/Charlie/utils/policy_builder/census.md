# E2E Run Diagnosis — 9/42 passing

**Run date:** 2026-04-22 · **Wall time:** 17m 44s · **Avg turn:** ~25s
**Outcome:** 9 passed, 33 failed across `TestVisionScenarioE2E`,
`TestObservabilityScenarioE2E`, `TestVoiceScenarioE2E`
(14 checkpoints × 3 scenarios = 42).

## The shape of the failure

Per-scenario outcome is identical across all three scenarios:

| step | flow              | Vision | Obs    | Voice  |
|------|-------------------|--------|--------|--------|
| 1    | create            | PASS   | PASS   | PASS   |
| 2    | outline (propose) | PASS   | PASS   | PASS   |
| 3    | outline (direct)  | FAIL   | FAIL   | FAIL   |
| 4    | refine            | FAIL   | FAIL   | FAIL   |
| 5    | compose           | FAIL   | FAIL   | FAIL   |
| 6    | rework            | FAIL   | FAIL   | FAIL   |
| 7    | simplify          | FAIL   | FAIL   | FAIL   |
| 8    | add               | FAIL   | FAIL   | FAIL   |
| 9    | polish (basic)    | FAIL   | FAIL   | FAIL   |
| 10   | inspect           | FAIL   | FAIL   | FAIL   |
| 11   | find              | FAIL   | FAIL   | FAIL   |
| 12   | audit             | FAIL   | FAIL   | FAIL   |
| 13   | polish (informed) | FAIL   | FAIL   | FAIL   |
| 14   | release           | PASS   | PASS   | PASS   |

Pattern: steps **1, 2, 14** pass; steps **3–13** fail. Step 14 passes because
the assertion expects the `tool_error` violation frame (Substack creds are
unconfigured) — not because release worked.

## Root cause — a single upstream failure in step 3

Isolated re-run of Vision steps 1–3 captured this:

```
Step 3 [outline] — 17.6s
  domain tools: ['read_metadata', 'read_metadata']
  L1 (functionality): FAIL ["expected block_type=card, got ['selection']"]
```

Step 3's utterance (`"Make an outline with 4 sections: Motivation, Process,
Ideas, and Takeaways. Under Motivation, add bullets about …"`) is *explicit
direct-mode* — the user supplied the section list verbatim. Expected
behavior per `utils/policy_builder/block_classification.md`:

- outline (propose) → `selection` block, no disk write
- outline (direct)  → `card` block, `generate_outline` commits to disk

What the agent actually did:

- Returned a `selection` block (propose-mode shape)
- Called only `read_metadata` twice — **never invoked `generate_outline`**
- No sections written to disk for `TestPost`

Because step 3 doesn't commit an outline, the post on disk has zero
sections. Steps 4–13 then cascade: refine has nothing to refine, compose
has nothing to compose, inspect reports a 0-section post, audit can't
compare-by-section, etc. Every middle-of-the-lifecycle assertion fails
for the same upstream reason.

## What the fix needs to solve

`outline` is the one flow in Hugo with a dual-stage policy (propose vs
direct). The policy picks a branch based on whether the user supplied
explicit sections. Something in that decision is defaulting to propose
mode even when the utterance enumerates sections. Candidates to inspect,
in order of likelihood:

1. **Starter / skill prompt for `outline`** — `backend/prompts/pex/starters/outline.py`
   (currently missing — falls back to `_default_starter`). Without a
   flow-specific starter, the skill sees a generic "Execute the outline
   skill" prompt and has no framing that forces it to commit when the
   user gave literal sections. This is the most probable cause.

2. **`OutlinePolicy` branching** — `backend/modules/policies/draft.py::outline_policy`.
   Verify the propose-vs-direct switch: does it route on a slot
   (`propose_mode`), on utterance heuristic, or on skill JSON output?
   If it trusts the skill's JSON, see (1).

3. **Skill's JSON contract** — `backend/prompts/pex/skills/outline.md`.
   If the skill is supposed to emit `{"sections": [...], "mode": "direct"}`
   vs `{"options": [...], "mode": "propose"}`, check whether the current
   skill consistently sets `mode` and whether the policy reads it.

## Secondary observations

- **Step 2 trajectory noise.** Vision step 2 (propose) logged tools
  `['read_metadata', 'read_metadata', 'find_posts']`. `find_posts` isn't in
  the expected list; it passed L2 because non-strict mode only requires
  `read_metadata` to be present. Consider whether propose mode should be
  calling `find_posts` at all — if not, the outline skill is reaching for
  inventory it doesn't need, adding latency.

- **Step 2 latency is high.** 32s for a purely in-memory propose call
  (no disk write, just 3 option strings). Likely the same `find_posts`
  detour above — the skill is browsing the post inventory instead of
  proposing from the utterance topic alone.

- **Step 1 is fast and correct.** 3.2s, card block, `create_post` only.
  Good baseline for turn latency — everything else is 5–10× slower.

- **Turn-time budget.** User target is 15 min for 42 turns (~21s avg).
  Observed: 17m 44s, ~25s avg. Over budget mainly because of the
  pathological 25–35s polish / outline turns, not because the suite is
  structurally slow.

## Cascading failure modes (will clear once step 3 lands)

These are effects, not independent bugs — listing so Step 5b doesn't chase
them individually:

- Step 4 (refine): no sections to refine → `generate_section` either skips
  or writes to a ghost slug.
- Step 5 (compose): `convert_to_prose` has no bullets to convert.
- Step 6 (rework), 7 (simplify), 9 (polish basic): `read_section` fails
  on non-existent sec_id.
- Step 8 (add): `insert_section` with `after=<missing>` can't anchor.
- Step 10 (inspect): returns `{section_count: 0}` which passes the
  metadata shape check but the post has no content to inspect — harmless
  in isolation, noisy in aggregate.
- Step 11 (find): works independent of post content — if it's still
  failing, it's a real find-policy bug. **Flag this one for a focused
  re-run after step 3 is fixed.**
- Step 12 (audit): depends on `compare_style` which needs sections.
- Step 13 (polish informed): consumes scratchpad from 10–12; if 11
  independently fails, 13's failure may persist.

## Recommended Step 5b order

1. **Write `backend/prompts/pex/starters/outline.py`** with the dual-mode
   framing spelled out in `pex-starters-missing.md` (the remaining-16
   starters plan). This is the smallest change that likely fixes step 3.
2. Rerun Vision steps 1–5 in isolation: `pytest
   utils/tests/e2e_agent_evals.py::TestVisionScenarioE2E -k "step_0[1-5]"`.
   Use the new `python utils/tests/e2e_agent_evals.py --progress` CLI
   during the run to watch turn times live.
3. If step 3 passes and 4 still fails, investigate refine in isolation
   before touching anything else — don't re-run all 42 until 3 & 4
   both pass on Vision.
4. Once Vision 1–5 are green, do a full 42-step run for the regression
   baseline.

## Telemetry added this session

- `utils/tests/reports/e2e_progress_latest.jsonl` — one JSON line per
  completed step (truncated at run start, appended+flushed per turn).
- Per-scenario timing table printed at class teardown (step / flow /
  duration / L1 / L2 / L3 + totals).
- `python utils/tests/e2e_agent_evals.py --progress` — snapshot CLI
  (N/42, avg turn, pass count, last-step label, ETA).
- Inline `[SLOW]` flag on any turn >60s.

## Pattern census — archived

The prior pattern-census table (observed policy/skill patterns across
12 flows with landing status) moved to
`utils/policy_builder/pattern_census_archive.md` so this file can hold
the live run diagnosis.
