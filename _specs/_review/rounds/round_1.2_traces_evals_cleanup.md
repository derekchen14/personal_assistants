# Round 1.2 (was fix 4) — Clean up the Traces and Evals tiers (delete the dead taxonomy)

Status: **SHIPPED 2026-07-03 — Option B, with the whole suite consolidated under `utils/evaluation_suite/`.**
Owner: eval infrastructure. See also [[round_1_evals.md]] (Current-state audit), [[round_2.10_orchestrator_activation.md]].

---

## What actually shipped (supersedes the plan below)

The cleanup ran, then went further than the two options this doc weighed — the user reorganized everything into
one folder. Final state (canonical: `_specs/utilities/evaluation_suite.md`):

- **Everything under `utils/evaluation_suite/`.** Tiers are `_tests/` (deterministic `*_unit_tests.py` +
  `model_tests.py` + `conftest.py`), `_traces/` (`run_traces.py` + `traces.json` baseline +
  `tolerance_rules.md`), `_evals/` (`run_evals.py`). Entry point `run_suite.py` sits at the folder root.
- **Shared infra consolidated (6 utility files → 3):** `harness.py` (agent build/seed/clean **+** the former
  `corpus.py` locator/sampler), `scoring.py` (the former `scorers/completion.py` + `scorers/tools.py` **+**
  `gates.py` — plus the new response scorers), and `_snapshot.py`. The two `conftest.py` files merged into
  one under `_tests/`.
- **`datasets/` is now pure data** — just `scenarios/`. Review verdicts moved to `review_app/feedback/`,
  trace tolerance to `_traces/tolerance_rules.md`, and the generation guides/case-banks to the
  `generating-evals` skill dir (their sole consumer).
- **The Evals tier is built, not stubbed.** `_evals/run_evals.py` scores all **7 criteria** end-to-end; six
  are deterministic and criterion 3 (response) defaults to **offline embedding similarity**
  (`backend/utilities/embeddings.py`, `all-MiniLM-L6-v2` — the same model business context will use), with
  `--judge-response` for the LLM judge.
- **No `DEFAULT_SCENARIOS`.** Fresh per-build sampling (`harness.sample`) replaced the fixed-8 idea — see
  round 2.10's resolved prerequisite.
- Deletes were done as **`mv` into `utils/trash_suite/`** (I can't delete; the user empties it).

The delete-list and rationale below still hold; the layout/entry-point decision section is superseded by the
above. Deterministic suite: **211 green**.

## What is being changed

The Tests tier was already pruned to 5 files. This does the same for the other two tiers: **delete the
legacy trace/parity graveyard and the dead 14-step E2E lifecycle, keep only the live 3-tier machinery, and
move the suite entry point out of the `evals/` folder** (it spans all three tiers, so it does not belong
inside one of them).

Three moves, in order:
1. **Delete `utils/traces/` almost entirely** — 20 hand-written trace fixtures + the whole `parity/` oracle
   system, all built on the retired `detect_and_fill` / NLU→PEX→RES pipeline. Relocate the one live helper
   (`_clean_leftovers`) first.
2. **Purge the stale bulk from `utils/evals/`** — the dead 14-step E2E suite, its golden snapshots, the
   NLU→PEX→RES guidelines doc, and two throwaway scripts. Keep the live traces runner, scorers, gate,
   datasets, and review app.
3. **Move `run_evaluation_suite.py` up to `utils/`** — it drives all three tiers.

No behavior change to the agent. This is deletion + one relocation + one path fix.

## Background and motivation

The corpus, catalog, and pipeline all moved: 48 flows → 16, `detect_and_fill` retired, and the **RES module
removed** (PEX composes the reply). Every LLM-bearing asset built before those changes now encodes a dead
taxonomy. `round_1_evals.md`'s Current-state audit already ruled "discard, don't migrate" on each of these;
this plan operationalizes that ruling with a concrete delete-list, now that the Tests tier proved the
approach.

Two specific proofs the legacy is dead, not merely old:
- `utils/traces/parity/comparator.py:3-4`: *"The oracle fixtures under `utils/traces/parity/fixtures/` are
  recordings of the OLD NLU→PEX→RES pipeline."* RES no longer exists, so the oracle can never be re-run.
- `utils/evals/e2e_agent_evals.py:7-11` targets *"policy_spec.md § The 14 Target Flows"* with steps
  `7 simplify · 8 add · 10 inspect` — all three are flows the 48→16 audit **cut**. The suite and its
  golden `snapshots/` name flows that do not exist.

Why it matters: a graveyard that still imports and half-runs is worse than no graveyard — `harness.py` (used
by the LIVE traces + model tiers) reaches into `utils/traces/parity/capture_oracle.py` for one helper,
which drags the whole dead parity chain (and transitively `e2e_agent_evals.py`) into every import. Cutting
it removes a fragile dependency, not just clutter.

## Inventory & decisions (the cut-list)

### `utils/traces/` — the legacy Traces material (delete ~all of it)

| Path | Fate | Reason |
|---|---|---|
| `01_*.json/.md` … `10_*.json/.md` (20 files) | **DELETE** | hand-written trajectories on retired `detect_and_fill`; two name cut flows (`02_revise_simplify`, `03_publish_preview`) |
| `parity/capture_oracle.py`, `comparator.py`, `record_traces.py`, `run_parity.py`, `smoke_openings.py`, `trace_recorder.py` | **DELETE** | the 3-axis parity oracle, built on the deleted NLU→PEX→RES pipeline (comparator.py:3-4) |
| `parity/fixtures/{observability,vision,voice}.json` | **DELETE** | recordings of the old pipeline; can never be replayed |
| `parity/capture_oracle.py::_clean_leftovers` | **RELOCATE → `utils/harness.py`** | 8-line cleanup helper, the ONLY live dependency (`harness.py:22`) |
| `tolerance_rules.md` | **KEEP → relocate** to `utils/evals/datasets/` | the tolerance vocabulary is still normative (`round_1_evals.md` Traces phase); it is a dataset-adjacent reference, not code |

After this, `utils/traces/` has no code left. Whether the empty dir survives depends on the layout decision
below.

### `utils/evals/` — separate the live suite from the dead bulk

| Path | Fate | Reason |
|---|---|---|
| `run_evaluation_suite.py` | **MOVE → `utils/run_evaluation_suite.py`** | drives all three tiers; must not live inside one tier's folder |
| `e2e_agent_evals.py` (70 KB) | **DELETE → replace** | dead 14-step lifecycle (`simplify/add/inspect`), `policy_spec.md §14` dead spec, golden-snapshot coupling |
| `e2e_multiturn_evals.py` | **DELETE** | tests cut flows (`test_simplify_multiturn_*`); ambiguity coverage moves to the corpus-driven evals |
| `snapshots/` (28 goldens) | **DELETE** | state-projection goldens for the dead 14-step scenario; filenames name cut flows |
| `evaluation_guidelines.md` | **DELETE** | documents the NLU→PEX→RES pipeline; superseded by `_specs/utilities/evaluation_suite.md` |
| `diagnose_crashes.py` | **DELETE** | throwaway crash-hypothesis script with stale line refs (`pex.py:228`, `nlu.py:410-414`) |
| `e2e_progress_latest.jsonl` | **DELETE + gitignore** | run artifact written by `e2e_agent_evals.py` |
| `run_evals.py` | **KEEP** (the live Traces runner) | the real Traces tier; the `--ids`/8-scenario default lands here (round 2.10) |
| `scorers/completion.py`, `scorers/tools.py` | **KEEP** | live scoring, shared by traces (and the new evals) |
| `gates.py`, `baselines/traces.json` | **KEEP** | folded-baseline gate + current baseline |
| `datasets/**` (96 scenarios, feedback, guides) | **KEEP** | the live corpus; path is referenced by the `generating-evals` skill — do not move casually |
| `review/{server.py,index.html,app.js}` | **KEEP** | the wired seed-review app |

### `utils/tests/` — one straggler

| Path | Fate | Reason |
|---|---|---|
| `test_cases.json` | **DELETE** | dead 48-flow accuracy labels; **zero references** (grep confirmed); `model_tests.py` is data-driven off `datasets/scenarios/` |

### Replacing the deleted Evals runner

`e2e_agent_evals.py` is deleted, not edited — migrating 1670 lines of dead-flow lifecycle costs more than
rewriting. Its replacement is a lean **`utils/evals/run_agent_evals.py`** that runs the standard 8 scenarios
(round 2.10) end-to-end through `agent.take_turn` and scores the **7 Eval criteria** from
`_specs/utilities/evaluation_suite.md` (completion, correctness/actions, response, task/state, latency,
ambiguity, planning). It reuses what already exists: `harness._build_agent`/`_seed_post`, the
`completion`/`tools` scorers, and `utils/_snapshot.py` for state projection if the task/state criterion
wants golden comparison. **Building that runner is a P4 eval-build task, not part of this cleanup** — this
plan only DELETES the dead runner and stubs the entry point so the suite still resolves. Flag for the user:
confirm the delete-and-rewrite over a salvage of the old 3-tier scaffolding.

## Decision: folder layout for the three tiers

The one firm requirement (the user): `run_evaluation_suite.py` leaves `utils/evals/`. Beyond that, the tiers
do not map cleanly to folders today — the **Traces runner lives in `utils/evals/`**, and `datasets/` +
`scorers/` are **shared across tiers**. Two ways to resolve it.

### Option A — minimal churn (recommended)

- Move `run_evaluation_suite.py` → `utils/`.
- **Delete `utils/traces/` outright** (after relocating `_clean_leftovers` + `tolerance_rules.md`).
- Leave the Traces runner where `round_1_evals.md`'s target architecture already puts it —
  `utils/evals/run_evals.py`. `utils/evals/` stays the shared home for the corpus, scorers, gate, review
  app, and both live runners (traces + the new evals).

- **Pros:** smallest diff; no import churn; keeps the `datasets/` path the `generating-evals` skill and
  `data_aug_guide.md` already document; matches the layout `round_1_evals.md` already committed to.
- **Cons:** the folder name `evals/` still contains the Traces runner — tier≠folder. `utils/traces/`
  disappears, so there is no "traces folder" to reflect the tier.

### Option B — full three-folder symmetry

- `utils/{run_evaluation_suite.py}` on top; `utils/tests/` (Tests, done); repurpose the purged
  `utils/traces/` as the real Traces tier (move `run_evals.py` → `utils/traces/`, plus the `scorers/` and
  `gates.py`/`baselines/` it uses); `utils/evals/` becomes the Evals tier (new runner + `datasets/` +
  `review/`).
- Requires a shared corpus module (see below) because `datasets/` stays under `evals/` but is read by all
  three tiers.

- **Pros:** folder names map 1:1 to the three tiers; `utils/traces/` earns its name; matches the mental
  model behind the request.
- **Cons:** more churn — `scorers/completion.py` is shared by traces AND the new evals, so it can't sit
  purely under `traces/`; moving `run_evals.py` breaks `model_tests.py:27`'s import; ripples into any doc
  that cites `utils/evals/run_evals.py`. The corpus path either stays cross-tier (a wart) or `datasets/`
  also moves (rippling into the `generating-evals` skill).

### Recommendation

**Option A**, unless the user specifically wants the folder symmetry. A deletes the confusing thing
(`utils/traces/` is not the traces tier — it is a graveyard) and satisfies the one hard requirement, at a
fraction of the churn. Revisit B once the new evals runner exists and the shared surface is settled.

### Shared corpus constant (needed by both options, ties to round 2.10)

`model_tests.py:27` imports `SCENARIOS` from `run_evals`. Rather than couple the Tests tier to the Traces
runner, hoist the corpus path AND the standard 8 into one small module — `utils/evals/corpus.py`:
```python
from pathlib import Path
SCENARIOS = Path(__file__).resolve().parent / 'datasets' / 'scenarios'
DEFAULT_SCENARIOS = ('B01.C01', 'B01.C04', 'B02.C01', 'B02.C02',
                     'B03.C01', 'B04.C01', 'B05.C01', 'B06.C01')  # round 2.10's standard 8
```
`run_evals.py`, `model_tests.py`, and the new `run_agent_evals.py` all import from here. This is the same
`DEFAULT_SCENARIOS` round 2.10 introduces — define it once, in this module, and round 2.10's "Shared prerequisite"
points at it.

## Connected files (imports to update after deletion)

| File | Change |
|---|---|
| `utils/harness.py:3-7,22` | drop the parity import; inline `_clean_leftovers`; fix the docstring (it names the deleted recorder) |
| `utils/tests/model_tests.py:27` | import `SCENARIOS` (and `DEFAULT_SCENARIOS`) from `utils/evals/corpus.py`, not `run_evals` |
| `utils/evals/run_evals.py:39` | `SCENARIOS` now comes from `corpus.py` (round 2.10 already touches this file for the 8-default) |
| `utils/run_evaluation_suite.py` (moved) | `_HUGO_ROOT = Path(__file__).resolve().parent` → **`.parent`** now IS `utils`, so use `.parents[0]` for Hugo root (was `.parents[1]`); the `'utils/tests/...'` argv paths stay root-relative and unchanged (cwd is still Hugo root) |
| `utils/run_evaluation_suite.py:53-54` | the `--evals` argv points at the deleted `e2e_*_evals.py`; repoint to `utils/evals/run_agent_evals.py` (or, until that exists, drop `--evals` from the default and print "evals runner: TODO") |
| `.gitignore` | add `utils/evals/e2e_progress_latest.jsonl` (moot once its writer is deleted, but keeps stray runs out) |

Note: `capture_oracle.py:38` imports scenario defs from `e2e_agent_evals.py`; both are deleted, so that
coupling dies with them (delete `parity/` first, then `e2e_agent_evals.py`).

## New concepts introduced

**None.** This is deletion, one 8-line helper relocated verbatim, and one constant hoisted into a shared
module. No new component, field, attribute, or mechanism. (`utils/_snapshot.py` stays — it is live infra:
`pex_unit_tests.py`'s `TestSnapshotHarness` and the future evals runner both use it. `review/` stays — the
`generating-evals` skill depends on it.)

## How to verify

1. **No dangling imports.** After the deletes + the `harness.py` relocation:
   - `grep -rn "utils.traces\|traces.parity\|e2e_agent_evals\|e2e_multiturn\|diagnose_crashes\|test_cases.json" utils backend` returns nothing outside comments.
   - `python -c "import utils.harness"` succeeds (no parity import) and `utils.harness._clean_leftovers` exists.
2. **Deterministic suite still green (208):** `python utils/run_evaluation_suite.py --tests`.
   (`pex_unit_tests.py`'s snapshot-harness smoke tests still pass — `utils/_snapshot.py` was kept.)
3. **Suite entry works from its new home:** `python utils/run_evaluation_suite.py` (no flags) runs the free
   deterministic tests; `--traces` runs `run_evals.py` on the standard 8; `--model nlu` scores the same 8.
   No path errors from the moved file.
4. **The corpus constant is shared:** `python -c "from utils.evals.corpus import SCENARIOS, DEFAULT_SCENARIOS; print(len(DEFAULT_SCENARIOS))"` → 8; both `run_evals` and `model_tests` import it.
5. **Nothing live was deleted:** `run_evals.py`, `scorers/`, `gates.py`, `baselines/traces.json`,
   `datasets/`, and `review/` all remain; the review app still serves (`python utils/evals/review/server.py`).
6. **File count sanity (the cut-list landed):** `utils/traces/` is gone (or empty); `utils/evals/` no longer
   contains `e2e_agent_evals.py`, `e2e_multiturn_evals.py`, `snapshots/`, `evaluation_guidelines.md`,
   `diagnose_crashes.py`, or `run_evaluation_suite.py`.
7. **Evals tier resolves:** either `run_agent_evals.py` exists and `--evals` runs it on the 8 scenarios, or
   `--evals` cleanly reports "not built yet" — never a stack trace from a deleted path.
