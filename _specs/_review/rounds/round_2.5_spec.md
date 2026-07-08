# Spec Sheet — 2.5 · Config-promote the PEX loop bounds + per-flow call caps (E10)

Round: 2.5 · Source: `_specs/_review/round_2_pex.md` §2.5 + master plan decision E10
(`master_plan.md:207`) · Milestone: Master Plan Step "1 · Hugo replies" (`master_plan.md:99-108`).
Status: **signed off 2026-07-03 with one amendment** — build order 2.2 (done) → **2.5** → 2.6 → 2.3.

> **Amendments (the user, 2026-07-03).** (1) **The `resilience` section is renamed `limits` outright**
> — "We should not have a 'resilience' section. Everything under this umbrella should go under the
> new 'limits' name." Everywhere this sheet says `resilience`, read `limits`. The final `limits:`
> section in `shared_defaults.yaml` = the old resilience contents (`tool_retries`, `llm_retries`,
> `fallback_model`, `max_recovery_attempts`) plus the five promoted keys flat (`max_rounds: 8`,
> `max_corrective: 3`, `max_tool_calls: 8`, `extended_tool_calls: 16`, `extended_call_flows:
> [audit, refine, rework, compose]`); the orphan `recovery:` section is deleted (D3 otherwise
> stands). Because the shared file serves all three assistants, the rename fans out: Hugo, Dana,
> and Kalli each swap `'resilience'` for `'limits'` in `_REQUIRED_SECTIONS` and rename the
> `self._resilience` handle to `self._limits` in their `prompt_engineer.py`; Hugo reads
> `config['limits']` directly (required section — no `.get`), Dana/Kalli keep their existing
> read style, rename only. Expected files: 11. (2) **Diff-size guard:** a config round should not
> balloon — past 10 files the DoE steps in and justifies every file before applying; here the 11th
> file is forced by the shared-file fan-out and is pre-justified. This guard is specific to THIS
> round (a config promotion has no business touching many files) — it is not a universal pipeline
> rule. D2/D4 stand as recommended.

## 2.5.1 · Feature definition & user story

Three acting-loop budgets are hardcoded today: the orchestrator round budget, the consecutive-
tool-failure cap, and the per-flow tool-call cap inside `tool_call`. Two config keys that were
meant for this territory exist but nothing reads them (`resilience.max_recovery_attempts`,
`recovery.max_repair_attempts`). E10 is decided: **each bound is declared in exactly one place**,
that place is config under `resilience` (the same pattern as the already-config-driven
`compression`, read at `agent.py:122`), and the two dead recovery keys collapse into one. The
nudge/wrap-up/fallback message strings stay code constants.

This is a behavior-preserving refactor: the values (8 / 3 / 8 / 16) do not change. What changes
is where they live and who can tune them.

**User story.** As a developer tuning Hugo (e.g. the D6 latency trims from round E1, which listed
"cap PEX rounds lower" as a candidate), I change one number in `shared_defaults.yaml` and rerun
the 8-scenario gate — no code edit, no risk of touching one of the two places a value is
duplicated and missing the other. As a config reader, I find every loop budget in the
`resilience` section instead of grepping module constants.

## 2.5.2 · Requirements (each traced — nothing invented)

| # | Requirement | Trace |
|---|---|---|
| R1 | `_MAX_ROUNDS` and `_MAX_CORRECTIVE` move from module constants (`pex.py:21-22`) to config keys under `resilience`; PEX reads them from config. | `round_2_pex.md:132-135`; E10 `master_plan.md:207` |
| R2 | The per-flow call-cap logic (`prompt_engineer.py:215-217`) reads its numbers and its flow list from config under `resilience` — no inline flow-name list in code. | `round_2_pex.md:134,153-156` |
| R3 | Collapse the two dead recovery keys into one: exactly one recovery-attempts key remains in `shared_defaults.yaml`; the other (and its section, if emptied) is deleted. | `round_2_pex.md:129-135`; E10 |
| R4 | Message strings (`_FALLBACK_MESSAGE`, `_NUDGE_MESSAGE`, `_WRAP_UP_MESSAGE`, `pex.py:23-27`) stay code constants — not config. | `round_2_pex.md:135-136` |
| R5 | Each bound is declared exactly once — no code-side default that duplicates the yaml value (see D4: the sub-plan's own `.get(…, 8)` sketch would violate this). | E10: "single declaration each … no duplication" |
| R6 | Values are unchanged: rounds 8, corrective 3, base cap 8, extended cap 16 for {audit, refine, rework, compose}. Offline suites stay green (baseline 208 passed / 0 skipped / 0 failed, measured 2026-07-03). | refactor scope; `master_plan.md:235-241` |
| R7 | Config validation that catches duplicate/dead keys is **out of scope** — it lands in Step 6.1. | `round_2_pex.md:159` |

## 2.5.3 · The constants being promoted — exact inventory (verified 2026-07-03)

| Constant | Value | Declared | Read |
|---|---|---|---|
| `_MAX_ROUNDS` | 8 | `backend/modules/pex.py:21` | `pex.py:332` (`for round_idx in range(_MAX_ROUNDS)`) |
| `_MAX_CORRECTIVE` | 3 | `backend/modules/pex.py:22` | `pex.py:374` (`if errors >= _MAX_CORRECTIVE`) |
| base call cap | 8 | `backend/components/prompt_engineer.py:215` (`max_num_calls = 8`) | passed to the four `_call_*_with_tools` loops (`:222-225`) |
| extended flows + doubling | `['audit','refine','rework','compose']`, `*= 2` | `prompt_engineer.py:216-217` | same |

Dead keys (zero readers anywhere in the repo — grep across all three assistants confirms):

| Key | Value | Location |
|---|---|---|
| `resilience.max_recovery_attempts` | 2 | `shared/shared_defaults.yaml:91` |
| `recovery.max_repair_attempts` | 2 | `shared/shared_defaults.yaml:93-94` (the whole `recovery:` section) |

Config surface facts the changes lean on:
- `resilience` is a required section (`schemas/config.py:19-23`); `recovery` is not — deleting it
  cannot fail validation. Dana and Kalli list the same required sections and only read
  `resilience.llm_retries` via `.get` (`Dana/…/prompt_engineer.py:57,114`), so the shared-file
  edits are safe for them.
- Domain sections fully replace shared ones (`config.py:39-43`); Hugo's `tools.yaml` does **not**
  define `resilience`, so Hugo inherits the shared section as-is.
- Config is deep-frozen (`config.py:26-31`): yaml lists become **tuples**. `flow.name() in
  <tuple>` works unchanged.
- `PromptEngineer` already holds `self._resilience = config.get('resilience', {})`
  (`prompt_engineer.py:86`) — the call-cap read needs zero new plumbing.
- PEX already holds `self.config` (`pex.py:93`); `agent.py:122` reads `self.config['compression']`
  by direct indexing — the precedent D4 follows.

## 2.5.4 · Config change (yaml)

`shared/shared_defaults.yaml` — the `resilience` section gains four keys (final shape pending
D1/D2; this shows the recommended options), and the `recovery:` section is deleted:

```yaml
resilience:
  tool_retries:                     # unchanged (:80-84)
    ...
  llm_retries:                      # unchanged (:85-89)
    ...
  fallback_model: null              # unchanged (:90)
  max_recovery_attempts: 2          # kept — the ONE recovery key (D3); wired by Step 3 escalation
  max_rounds: 8                     # was pex.py:21 _MAX_ROUNDS — orchestrator acting-loop rounds
  max_corrective: 3                 # was pex.py:22 _MAX_CORRECTIVE — consecutive failed tool calls
  max_tool_calls: 8                 # was prompt_engineer.py:215 — per-flow tool-call cap
  extended_tool_calls: 16           # cap for the heavy flows below (was the *2 at :217)
  extended_call_flows: [audit, refine, rework, compose]   # was the inline list at :216

# DELETE lines 93-94:
# recovery:
#   max_repair_attempts: 2
```

The `extended_call_flows` names are Hugo flows sitting in a shared file — acceptable because only
Hugo's code reads the keys and any domain that overrides `resilience` replaces the whole section
anyway (see D1 for the alternatives considered). A one-line comment marks them domain-specific.

No change to `schemas/tools.yaml` (inherits shared `resilience`) and no change to
`_REQUIRED_SECTIONS` in `schemas/config.py`.

## 2.5.5 · Code changes (pseudo-code, verified against current source)

**`backend/modules/pex.py`** — delete lines 21-22 (`_MAX_ROUNDS`, `_MAX_CORRECTIVE`) and the
now-stale half of the comment at :19-20; keep :23-27 (messages). Read the bounds once in
`__init__` (public attributes per the public-attrs rule — the sub-plan sketch's `_max_rounds`
underscore is dropped):

```python
# pex.py __init__ (after self.config = config, pex.py:93)
self.max_rounds = config['resilience']['max_rounds']            # direct indexing per D4
self.max_corrective = config['resilience']['max_corrective']

# pex.py:332
for round_idx in range(self.max_rounds):
# pex.py:374
if errors >= self.max_corrective:
```

**`backend/components/prompt_engineer.py:215-217`** — replace the three hardcoded lines with one
config read off the `self._resilience` handle that already exists (`:86`):

```python
# was:  max_num_calls = 8
#       if flow.name() in ['audit', 'refine', 'rework', 'compose']:
#           max_num_calls *= 2
extended = flow.name() in self._resilience['extended_call_flows']
max_num_calls = self._resilience['extended_tool_calls' if extended else 'max_tool_calls']
```

**`utils/tests/conftest.py:27`** — `minimal_config`'s `'resilience': {}` gains the four keys, so
`PromptEngineer` built from the fixture can serve `tool_call` under direct indexing:

```python
'resilience': {'max_rounds': 8, 'max_corrective': 3, 'max_tool_calls': 8,
               'extended_tool_calls': 16, 'extended_call_flows': ['audit', 'refine',
               'rework', 'compose']},
```

Diff size: ~6 changed lines in code, ~7 in yaml, one fixture edit, plus tests. No new components,
no new function signatures, no new attributes on frames/artifacts. The only new surface is the
config keys themselves (justified per decision in §2.5.10; nothing else is invented).

**Caveat for SWE plans — override semantics.** `load_config(overrides=…)` replaces whole
top-level sections (`config.py:66` does `merged.update(overrides)`). A test overriding
`resilience` must pass the full section (at minimum the four new keys — `llm_retries` readers
use `.get` chains and survive its absence). T1 below does exactly this.

## 2.5.6 · Test plan — E2E Agent Evaluations (headline gate, ~8 of 96)

The round must prove **no behavior change** under the same values, with the heaviest coverage on
turns that actually approach the promoted budgets: long flow chains (round budget) and the four
extended-cap flows (call cap). 8 scenarios selected from `utils/evals/datasets/scenarios/`
(none flagged; overlap with the 1.1 release-gate set kept where it stresses this round):

| Scenario | Why it judges 2.5 |
|---|---|
| B01.C01 | Release-gate anchor (find→outline→compose→release) — continuity with the 1.1/2.2 baseline runs. |
| B01.C14 | 12 turns, longest chain (browse→find→summarize→outline→compose→audit) — most orchestrator rounds per session. |
| B02.C02 | 10 turns with **refine** — extended-cap flow that no prior gate set covered. |
| B02.C06 | 12 turns, audit twice + rework + compose — densest extended-cap usage in the corpus. |
| B02.C14 | 12 turns ending in release (outline→compose→rework→write→audit→release) — publish end under the round budget. |
| B03.C03 | compose→rework→audit→propose — three extended flows plus propose (1 exemplar, most likely to burn rounds). |
| B03.C07 | chat→brainstorm→outline→chat — Converse-led control: cheap short turns must be byte-equivalent in behavior. |
| B03.C11 | outline→compose→refine cycled twice — repeated extended-cap flow within one session. |

All four `extended_call_flows` (audit, refine, rework, compose) appear; B01.C14/B02.C06/B02.C14
carry the 12-turn round-budget pressure. No scenario deliberately forces 3 consecutive tool
failures — the corrective cap is covered offline (T-existing below), not by evals.

**Run command** (cwd = `assistants/Hugo`; live, ≤10 min per the 1.1 gate budget):

```
python utils/evals/run_evals.py --ids B01.C01,B01.C14,B02.C02,B02.C06,B02.C14,B03.C03,B03.C07,B03.C11
```

**What pass looks like.** Same red-green model as E1: gate exit 0; `completion_rate` at or above
the post-1.1 stamped baseline (0.36 after the high-voter trim — any drop on this refactor means
the wiring changed a value, not just its home); printed wall times read against the doctrine
targets (≤10 min gate, ≤60 s convo — informational). QA reads the per-turn log for the 8 ids.

## 2.5.7 · Test plan — Observability Traces

Carried flag from 2.2/1.1: the approved-trajectory set is still thin; this round does not grow it.
One check: a trace-level run (`run_evals.py`, default `--level traces`) on the same 8 ids —
`tool_match_rate` should be unchanged from baseline, since identical budgets must produce
identical dispatch trajectories at temp 0. A shift means a bound got mistranslated.

## 2.5.8 · Test plan — offline deterministic tests + greps

Baseline first (cwd = `assistants/Hugo`, the cwd gotcha applies):

```
python -m pytest utils/tests/nlu_unit_tests.py utils/tests/pex_unit_tests.py \
    utils/tests/mem_unit_tests.py -q
```

Measured 2026-07-03: **208 passed, 0 skipped, 0 failed** (1.9 s).

| ID | Test (in `utils/tests/pex_unit_tests.py`, class `TestOrchestratorLoop`) | Expected |
|---|---|---|
| T1 | `test_max_rounds_read_from_config` — build the agent with `load_config(overrides={'debug': True, 'resilience': {…full section, 'max_rounds': 1, …}})` (the `orch_agent` pattern, `conftest.py:52-61`); script one tool round then a text response; assert the loop stops after 1 round and routes to `_WRAP_UP_MESSAGE`. Fails if the config wire is dead (a dead wire silently keeps 8). | passes |
| T2 | `test_call_cap_read_from_config` — `PromptEngineer(minimal_config)`; monkeypatch `_call_claude_with_tools` (and family routing to `'claude'`) to capture `max_num_calls`; `tool_call` with an `audit` flow captures 16, with a `find` flow captures 8. Fails if the flow list or either cap stops flowing from config. | passes |
| T3 | `test_recovery_keys_collapsed` — `cfg = load_config()`; assert `'recovery' not in cfg`, `cfg['resilience']['max_recovery_attempts'] == 2`, and the four new keys carry 8/3/8/16. Guards the single-declaration invariant until Step 6.1's validating loader exists. | passes |
| T-existing | `test_consecutive_failures_cap_breaks_to_wrap_up` (`pex_unit_tests.py:483`) already pins corrective-cap behavior at 3 — it now exercises the config-fed value. No edit needed; it failing is the regression alarm for `max_corrective`. | still passes |
| S1 | Full offline rerun (command above). | 208 + T1-T3 passed / 0 skipped / 0 failed |

Prune-bar note: no test asserts `self.max_rounds == 8` on a default agent (T3 already pins the
yaml value; an attribute-equality copy would be a trivial signature test). T1/T2 test the wiring
by observed behavior, not by reading the attribute back.

Greps (QA manual):

| Check | Expected |
|---|---|
| `grep -rn "_MAX_ROUNDS\|_MAX_CORRECTIVE" assistants/Hugo --include='*.py'` | zero hits |
| `grep -rn "max_repair_attempts\|recovery:" shared/shared_defaults.yaml` | zero hits |
| `grep -rn "'audit', 'refine', 'rework', 'compose'" assistants/Hugo/backend` | zero hits (list lives in yaml + test fixture only) |

## 2.5.9 · Simplification opportunities

- **No multiplier key.** The sub-plan sketch's `extended_call_multiplier: 2` is dropped (D2):
  the multiplier was only ever a way to write 16, and a config key nobody would set fails the
  "no config keys nobody sets" rule. Two plain numbers instead.
- **No code-side defaults.** The sketch's `config['resilience'].get('max_rounds', 8)` would
  re-declare 8 in code — the exact duplication E10 kills. Direct indexing, crash-loud (D4).
- **No validation work.** Dead-key/duplicate-key detection is Step 6.1; this round only deletes
  the two dead keys it inherited (R3, R7).
- **No changes to Dana/Kalli.** They ignore the new keys and never read the deleted ones.
- **Messages stay put.** The three message strings are prose, not budgets — config would make
  them harder to review, not easier to tune (R4, locked).

## 2.5.10 · Open decisions for the user

Locked and NOT re-asked (E10): one declaration per bound; the home is config under `resilience`;
the two dead recovery keys collapse to one; message strings stay code constants. The four below
are the remaining genuine choices inside those locks.

### D1 — Where the four keys sit in yaml

- **A (flat keys on `resilience`, per the sub-plan sketch `round_2_pex.md:139-146`):**
  ```yaml
  resilience:
    max_rounds: 8
    max_corrective: 3
    max_tool_calls: 8
    extended_tool_calls: 16
    extended_call_flows: [audit, refine, rework, compose]
  ```
  - Pro: matches the sketch the user already reviewed; shortest reads
    (`config['resilience']['max_rounds']`); `fallback_model`/`max_recovery_attempts` are already
    flat siblings, so the section stays stylistically mixed either way.
  - Con: five flat keys crowd the section; Hugo flow names land in the shared baseline file
    (mitigated: only Hugo reads them, and domains replace the whole section when overriding).
- **B (nested subsection, matching `tool_retries`/`llm_retries` style):**
  ```yaml
  resilience:
    acting_loop:
      max_rounds: 8
      max_corrective: 3
      max_tool_calls: 8
      extended_tool_calls: 16
      extended_call_flows: [audit, refine, rework, compose]
  ```
  - Pro: groups the five related knobs under one name; consistent with the two existing
    subsections.
  - Con: `acting_loop` is a new invented config name (the plain-language bar applies to config
    keys too); reads get longer; the sketch didn't have it.
- **C (split: bounds in shared `resilience`, the flow list + caps in Hugo's `tools.yaml`):**
  - Pro: domain flow names stay in the domain file.
  - Con: `tools.yaml` defining `resilience:` **replaces the whole shared section**
    (`config.py:39-43`), forcing a copy of `tool_retries`/`llm_retries`/`fallback_model` into
    the domain file — duplication, which E10 exists to kill. Splitting across a new top-level
    domain key instead would invent a section. Rejected.

**Recommendation: A.** It is the reviewed sketch minus the multiplier, and the flow-name concern
is real but small next to C's section duplication.

### D2 — Shape of the call-cap keys

Current code (`prompt_engineer.py:215-217`): base 8, doubled to 16 for the four heavy flows.

- **A (sketch verbatim: list + multiplier, base stays a code literal):**
  `extended_call_flows: [...]` + `extended_call_multiplier: 2`; code keeps
  `max_num_calls = 8 if … else 8 * multiplier`.
  - Pro: smallest yaml; exactly `round_2_pex.md:143-144`.
  - Con: the base cap 8 stays declared in code — the very split-declaration E10 forbids (and the
    literal appears twice in the expression).
- **B (all three promoted, multiplier kept):** `max_tool_calls: 8` + `extended_call_flows` +
  `extended_call_multiplier: 2`; code computes `base * mult`.
  - Pro: every number in config.
  - Con: the multiplier is a key nobody will ever set independently of the caps — it exists only
    to derive 16. Three keys where two suffice.
- **C (two explicit caps, no arithmetic):** `max_tool_calls: 8` + `extended_tool_calls: 16` +
  `extended_call_flows`; code picks one of two numbers:
  ```python
  extended = flow.name() in self._resilience['extended_call_flows']
  max_num_calls = self._resilience['extended_tool_calls' if extended else 'max_tool_calls']
  ```
  - Pro: a tuner edits the number they mean; no derived values; one-line code read.
  - Con: 16 no longer automatically tracks a change to 8 (if you raise the base you must decide
    the extended cap too — arguably a feature: the two budgets are independent decisions).

**Recommendation: C.** It deviates from the sketch only by replacing the multiplier with the
number it produced, and it is the only option where every declared value is one a person would
actually set. (The sub-plan itself says "*Where* isn't the point — no duplication is.")

### D3 — Which recovery key survives the collapse

Both keys are dead (zero readers repo-wide). E10 says collapse to one, not zero.

- **A (keep `resilience.max_recovery_attempts: 2`, delete the `recovery:` section):**
  - Pro: the survivor sits in the section E10 designated; its comment ("max times Agent tries
    re-route before escalate") matches the Step 3 wiring of `should_escalate`, and
    `human_in_the_loop.escalation.triggers` already names `max_recovery_exceeded`
    (`shared_defaults.yaml:158`) — the key's future reader is planned. Deleting `recovery:`
    removes a whole orphan section; `recovery` is not in `_REQUIRED_SECTIONS`, so no validation
    change.
  - Con: keeps one still-unread key until Step 3 lands (marked with a comment).
- **B (keep `recovery.max_repair_attempts`, delete the `resilience` one):**
  - Pro: none found — the name is narrower ("repair" was the old slot-repair framing) and it
    strands a one-key top-level section outside the designated home.
  - Con: contradicts E10's "config under resilience"; the orphan section survives.
- **C (delete both):**
  - Pro: zero dead keys today.
  - Con: overrides E10's letter, and Step 3's escalation wiring (`master_plan.md:129-131`) would
    re-add the key within weeks — churn for nothing.

**Recommendation: A.** Matches E10, kills the orphan section, and leaves the one key whose
consumer is already on the roadmap.

### D4 — Read pattern and defaults in code

- **A (read once in `__init__`, direct indexing, no code defaults):**
  `self.max_rounds = config['resilience']['max_rounds']` in PEX; the two-line config pick in
  `tool_call` (D2-C snippet); `minimal_config` fixture updated to carry the keys.
  - Pro: single declaration holds — the yaml is the only place 8/3/8/16 exist; a missing key
    crashes at agent build (loud failure per repo doctrine, same as `agent.py:122`'s
    `self.config['compression']` precedent); reads in the loop are attribute lookups.
  - Con: any test override of `resilience` must carry all four keys (one fixture edit; noted in
    §2.5.5).
- **B (`.get()` with defaults, per the sketch `round_2_pex.md:149-156`):**
  `config['resilience'].get('max_rounds', 8)`.
  - Pro: fixtures and partial overrides keep working untouched.
  - Con: 8 is now declared in yaml **and** in code — the exact double declaration E10 forbids;
    a typo'd yaml key silently falls back to the code default and the config becomes decorative.
    The sketch predates the "no over-defending" feedback; recommend rejecting its `.get`s.
- **C (read at use site each call, direct indexing, no `__init__` attrs):**
  `range(self.config['resilience']['max_rounds'])` inline at `pex.py:332`.
  - Pro: no new attributes at all; config is frozen so there is no staleness difference.
  - Con: two long dict-hop expressions in the loop body; the call-cap read in `PromptEngineer`
    already goes through the `self._resilience` handle, so PEX doing raw hops is inconsistent
    with its neighbor for no gain.

**Recommendation: A.** Crash-loud, single-declaration, and it matches how `compression` and
`self._resilience` are already consumed. Attributes are public (`max_rounds`, not `_max_rounds`)
per the public-attributes rule.
