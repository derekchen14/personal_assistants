# Spec Sheet — E1 · Fast eval mode (record/replay at the PromptEngineer seam)

Round: E1 · Source: the user's eval-speed doctrine (2026-07-02) + `_specs/_review/step_1_evals.md`
(Master Plan parallel eval track). Runs NEXT, ahead of 4.5. Status: **APPROVED by the user
2026-07-03** — every decision in §6 is recorded final (D1/D2 as recommended; D3 overruled to
checkpoint reuse; D4 overruled to a config key; D5 canonical shape approved; timing =
print-don't-gate; D6 = trim inside E1, sequenced). SWE planning builds from this revision.

> **ROUND OUTCOME (2026-07-03) — scope reduced mid-round by the user.** The record/replay seam was
> built, proven end-to-end on one scenario, and then REMOVED: byte-exact replay demanded pinning
> every environmental input (session ids, timestamps, uuids, DB state), which the user rejected as
> overkill for evals ("we do not need perfect replay"). Evals judge the 7 E2E criteria only; the
> authoritative spec is `_specs/utilities/evaluation_suite.md` (latency = total ≤10 min +
> TTFT ≤1 min — the per-turn 10 s target is retired). What E1 shipped: R9 (corpus-shape
> normalizer — the runner seeds all 96 cases), timing reports + `--ids` gate subset in the
> runner, `HUGO_EVAL_MODE` env var removed in favor of `schemas.config.EVAL_HARNESS`, the
> fill_slots prompt slot-order nondeterminism fix (keyed by `slot.slot_type`), an atomic
> metadata write, `_seed_post` hardening, and ONE D6 trim (high ensemble voter dropped —
> completion 0.31→0.36, gate 11.8→8.4 min, its truncated-JSON turn crashes eliminated).
> R1/R2/R9/R10 delivered; R3-R8 (replay, recordings, trace baseline) intentionally not.

**Doctrine (refined by the user, supersedes the first cut):** each TURN ≤ 10 s; each CONVERSATION
≤ 1 min; the **per-release gate is a SAMPLE of 8 scenarios in ≤ 10 min**. The full 96-sweep is
NOT the per-release gate — it is the dev-iteration loop and the CI/trace substrate. Any pipeline
part over 10 s gets terminated and sped up (e.g. by mocking the service).

**Round 4.2 status:** shipped — PR #1, commit `2f51b6b`, branch `round/4.2-closing-reminder`, on
the offline verdict; its eval leg is deferred to this round's acceptance demo (R10).

## 1 · Feature definition & user story

**Problem statement — measured 2026-07-02:**

| What | Today |
|---|---|
| One live turn through the orchestrator | 12.6 s (agent build 1.5 s) |
| One conversation (~7 turns) | ~60-90 s |
| 96-scenario sweep | ~2 h |
| `HUGO_EVAL_MODE` | mocks **nothing** — only prefixes artifact filenames (`platform_service.py:486`) |

**Interim 8-scenario run (2026-07-02, for round 4.2) — confirmed the doctrine, surfaced a
blocker:**
- **B01.C01 took 59 s for one 4-user-turn conversation.** 1/4 turns completed: turn 1 expected
  `find`, got `''` (empty artifact origin); turns 3-4 expected `compose`/`release` but got
  `outline` both times — the flow appears stuck. Consistent with the red-green `expected_fail`
  baseline, but recorded here as behavioral signal for the milestone.
- **The runner CRASHED on B01.C08.** `run_evals.py:46` does `post.get('sections')`, but that
  case's `available_data.posts` holds bare title **strings**, not dicts — the runner predates
  the regenerated corpus in the working tree. Full-corpus audit of every `posts` entry
  (2026-07-02): **27 cases** carry bare title strings (crash at `.get`); **16 cases** carry
  `{post_id, title, status}` with no `sections` (silently skipped — never seeded); **4 cases**
  carry `{id, title, status, sections:[names]}` (wrong key — runner wants `post_id` — and
  section *names* without prose, so `_seed_post`'s `sections.values()` zip has no content).
  Several cases also carry a `notes` key the runner ignores. Net: **zero scenarios seed
  correctly today**, and the eval leg of round 4.2 was **deferred pending E1**.

**Where the 12.6 s goes (from code structure — every stage routes through `PromptEngineer`,
`ACTIVE_FAMILY='gemini'`).** A turn runs these model stages **sequentially**:

| Stage | Calls · tier | Notes |
|---|---|---|
| NLU `classify_intent` (`nlu.py:315`) | 1 · med (Flash) | schema-constrained |
| NLU `detect_flow` ensemble (`nlu.py:328-346`) | 3 in **parallel** · low/med/high | already parallel (`ThreadPoolExecutor`); latency floor = the **high** voter (Gemini 3.1 Pro preview) |
| NLU `fill_slots` (`nlu.py:391`) | 1 · med | max_tokens=2048; occasional `repair_slot` |
| PEX `tool_call` loop (`policies/base.py`) | 1-4+ rounds · med | cap 8 (16 for audit/refine/rework/compose); + local tool dispatch (ms) |
| PEX `quality_check` (`pex.py:260`) | 1 · low | max_tokens=128 |

The ensemble is already parallel, so every trim that would push a live turn under 10 s is
**behavioral**: drop/downgrade the high voter, merge intent+flow detection, cap PEX rounds lower,
or skip `quality_check`. Per D6 (decided), E1 **does** trim — but sequenced: the seam and timing
reports land first, a pre-trim baseline is recorded, then one trim at a time with the 8-scenario
gate re-run after each so regressions are attributable. Timing itself is printed, not gated (R2).
What needs **no** behavior change: **the 8-scenario release gate fits its 10-min budget live
today** — 8 × 60-90 s ≈ 8-12 min serial (borderline), ~2-3 min with 4-way scenario-level
parallelism (comfortable). Record/replay is therefore NOT a prerequisite of the release gate.

Record/replay remains the right tool for everything else: the full 96-sweep (dev iteration), the
trace gate, and CI-without-keys. The spec already prescribes it for traces — record-once /
replay-many, cached voter outputs fed back instead of calling the model, temp-0
(`evaluation.md:69-72`; `step_1_evals.md:58`); this round extends that pattern to every model
call at the PromptEngineer provider boundary, so the full loop runs with zero live calls.

**User story (the iteration loop).** As a developer on Hugo, I change a prompt or a policy, run
the 96-scenario sweep in replay, and read the completion report **under a minute later** — then
fix, rerun, and repeat dozens of times a day. Before a release I run the live 8-scenario gate and
get a verdict inside 10 minutes. Today one sweep costs ~2 h and the gate crashes on seeding, so
neither exists; fast testing, fixing, iterating, and more automation is the meta plan this round
unblocks.

**Budget after replay.** With model calls served from disk, the remaining per-convo cost is agent
build (1.5 s) + local tool dispatch (file-backed services, ms). Serial agent builds alone are
96 × 1.5 s = 144 s — over budget — so the runner must also parallelize across scenarios
(`ThreadPoolExecutor` is already imported in `run_evals.py`; ~12 workers puts the sweep well
under 60 s).

## 2 · Requirements (each traced — nothing invented)

| # | Requirement | Trace |
|---|---|---|
| R1 | **Per-release gate:** a LIVE sample of 8 scenarios completes in ≤ 10 min (scenario-level parallelism allowed; no record/replay required). The 96-sweep is not the release gate. | refined doctrine 2026-07-02 |
| R2 | **Timing is printed, not gated** (the user 2026-07-03): the runner reports per-turn, per-conversation, and total wall time in every run's output (~10 lines of measurement code); QA reads the report against the doctrine targets (≤ 10 s turn / ≤ 60 s convo / ≤ 10 min 8-scenario gate). NO new entries in `baselines/evals.json`, no timing gate records, no `expected_fail`. | refined doctrine; the user's decision 2026-07-03 |
| R3 | Replay mode makes **zero live model calls**; recorded responses fed back deterministically (record-once / replay-many, temp-0). Scope: the full-96 dev sweep, the trace gate, and CI-without-keys — not the release gate. | `evaluation.md:69-72`; `step_1_evals.md:58`; refined doctrine |
| R4 | One mechanism at the PromptEngineer boundary — generalizes the cached-vote replay design rather than duplicating it; the traces-level runner consumes the same seam. | `step_1_evals.md:58,209-210` (complement, don't duplicate) |
| R5 | Tool dispatch stays **live** during replay (local services): seeded posts, end-state, and grounding still change for real, so the completion scorer and the 3-axis parity checks keep working. | `evaluation.md` §Scenario/parity axes; `run_evals.py:44-64` |
| R6 | Side effect: a runnable trace gate — `baselines/` today holds only `evals.json`; the replay runner writes `traces` metrics + baseline so the trace level stops being aspirational. | QA finding; `step_1_evals.md:246` (one entrypoint, four levels) |
| R7 | Live runs remain the ground-truth source: recordings are captured from live runs and re-captured on demand; gold is recorded, never synthesized. | `step_1_evals.md:253-264` |
| R8 | Every run (live gate or replay sweep) prints per-turn, per-conversation, and total wall time in its output; QA reads them against the R2 targets. | doctrine ("the new mode must itself be timed") |
| R9 | Reconcile the runner with the current corpus schema per D5 (decided): declare the canonical shape in `datasets/_gen_spec.md` and add one thin temporary `_normalize_posts()` in `run_evals.py` upgrading the three legacy shapes on read; no crash on any of the 96 cases; no corpus rewrite this round. | coordinator addendum 2026-07-02; corpus audit above; `run_evals.py:44-48`; D5 |
| R10 | Acceptance demo: re-gate round 4.2 (shipped as PR #1, `2f51b6b`, on the offline verdict) by running its 8 selected scenarios (B01.C01/C08/C11/C12/C14, B02.C15, B03.C03/C07) as the first live release gate — 4.2's deferred eval leg completes as E1's verification. | coordinator addendum 2026-07-02; `round_4.2_spec.md` §4a |

## 3 · Pseudo-code — the record/replay seam

All live traffic exits through four single-shot provider methods (`_call_claude:288`,
`_call_gemini:322`, `_call_gpt:350`, `_call_together:373`) and the tool loops that invoke either
those or the SDK clients per round (`_call_claude_with_tools:227`, `_call_gemini_with_tools:453`,
`_openai_tool_loop:525`). The seam wraps the **single-shot response fetch** — one recorded blob
per model round-trip. Tool loops therefore replay round-by-round while `tool_dispatcher` executes
for real (R5).

Storage is the **existing checkpoint system** (D3, decided): `ContextCoordinator.save_checkpoint
(label, data)` / `get_checkpoint(label)` at `context_coordinator.py:116-132`. The label IS the
cache key; the recorded blob rides in `data`. Mode comes from config (D4, decided) with the
eval-harness safeguard.

```python
# components/prompt_engineer.py — the seam (sketch; placement per D2)
class CacheMiss(Exception): ...

def __init__(self, config):
    ...                                            # existing body unchanged
    self._eval_mode = self._models.get('eval_mode', 'off')      # D4: models.eval_mode
    if self._eval_mode != 'off' and not schemas.config.EVAL_HARNESS:
        raise RuntimeError('models.eval_mode requires the eval harness (EVAL_HARNESS is False)')
    self.recorder = None            # ContextCoordinator, attached by Agent/harness wiring

def _cache_key(family, model_id, system, messages, tool_defs, schema_dict) -> str:
    blob = json.dumps([family, model_id, system, messages, tool_defs, schema_dict],
                      sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()

def _cached_response(self, family, key_parts, live_fn):
    """mode 'off' → live. 'replay' → checkpoint blob or CacheMiss. 'record' → live + save."""
    if self._eval_mode == 'off':
        return live_fn()
    label = _cache_key(*key_parts)
    found = self.recorder.get_checkpoint(label)
    if found:
        return _rehydrate(family, found['data'])
    if self._eval_mode == 'replay':
        raise CacheMiss(f'no recording for this call — re-record ({label[:12]})')
    response = live_fn()                           # 'record': call live, then checkpoint
    self.recorder.save_checkpoint(label, _serialize(family, response))
    return response
```

- **Checkpoint persistence is the harness's job (verified 2026-07-03):** `save_checkpoint`
  appends `{label, turn_count, history_snapshot, data}` to the in-memory `self._checkpoints`
  list — the component writes **nothing to disk**, and `reset()` clears the list. So the harness
  persists across runs: after a record run it dumps the recording checkpoints (label + data
  only — `history_snapshot` duplicates the full conversation per call and is dropped on save)
  to `utils/traces/recordings.jsonl` (existing traces dir — recordings ride trace observability;
  no new folders); at replay start it re-seeds them via `save_checkpoint(label, data)` before
  the first turn.
- **Wiring:** `PromptEngineer` has no coordinator reference today; `Agent` builds both. One
  attach line at build (`engineer.recorder = coordinator`) — the SWE plans pick the exact spot.
- `_serialize`/`_rehydrate`: provider responses are SDK objects; persist the fields the loops
  actually read (Claude: `content[].type/text/tool_use`, `stop_reason`; OpenAI-style: message +
  `tool_calls`; Gemini: candidates/parts) and rehydrate as a minimal `SimpleNamespace` tree. No
  full SDK-object reconstruction.
- **Staleness is structural, not scheduled:** the key hashes the full request. Change a prompt,
  a slot rendering, or a tool def and only the affected calls miss — everything else replays.
  A miss in replay mode fails loudly with the re-record instruction (no silent live fallback in
  CI; D1, decided).
- Runner change (`run_evals.py`): map `_run_case` over a `ThreadPoolExecutor(max_workers≈12)`,
  time each turn and case, and print wall times in the run output (R2/R8 — print, don't gate).
  Recordings make turns deterministic, so the existing 240 s turn timeout stops mattering in
  replay.
- Non-determinism caveat: replay only matches if the assembled prompt is reproducible. Volatile
  tokens (dates, session ids) live in the user message by design — recordings must be captured
  with the same seeded posts and pinned/frozen date, or those keys churn. The recorder already
  runs seeded (`harness._seed_post`); date pinning lands with the recorder wrapper.

Scope guard: no new components — the seam is a private method + one config key on the existing
`PromptEngineer`, storage is the existing checkpoint system, and the runner edits stay inside
`run_evals.py`.

## 4 · Test plan — coverage doctrine: Evals lead → Traces → Tests → greps

### 4a · E2E Agent Evaluations (headline gate)

The deliverable IS an eval mode, so the eval of the round is running both modes, timed. All runs
cwd = `assistants/Hugo`; mode selection per D4.

**Ordering constraint:** R9 (schema reconciliation) lands first — neither gate can run while the
runner crashes on 27 of 96 cases and seeds none of them.

**Run 1 — the live release gate (R1, R10 acceptance demo):**

```
python utils/evals/run_evals.py --level evals --metric completion        # live, 8-scenario sample
```

on round 4.2's 8 selected scenarios. Pass = (a) no crash on B01.C08 (schema fix proven),
(b) QA reads the printed wall times against the doctrine targets — 8-scenario gate ≤ 10 min,
convos ≤ 60 s, turns ≤ 10 s (turns start at ~12.6 s pre-trim; noted, not gated — R2),
(c) QA applies 4.2's pass criteria from the per-turn log (turns log `ok` per the red-green
model; no JSON-wrapped or instruction-restating replies). This completes 4.2's deferred eval
leg and is the template for every future release gate. Re-run after each D6 trim so any
completion regression is attributable to that one trim.

**Run 2 — the replay dev sweep (R3):**

```
python utils/evals/run_evals.py --level evals --metric completion        # replay mode, all 96
```

Pass = (a) sweep completes with **zero live calls** (assert via a no-network run: unset API
keys — recordings must carry the whole suite), (b) total wall time well under the ~2 min the
parallel budget predicts (report `sweep_seconds`; informational, not doctrine-gated),
(c) `completion_rate` in replay equals the recorded live baseline exactly (same responses in →
same verdicts out; any diff means the seam leaks nondeterminism).

**Round process note (applies to E1 and every later round):** DoE adjudication of the merged
diff must include a visible ponytail over-engineering review — what could be deleted or
simplified, stated in the Verdict, not silently skipped.

### 4b · Observability Traces

- The recording layer captures per-round model outputs — a superset of the cached voter outputs
  the traces design needs (`step_1_evals.md:58`). The trace-replay runner consumes the same
  recordings; this round writes the first `baselines/traces.json` (R6), turning the trace gate
  from missing to runnable.
- Milestone flag (carried from 4.2): approved gold trajectories are still thin; this round gives
  them a fast recorder, it does not author them.

### 4c · Model Unit Tests (only genuinely-failable checks)

Baseline first (cwd = `assistants/Hugo`): 324 passed / 0 skipped / 0 failed via
`python -m pytest utils/tests/test_artifacts.py utils/tests/unit_tests.py utils/tests/test_nlu_module.py -q`

| ID | Test | Expected |
|---|---|---|
| T1 | `test_cache_key_stable` — same request parts → same key; any single part changed → different key. | passes |
| T2 | `test_record_then_replay_roundtrip` — record a stubbed response, replay it, rehydrated object exposes the fields the tool loop reads. | passes |
| T3 | `test_replay_miss_raises` — replay mode + absent recording → `CacheMiss` (no silent live call). | passes |
| T4 | `test_off_mode_untouched` — mode `off` never reads or writes checkpoints; and `models.eval_mode != 'off'` with `schemas.config.EVAL_HARNESS` False raises at `__init__` (the D4 safeguard). | passes |
| S1 | Full offline gate rerun. | 324 + T1-T4 passed / 0 skipped / 0 failed |

**Piggyback candidate (from 4.2's ponytail retro-review):** if this round touches
`test_artifacts.py`, delete the `test_json_reminder_deleted` tombstone test — it guards against
a constant resurrecting, which grep G1-style checks cover; flagged optional by the retro, to be
picked up by the next round editing that file.

### 4d · Greps (QA manual)

| Check | Expected |
|---|---|
| `grep -rn HUGO_EVAL_MODE assistants/Hugo` | ZERO hits — the user removed the env var mid-round (2026-07-03); the marker is now `schemas.config.EVAL_HARNESS`, a module flag set only by harness/test entrypoints |
| Replay-mode run with API keys unset | zero auth errors — proves no live path executes |

## 5 · Simplification opportunities

- **No new mocking framework, no vcrpy.** Three SDKs (anthropic, genai, openai) at the HTTP layer
  is brittle; one checkpoint-backed cache at our own boundary is ~40 lines and provider-agnostic.
- **No new storage concept.** Recordings reuse `save_checkpoint`/`get_checkpoint` and the
  existing `utils/traces/` home — zero new folders, zero new components (D3, decided).
- **No mock services.** Tool dispatch is already local and fast; mocking it would break the
  end-state axes for zero speed gain (R5).
- **No scheduler/TTL for staleness.** Content-addressed keys self-invalidate; a re-record is just
  running the same sweep in record mode. Nothing to cron inside this round (live cadence is D3).
- **No streaming support in the seam.** `stream()` is a chat-UI path, not an eval path — leave it
  live-only.
- **Agent-build cost (1.5 s) left as-is.** Parallelism absorbs it; shaving the build is a
  separate, unrequested optimization.

## 6 · Decisions — recorded final (the user, 2026-07-03)

All six are settled; alternatives are kept below for the record. D1/D2 landed as recommended;
D3/D4 were overruled; D5's canonical shape was approved verbatim; D6 chose trimming inside E1,
sequenced.

### D1 — Replay mechanism

- **A (strict record/replay, content-addressed):** replay serves recordings; a miss raises
  `CacheMiss` and the run fails with a re-record instruction.
  - Pro: deterministic and honest — CI can never silently spend 2 h or dollars; a miss is a
    signal that a prompt changed and ground truth needs refreshing.
  - Con: the first sweep after any prompt change fails until someone re-records (one live run of
    the affected scenarios).
- **B (hand-written mock service):** a canned-response fake per task/flow (e.g. "outline call →
  fixed outline JSON") behind the same seam.
  - Pro: no recording step, works from day zero, human-readable fixtures.
  - Con: hand-maintained parallel model of 18 flows × tools × rounds — drifts from real model
    behavior immediately; completion numbers stop meaning anything. Rejected as primary.
- **C (hybrid: replay, fall through to live + auto-record on miss):**
  - Pro: never blocks — a prompt change transparently re-records just the changed calls.
  - Con: a broad change silently turns "fast sweep" into a slow, costly live run; timing gate
    (R8) only catches it after the fact. Also needs keys present in CI.

**DECIDED: A, as recommended.** Strict record/replay; a miss raises `CacheMiss`; `record` mode
is the explicit re-record path. No silent live fallback anywhere.

### D2 — Where the seam sits

- **A (provider single-shot methods + per-round in the tool loops):** wrap the response fetch in
  `_call_claude/_call_gemini/_call_gpt/_call_together` and the per-round client calls in the
  three tool loops. Tools dispatch live.
  - Pro: covers every call (NLU voters, one-shots, skill calls, each loop round) with real side
    effects preserved — end-state, grounding, and the completion scorer all keep working.
  - Con: ~7 wrap points (each loop reads responses slightly differently), and the serializer must
    handle three response shapes.
- **B (public boundary — cache final `(text, tool_log)` of `__call__`/`skill_call`/`tool_call`):**
  - Pro: 3 wrap points, no per-round serialization, simplest possible diff.
  - Con: skips live tool dispatch — no posts created, no end-state to score; `is_completed` still
    reads `artifact.origin` but the parity axes and seeded-post flows go dark. Kills R5.
- **C (HTTP/SDK layer, VCR-style):**
  - Pro: zero application code touched.
  - Con: new dependency; three different SDKs with streaming and retry internals; cassette keys
    are fragile against header/SDK-version churn. Rejected.

**DECIDED: A, as recommended.** Provider single-shot methods + per-round in the tool loops;
tools dispatch live so replay runs produce real end-states.

### D3 — Recording storage: DECIDED — the user OVERRULED committed blob files

**Decision: recordings reuse the EXISTING checkpoint system** —
`ContextCoordinator.save_checkpoint(label, data)` / `get_checkpoint(label)`
(`context_coordinator.py:116-132`). Recordings are effectively traces; no new folders, no new
concepts — they ride the existing trace observability. (The PM's option A — a new committed
`recordings/` folder of hash-named files — and options B/C are superseded; the content-addressed
**key** survives as the checkpoint **label**.)

Storage design as decided (verified against the component 2026-07-03):

- **Label scheme = the cache key.** The seam calls `save_checkpoint(label=<sha256 of the full
  request>, data=<serialized response>)` at record time and `get_checkpoint(label)` at replay.
  `get_checkpoint` scans newest-first for the label — a re-record of the same key simply
  shadows the older entry within a run.
- **What the component actually does:** `save_checkpoint` appends `{label, turn_count,
  history_snapshot, data}` to the in-memory `self._checkpoints` list; **nothing is written to
  disk**, and `reset()` clears the list. Cross-run persistence is therefore the harness's job:
  - end of a record run → dump recording checkpoints to `utils/traces/recordings.jsonl`
    (one line per checkpoint, **label + data only** — the `history_snapshot` the component
    attaches duplicates the whole conversation per model call and is dropped at dump time);
  - start of a replay run → read the file and re-seed via `save_checkpoint(label, data)`
    before the first turn.
- **Fresh truth:** the live 8-scenario release gate every release is the drift canary for the
  sampled slice; a scheduled full live record pass refreshes the rest (nightly cadence per
  `step_1_evals.md`).

### D4 — Mode selection: DECIDED — config key, NOT a new env var (the user overruled option A)

**Decision: `models.eval_mode: off | record | replay`, default `off`**, read once in
`PromptEngineer.__init__` from the config dict it already receives — `self._models =
config.get('models', {})` exists at `prompt_engineer.py:84`, so the read is one line:
`self._eval_mode = self._models.get('eval_mode', 'off')`. The harness sets the key through the
`load_config(overrides=...)` path it already uses (`harness.py:32`). No new env var.

**Mandatory safeguard — replay can never boot in a real session:** at `__init__`, any mode
other than `'off'` demands the eval-harness marker. Mid-round (2026-07-03) the user also removed
the `HUGO_EVAL_MODE` env var entirely ("global env is generally to be avoided"); the marker is
now `schemas.config.EVAL_HARNESS`, a module-level flag that only the harness/test entrypoints
set (`utils/harness.py`, `utils/conftest.py`, the parity runners) and that also gates the
pinned service timestamps and the `_eval_` artifact filename prefix:

```python
if self._eval_mode != 'off' and not schemas.config.EVAL_HARNESS:
    raise RuntimeError('models.eval_mode requires the eval harness (EVAL_HARNESS is False)')
```

A real session that somehow inherits `eval_mode: replay` in config crashes at agent build —
loud failure per repo doctrine, not a silently-replaying production agent. Covered by T4.

### D5 — Schema reconciliation: fix the runner or normalize the corpus (R9)

The corpus ships three `posts` shapes (audit in §1); the runner understands none of them.

- **A (fix the runner only):** `_run_case` seeding accepts all three shapes — a string becomes
  `{title}` with a generated id and stub sections; `{id,...}` maps to `post_id`; missing prose
  gets a short generated paragraph per named section.
  - Pro: 96 corpus files stay untouched (they are reviewed ground truth); one function changes.
  - Con: the runner grows a shape-tolerant adapter — exactly the many-shapes-one-signature
    pattern the repo style forbids in backend code; acceptable in a harness, but it normalizes
    the corpus's inconsistency instead of fixing it.
- **B (normalize the corpus to one canonical shape):** one migration pass rewrites all 96
  `available_data` blocks to the runner's `{post_id, title, status, sections:{sec_id: prose}}`;
  the generator spec (`datasets/_gen_spec.md`) is updated so future batches emit it.
  - Pro: one shape forever; the runner keeps its clean contract; the generator stops producing
    drift.
  - Con: touches 47 reviewed corpus files + the generator; prose must be synthesized for
    sections that only have names — a bigger, riskier diff mid-round.
- **C (canonical shape + thin normalizer):** define the canonical shape in the gen spec now;
  the runner carries a small `_normalize_posts()` that upgrades legacy shapes on read, marked
  as temporary until the corpus is regenerated.
  - Pro: unblocks recording immediately, converges on one shape without rewriting 96 files
    mid-round.
  - Con: two artifacts to keep honest (normalizer + spec) until the regeneration actually
    happens — "temporary" adapters have a way of becoming permanent.

**DECIDED: C, with the canonical shape approved verbatim:**

```json
{"post_id": str, "title": str, "status": str, "sections": {"<name>": "<prose>", ...}}
```

— the exact `_seed_post` contract; the `notes` key stays separate. R9 therefore = declare this
shape in `datasets/_gen_spec.md` + one thin temporary `_normalize_posts()` in `run_evals.py`
upgrading the three legacy shapes on read (bare string / dict-without-sections /
sections-as-name-list). **No corpus rewrite this round.**

### D6 — Live turns under 10 s: DECIDED — trim inside E1, sequenced

The latency anatomy (§1) shows the remaining trims are all behavioral. The user chose to do them
in this round, in a strict sequence so every regression is attributable:

1. **Seam + timing reports land first** (the harness work: R9, the seam, the printed wall
   times).
2. **Record the pre-trim baseline** — the live 8-scenario gate's completion results and wall
   times at 12.6 s/turn.
3. **One behavioral trim at a time**, re-running the 8-scenario gate after each. Candidates,
   in the order they'd be attempted: downgrade/drop the **high ensemble voter**; **merge
   intent+flow detection** into one call; **fold `quality_check`** into the loop's last round.
   A trim that regresses completion is reverted before the next is tried.
4. **Re-capture recordings after the final accepted trim** — trims change prompts/call shapes,
   so recordings captured pre-trim are stale by construction; the post-trim record run is the
   one that ships.
