# Spec Sheet — 4.2 · Inject the closing reminder

Round: 4.2 · Source: `_specs/_review/step_4_pex.md` §4.2 + Decisions · Milestone: Master Plan
Step "1 · Hugo replies" (`master_plan.md:73,99-103`). Status: **signed off by Derek 2026-07-02**;
agentic contract confirmed, with the explicit fallback that if parsing/contract issues appear in
practice we revisit and switch (reopening E9).

## 1 · Feature definition & user story

Every per-flow sub-agent prompt (the `prompts/pex/skills/*.md` bodies assembled by
`build_skill_system`) currently ends with the skill body. Nothing restates the output contract at
the end of the system prompt — the highest-recency position, which the model weights most. The
style guide reserves slot 7 for exactly this: a one-liner closing reminder appended by the Prompt
Engineer after the body/exemplars (`style_guide.md:137,142`).

Two constants exist for it but neither is used, and both carry the wrong (JSON) contract: per the
4.1 taxonomy, sub-agent prompts are **agentic** — they finish by calling a tool or replying in
plain prose, not by emitting JSON (`step_4_pex.md:54-65`).

**User story.** As a Hugo user, when I say "draft an intro about X", the reply is plain prose (or
a persisted tool action) — never a JSON blob, a markdown-fenced object, or a restatement of the
skill instructions. The closing reminder is the cheapest lever for that: one static line at the
end of the cacheable system prompt.

**Glossary.** The 8-slot prompt format (`style_guide.md:127-138`): grounding data / role+task /
detailed instructions / keywords+options / output shape / exemplars / closing reminder / final
request — the reminder is slot 7. Two-layer output contract: structure reaches PEX through
schema-validated tool calls, the Session Scratchpad completion entry (`{flow, summary, metadata}`
appended on flow completion per `modules/pex.md`), and the TaskArtifact (the policy's return to
PEX). The model's free text is the user-facing reply only — it carries no parsed structure, which
is why the reminder forbids JSON-wrapped replies.

## 2 · Requirements (each traced — nothing invented)

| # | Requirement | Trace |
|---|---|---|
| R1 | Append the closing reminder as the **final** element of the assembled per-flow system prompt, after the skill body. | `step_4_pex.md:76-78,90`; Decisions `:31-32`; `style_guide.md:137,142` |
| R2 | Repurpose `SLOT_7_REMINDER` (`general.py:12`) to the agentic reminder text (tool call OR plain prose; no JSON wrapping, no instruction restating). | `step_4_pex.md:78,82-84`; Decisions `:33-34` |
| R3 | **Delete** `JSON_REMINDER` (`general.py:10`) — zero call sites, contradicts the agentic contract. | `step_4_pex.md:78,84`; Decisions `:33` |
| R4 | Single-shot NLU prompts keep their JSON demands via `_TASK_SUFFIXES` (`prompt_engineer.py:20-37`) — do not touch them (4.1 carve-out). | `step_4_pex.md:94-95` |
| R5 | After the change: `SLOT_7_REMINDER` has a live call site in `for_pex.py`; `JSON_REMINDER` is gone from the codebase. | `step_4_pex.md:209` (§Verification) |
| R6 | Offline gate suites stay green — baseline 324 passed / 0 skipped / 0 failed. | `step_4_pex.md:205`; `master_plan.md:229` |

**Notes (consequences of R1-R3, not new requirements):**
- The `build_skill_system` docstring (`for_pex.py:52-53`) says "there is no shared suffix" — that
  sentence becomes false and must be corrected in the same diff.
- Cache safety: the reminder is static per flow, so appending it inside the system prompt does not
  churn the cache key (`components/prompt_engineer.md` §Prompt Caching). No change to the
  `cache_control` markers (`prompt_engineer.py:295,311`).
- Both entry points get the reminder for free: `skill_call` and `tool_call` both route through
  `build_skill_system` (`prompt_engineer.py:188,211`) — no other assembly path exists.

## 3 · Pseudo-code (verified against current source)

**Drift check on the sub-plan's sketch (`step_4_pex.md:80-92`):** the `parts` list matches
`for_pex.py:58` exactly. Current code at `:59-61` hoists `flow_name = flow.name().capitalize()`
into a local before the f-string; the sketch inlines it — keep the existing local (surgical-change
rule). The sketch omits the docstring fix (R6 note). Exact current line numbers confirmed
2026-07-02: `JSON_REMINDER` at `general.py:10`, `SLOT_7_REMINDER` at `general.py:12`,
`build_skill_system` at `for_pex.py:49-62`, `_TASK_SUFFIXES` at `prompt_engineer.py:20-37`.

```python
# general.py — repurpose the constant (was 'Respond with ONLY valid JSON...'); delete line 10
SLOT_7_REMINDER = ('Finish the turn by EITHER calling a tool OR replying to the user in plain '
                   'prose. Do not wrap your reply in JSON or restate these instructions.')

# for_pex.py — add import, append the reminder last, fix the stale docstring sentence
from backend.prompts.general import SLOT_7_REMINDER

def build_skill_system(base_system:str, flow, skill_prompt:str|None) -> str:
    """System prompt = persona + intent prompt + ambiguity block + skill body + closing reminder.
    ... (replace 'there is no shared suffix' with: the slot-7 closing reminder is the shared
    suffix — it restates the agentic output contract at the highest-recency position) ..."""
    ...
    parts = [base_system, '\n\n', intent_prompt, '\n\n', AMBIGUITY_AND_ERRORS]
    if skill_prompt:
        flow_name = flow.name().capitalize()
        parts.append(f'\n\n--- {flow_name} Skill Instructions ---\n\n{skill_prompt}')
    parts.append(f'\n\n{SLOT_7_REMINDER}')        # NEW: slot-7 closing reminder, always last
    return ''.join(parts)
```

Diff size: ~5 changed lines across 2 files, plus the new test. No new concepts, attributes, or
flags; no signature changes; no defensive guards.

## 4 · Test plan — coverage doctrine: Evals lead → Traces → Tests → greps

Per Derek's coverage doctrine (2026-07-02): coverage is a weighted mix of the three eval levels
(`_specs/utilities/evaluation.md` — Tests / Traces / Evals). Evals are the headline gate; unit
tests must not grow the suite beyond checks that can genuinely fail.

### 4a · E2E Agent Evaluations (headline gate)

The closing reminder shapes **every** sub-agent reply, so the judge is the live corpus. From the
96 scenarios under `utils/evals/datasets/scenarios/`, these 8 (all unflagged) were selected for
maximum diversity of flows and reply shapes:

| Scenario | Why it judges 4.2 |
|---|---|
| B01.C01 | Canonical straight build (find→outline→compose→release) — the literal "Hugo replies" user story, publish end. |
| B01.C08 | Plan-chain (fan_out, step_0 check) + chat + audit + release — plan orchestration, converse, and publish in one convo. |
| B01.C11 | Plan (mix, step_0) + **specific** ambiguity with a user reject at turn 3 — clarify reply shape inside a plan-chain. |
| B01.C12 | write→audit→cite→release — publish-heavy; citation reply shape. |
| B01.C14 | browse→find→summarize→outline→compose→audit — longest chain (6 flows); research prose replies where JSON leakage shows first. |
| B02.C15 | **Confirmation** ambiguity with a user reject at turn 5, ends in release — clarify + rejection + publish. |
| B03.C03 | compose→rework→audit→**propose** — propose has the weakest exemplar count (1, per §4.3), so it leans hardest on the reminder. |
| B03.C07 | chat→brainstorm→outline→chat — Converse-led, pure-prose voice turns where instruction-echo or JSON wrapping is most visible. |

Combined flow coverage: 15 distinct flows. Gap: **refine** appears in none of the 8; if Derek
wants it covered, swap B01.C01 → B03.C11 (plan→outline→compose→refine). No new scenarios are
needed — the corpus already exercises every reply shape 4.2 touches.

**Run command** (cwd = `assistants/Hugo`; live LLM run):

```
python utils/evals/run_evals.py --level evals --metric completion
```

Caveat: the runner globs **all** scenarios (`run_evals.py:68`) — no per-scenario filter exists.
The gate number is therefore corpus-wide; QA judges the 8 selected scenarios from the runner's
per-turn log lines (`run_evals.py:59` prints `<convo_id> turn N: ok|reason`). Do not add a
subset flag for this — reading 8 convo IDs out of the log is enough.

**What pass looks like.** Headline metric is `completion_rate` — per-turn task completion via
`scorers/completion.is_completed`, graded by `gates.py` against `baselines/evals.json`. The
scorer judges completion from the reply plus the TaskArtifact's `origin` (the policy's return to
PEX); flow summaries live only as the Session Scratchpad completion entry (`{flow, summary,
metadata}`) — there is no standalone completion object. The gate's baseline entry for this
metric is currently `target: 0.9, expected_fail: true, value: null` (red-green model:
the gate reports `xfail` / exit 0 while the feature set is unbuilt). Pass for 4.2 = (a) gate
exit 0, (b) every user turn of the 8 selected scenarios logs `ok`, (c) no JSON-wrapped or
instruction-restating reply in those turns (QA reads the transcripts). Once the milestone
stabilizes, stamp with `--record` so any later drop turns the gate red.

### 4b · Observability Traces

| ID | Check | Expected |
|---|---|---|
| TR1 | Trace-gate smoke run. 4.2 changes no exemplars, so trajectory scores are expected unchanged; a shift flags the reminder wording for review. | pass, no score regression |

**Milestone-view flag: traces need attention.** TR1 is the only trace check applicable to 4.2,
and the approved-trajectory dev set is still thin (Step 1 deliverable). Growing approved traces
should be prioritized within "1 · Hugo replies"; 4.2 does not block on it.

### 4c · Model Unit Tests (suite must not grow beyond genuinely-failable checks)

Baseline before any code: with cwd set to `assistants/Hugo` (test-cwd gotcha,
`master_plan.md:230`):

```
python -m pytest utils/tests/test_artifacts.py utils/tests/unit_tests.py \
    utils/tests/test_nlu_module.py -q
```

Expected baseline: **324 passed, 0 skipped, 0 failed**.

| ID | Test | Expected |
|---|---|---|
| T1 | `test_skill_system_ends_with_reminder` — for a real flow from `flow_classes`, `build_skill_system('base', flow, 'skill body')` ends with `SLOT_7_REMINDER`. Parametrize `skill_prompt` over `['skill body', None]` so the no-skill path is covered too. | endswith holds in both cases |
| T2 | `test_json_reminder_deleted` — `from backend.prompts import general; assert not hasattr(general, 'JSON_REMINDER')`. | passes (constant gone) |
| T3 | `test_reminder_is_agentic` — `SLOT_7_REMINDER` contains no demand for JSON output (e.g. `'ONLY valid JSON' not in SLOT_7_REMINDER`) and `_TASK_SUFFIXES['classify_intent']` still does (R4 guard). | passes |
| S1 | Full offline gate rerun (command above). | 324 + T1-T3 passed / 0 skipped / 0 failed |

T1-T3 qualify under the doctrine — each can genuinely fail (wording regressed, constant
resurrected, JSON demand leaked into the reminder). `test_artifacts.py` parametrizes over the
skill `.md` files (frontmatter `tools:` lints) — 4.2 adds no exemplars, so those lints are
untouched.

**Deletion candidates for the DoE** (adjacent to files this round touches; PM deletes nothing):

- `test_artifacts.py:102-106` — the two `pytest.skip` branches in `test_skill_tools_match_flow`
  are dead paths: `ORPHAN_SKILLS` (`:38`) and `SKILL_TO_FLOW` (`:34`) are both empty containers,
  and the 324/0-skips baseline confirms the branches never fire. Per the skip-counts-as-failure
  rule, an orphan skill should fail loudly, not skip. Candidate: delete both branches plus the
  two empty containers.
- Sweep result: no `assert True`-style always-pass tests found in `test_artifacts.py` or
  `unit_tests.py`. Noted, not a deletion: `test_few_shot_tools_are_allowlisted`
  (`test_artifacts.py:125-135`) passes vacuously for skills with no `## Few-shot` block, but it
  still fails on real violations, so it stays.

### 4d · Greps (QA manual)

| ID | Check | Expected |
|---|---|---|
| G1 | `grep -rn JSON_REMINDER assistants/Hugo --include='*.py'` | zero hits |
| G2 | `grep -rn SLOT_7_REMINDER assistants/Hugo --include='*.py'` | hits in `general.py` (definition), `for_pex.py` (call site), tests |

## 5 · Simplification opportunities

- **No new eval scenarios and no runner subset flag.** The existing 96-convo corpus already
  exercises every reply shape 4.2 touches; the 8 selected scenarios are judged from the runner's
  per-turn log, so no filtering feature is added. (Supersedes the pre-doctrine "no E2E eval"
  stance — evals now lead per Derek's 2026-07-02 coverage doctrine.)
- **No second reminder constant.** One reminder serves both `skill_call` and `tool_call` (see D1);
  a per-entry-point variant would be a new concept for zero measured benefit.
- **No call-site edits in `prompt_engineer.py`** if D2 option A is chosen — both callers inherit
  the reminder from the single assembly function.
- **Sketch drift is cosmetic** — keep the existing `flow_name` local rather than matching the
  sketch's inlined f-string; smaller diff.

## 6 · Open decisions for Derek

Locked and NOT re-asked: inject the reminder last, delete `JSON_REMINDER`, repurpose
`SLOT_7_REMINDER`. The four below are the remaining genuine choices inside those locks.

### D1 — Exact reminder wording

`build_skill_system` serves both entry points: `tool_call` (tools exposed) and `skill_call`
(no tools — the policy parses the text). The wording must fit both.

- **A (sub-plan draft, verbatim):** `'Finish the turn by EITHER calling a tool OR replying to the`
  `user in plain prose. Do not wrap your reply in JSON or restate these instructions.'`
  - Pro: exactly the sketched text; the tool nudge helps the agentic loop terminate cleanly.
  - Con: mentions tools in `skill_call` prompts where none are offered (harmless — a model with no
    tools just takes the prose branch — but slightly inaccurate).
- **B (tool-neutral):** `'Close the turn by replying to the user in plain prose. Do not wrap your`
  `reply in JSON or restate these instructions.'`
  - Pro: literally true for both entry points.
  - Con: drops the "or call a tool" permission — in `tool_call` a model mid-loop could read this
    as "stop calling tools now", cutting agentic work short. Also drifts from the sketch.
- **C (two variants, one per entry point):** a second constant, `build_skill_system` picks by a
  new param.
  - Pro: each prompt gets a precisely true sentence.
  - Con: new concept + signature change for a nuance with no observed failure; violates minimal
    diff. Rejected unless A/B measurably misbehave.

**Recommendation: A.** "EITHER … OR" grants permission, it doesn't demand a tool; it is safe in
both contexts and it is the text the sub-plan already reviewed.

### D2 — Code placement of the append

- **A (inside `build_skill_system`, per the sketch):** `parts.append(f'\n\n{SLOT_7_REMINDER}')`
  at `for_pex.py:62`, plus one import from `general`.
  - Pro: one edit covers both call sites and any future caller; matches the sub-plan's pseudo-code.
  - Con: `style_guide.md:142` says "Slot 7 is appended by the Prompt Engineer" — strictly that
    points at the component, not the assembly helper (the helper is owned/called by the Prompt
    Engineer, so this is arguably satisfied).
- **B (at the two call sites in `prompt_engineer.py:188,211`):**
  `system = build_skill_system(...) + '\n\n' + SLOT_7_REMINDER` — `general` is already imported
  there (`:15`).
  - Pro: literal reading of the style guide; no new import in `for_pex.py`.
  - Con: two edits that must stay in sync; a future third caller silently loses the reminder.
- **C (fold the text into `AMBIGUITY_AND_ERRORS`):**
  - Pro: zero structural change.
  - Con: lands mid-prompt when a skill body follows — defeats the entire recency purpose. Rejected.

**Recommendation: A.** Single source of truth for assembly; the style-guide sentence describes
ownership, not a file name.

### D3 — Test placement

- **A (`utils/tests/test_artifacts.py`):** add T1-T3 as a small "closing reminder" section.
  - Pro: this file already holds prompt-conformance lints and imports `flow_classes` + the skill
    loader — the fixtures T1 needs are already there; it is in the offline gate.
  - Con: the file's charter is skill `.md` artifacts; assembly logic is a slight stretch.
- **B (`utils/tests/unit_tests.py`):** add a `TestSkillPromptAssembly` class.
  - Pro: component-behavior tests live here; `PromptEngineer` is already imported.
  - Con: needs its own flow fixture; the file is already the largest suite, and the check is a
    prompt-artifact lint in spirit.
- **C (both):** duplicate coverage.
  - Pro: none beyond redundancy. Con: two places to update when wording changes. Rejected.

**Recommendation: A.** Prompt-conformance checks belong with the other prompt lints, and the
parametrization plumbing is free there.

### D4 — Constant name: keep `SLOT_7_REMINDER` or rename to `CLOSING_REMINDER`

- **A (keep `SLOT_7_REMINDER`):**
  - Pro: zero extra churn; the sub-plan, style guide (slot 7), and verification greps all use this
    name.
  - Con: "slot 7" comes from the 8-slot format that §4.1 partially carved out; the number is
    opaque to a reader who hasn't seen `style_guide.md:137`.
- **B (rename to `CLOSING_REMINDER`):**
  - Pro: self-describing; survives any future style-guide renumbering.
  - Con: breaks the verification grep as written in `step_4_pex.md:209` (it names
    `SLOT_7_REMINDER`), so the sub-plan text would need a matching edit; extra diff for zero
    behavior change.

**Recommendation: A.** The style guide still defines slot 7 for sub-agent/tool prompts — the name
is accurate where it applies. Rename only if the 8-slot table itself gets reworked later.
