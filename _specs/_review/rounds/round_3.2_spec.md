# Round 3.2 — Session Scratchpad contract + synchronous NLU review

Status: **built 2026-07-08** (decisions reviewed with Derek via AskUserQuestion; see Decisions).
Implements §3.3 of `round_3_nlu.md`, with the already-landed World-owned `SessionScratchpad` as
the starting point. Scope is the scratchpad entry contract + NLU review only; intent routing
(§3.1), ambiguity binding (§3.2 of round_3_nlu), and flag cleanup (§3.4) are separate sub-rounds.

---

## The change in one paragraph

Hugo already has a shared `SessionScratchpad` on the World, but the write contract was loose:
some entries omitted the required minimal schema, nothing ever reviewed the pad, and — discovered
during the build — the pad was never bound to its session file, so live runs silently used an
in-memory dict. This round makes the contract real: every entry carries `origin` (one field
replacing the old `key`/`writer`/`flow` trio), `version:int`, `turn_number`, and `used_count`,
stamped explicitly by each code writer (the one LLM-authored path — the `append_to_scratchpad`
tool — is normalized in code, since tool arguments are unpredictable input); storage is one mode,
the append-only `scratchpad.jsonl` bound at `World.open_session`, so the pad is automatically
shared across all agents and sub-agents; and NLU runs a synchronous, conservative review pass at
its own turn point (end of `understand`), repairing non-conformant entries through the NLU-only
`SessionScratchpad.update`. Writers do NOT route through NLU — the scratchpad is a World component
every module reaches directly. The continuous background review loop remains designed-not-built.

## Current state

Verified from the current code:

1. **Physical location is already correct.** `World` exposes `world.scratchpad` from PEX's
   `SessionScratchpad` instance (`backend/components/world.py`). NLU can reach it as
   `self.world.scratchpad`.
2. **The component is append-only in file mode.** `SessionScratchpad.write(...)` stamps `writer`
   in code and appends JSONL when a session path is bound (`backend/components/session_scratchpad.py`).
3. **PEX bypasses NLU on writes.** `_dispatch_append_scratchpad`, `_dispatch_save_findings_tool`,
   `_dispatch_recover_ambiguity`, and policy completion writes call `session_scratchpad.write(...)`
   directly (`backend/modules/pex.py`).
4. **Entries are inconsistent with the spec.** `save_findings` includes the required fields, but
   `write_completion` writes only `{flow, summary, metadata}`, and recovery writes only
   `{key, found|missing}`. The spec requires `version`, `turn_number`, and `used_count` on every
   entry.
5. **No review hook exists.** Appending does not trigger NLU, and there is no `update_scratchpad`
   path reserved for NLU review.

## Target behavior

### 1. Entry schema is stamped by each writer

Every scratchpad entry contains:

- `origin`: what the entry is from / about — a flow name, `'orchestrator'`, or a stable topic
  (`'recovery'`). Stamped in code by `append`; also the lookup handle. Replaces the old `key`
  (too generic), `writer` (redundant), and completion-record `flow` (redundant) fields (Derek).
- `version`: integer schema version for that payload (an `int`, not the old string `'1'`).
- `turn_number`: current conversation turn id (`context.turn_id`).
- `used_count`: integer counter, initially `0`.

Each CODE writer stamps the fields itself — nothing is added behind its back (round_3_nlu §3.3.1;
a code writer that forgets a field is a bug that should surface, not get silently patched). The
one exception is the `append_to_scratchpad` TOOL, whose `entry` dict is LLM-authored: PEX's
dispatch handler forces `turn_number`/`used_count`, defaults `version`, and rejects an entry
without an `origin` with a corrective tool error.

Writers brought under the contract: `append_completion` (record is now
`{origin, version, turn_number, used_count, summary, metadata}`), NLU + PEX ambiguity-recovery
records, the propose policy's candidates entry, and `save_findings` / the find policy
(version string → int).

### 2. Writers hit the component directly; NLU owns review only

PEX, the policies, and NLU all keep writing the shared `SessionScratchpad` directly (it is a World
component, not an NLU internal). There are NO NLU-facing append/read wrappers — the earlier draft's
`NLU.append_to_scratchpad` / `read_from_scratchpad` were dropped (Derek). NLU's ownership is the
review pass:

```python
def review_scratchpad(self) -> dict: ...   # nlu.py — called at the end of understand()
```

Mutating existing entries is NLU-only, via `SessionScratchpad.amend_entry(origin, turn_number,
entry)` and `prune_entry(origin, turn_number)` — origin + turn_number is the pad's unique ID, and
both rewrite the file in place (raising when no entry carries the ID). Neither is in any tool
catalog.

### 3. Review is synchronous for now

The full continuous event-triggered loop stays deferred. Review runs once per turn at NLU's own
turn point — the end of `understand`, which also covers the PREVIOUS turn's PEX/policy appends —
and is deliberately conservative:

- Repair entries missing the contract fields losslessly via `update` (newest entry per origin wins).
- Leave semantic review (contradictions, pruning, used_count maintenance) as designed-not-built.
- Return a small diagnostic result: `{'reviewed': True, 'size': ..., 'repaired': ...}`.

This is enough to prove the entry contract and give future NLU review a single hook without adding a
background worker.

### 4. Reads stay read-only

`SessionScratchpad.read` and PEX's `read_scratchpad` tool must not increment `used_count` in this
round. The spec says NLU maintains `used_count` during review, but automatic read counting is a
future behavior. For now, entries start at `0` and stay stable unless an explicit NLU review update
is later added.

## Out of scope

- LLM-based contradiction review.
- Scratchpad auto-promotion to MEM.
- Background async loops or file watchers.
- Rewriting historical `scratchpad.jsonl` entries.
- Using the scratchpad to store user intent, flow predictions, or policy trajectories. Those stay in
  Dialogue State / Context Coordinator.

## Implementation (as built)

### `backend/components/session_scratchpad.py`

- One storage mode: append-only JSONL. The in-memory dict mode is deleted (Derek: the pad is
  always on disk for automatic sharing across agents and sub-agents); the unused `config` param
  and the in-memory 64-entry cap went with it (eviction is designed-not-built).
- `attach(scratchpad_path)` — binds the pad to `<session dir>/scratchpad.jsonl`; called by
  `World.open_session` (which previously never bound the pad — live runs silently ran in-memory).
  The session dir is created lazily on first write, keeping `open_session` side-effect free.
- The method surface is append-family for producers and ID-addressed mutation for NLU (Derek:
  there is no `write()`): `append_entry(origin, entry)` for PEX, the policies, and every
  sub-agent; `amend_entry` / `prune_entry` for NLU only. All take `origin` first.
- `append_entry(origin, entry)` — stamps `origin` (the merged key/writer field); no default
  origin, every caller names its own.
- No `append_completion` (Derek): `complete_flow` and `activate_flow`'s fallback build the
  completion record `{version, turn_number, used_count, summary, metadata}` themselves and call
  `append_entry(flow.name(), record)` like any other producer.
- `amend_entry(origin, turn_number, entry)` — NLU-only (review pass): origin + turn_number is
  the pad's unique ID; the file is rewritten with the amended entry on the matched line.
- `prune_entry(origin, turn_number)` — NLU-only: removes the identified entry (stale note,
  merged duplicate). Both mutators raise `KeyError` when no entry carries the ID.

### `backend/modules/nlu.py`

- `review_scratchpad()` — the conservative synchronous pass; called at the end of `understand`.
- `attempt_recovery` stamps the contract fields on its recovery record.

### `backend/modules/pex.py`

- `_dispatch_append_scratchpad` — rejects an entry without an `origin` (`invalid_input`
  corrective error); forces `turn_number`/`used_count` and defaults `version` on the LLM-authored
  entry. The `read_scratchpad` / `append_to_scratchpad` tool docs and the orchestrator prompt's
  completion-record line now speak `origin`.
- `_dispatch_recover_ambiguity` — recovery record stamps the contract fields.
- `_dispatch_save_findings_tool` — `version` is now the int `1`.
- `activate_flow` fallback completion passes `turn_number=self.world.context.turn_id`.

### `backend/modules/policies/`

- `BasePolicy.complete_flow(flow, state, context, summary, metadata=None)` — gained `context`
  (mirrors the policy-method parameter order) so completion records stamp
  `turn_number=context.turn_id`; all 21 call sites updated (`_rework_delete` also gained context).
- `revise.py` propose write stamps the fields; the used_count bump now indexes
  `entry['used_count']` directly (contract-guaranteed).
- `research.py` find write: version string → int.

## Decisions (reviewed with Derek, 2026-07-08)

### D0 — How do writers reach the scratchpad?

**Decided: directly.** PEX already holds `self.session_scratchpad`; the scratchpad is a World
component, not an NLU internal. No `world.nlu` handle (violates the round 0.3 components-only
rule), no `pex.nlu` handle, and no NLU append/read wrapper methods at all. NLU keeps only the
review pass, run at its own turn point.

### D1 — Where does entry normalization live?

**Decided: code writers stamp explicitly; only the LLM path is guarded.** Component-level
`setdefault` normalization was rejected — it would silently paper over our own writers' bugs
(the ghost-fallback pattern CLAUDE.md bans). The `append_to_scratchpad` tool's entry is
LLM-authored, so PEX's dispatch handler normalizes it in code — the one legitimate guardrail.

### D2 — Does an update path exist, and who sees it?

**Decided: NLU-private update now.** `SessionScratchpad.update(origin, entry)` exists with an
NLU-only docstring and is used by the review repair; it is in no tool catalog. PEX and sub-agents
remain append-only.

### D3 — Should read increment `used_count` now?

**Decided: no.** Reads stay pure; entries start at `0`. (The revise policy's explicit
skill-consumption bump — a deliberate write-back, not read counting — predates this round and
stays.) Real counting arrives when NLU review becomes stateful and S-2 auto-promotion consumes
the signal.

### D4 — How does `complete_flow` get the turn number?

**Decided: add the `context` param.** `complete_flow(flow, state, context, summary, metadata)`
mirrors the policy-method order and keeps completion records on the same clock
(`context.turn_id`) as every other entry. `components['context']` (two access paths to one
object) and `state.turn_count` (a different clock) were rejected.

### D5 — One identity field: `origin`

**Decided (Derek): merge `key`, `writer`, and the completion-record `flow` into a single
`origin` field.** `key` was too generic; `flow` carries the most meaning but not every writer is
a flow policy; a separate `writer` stamp is redundant once the identity field is code-stamped.
`origin` is stamped by `append(entry, origin=...)` and doubles as the lookup handle
(`read(origin=...)`).

### D6 — Storage is always the session file

**Decided (Derek): no in-memory mode.** The pad is always the append-only
`<session dir>/scratchpad.jsonl`, bound at `World.open_session` — disk is what makes the pad
automatically shared across all agents and sub-agents. The build also fixed the latent bug that
`open_session` never bound the pad, so live runs had silently used the in-memory dict.

## Tests (shipped)

Deterministic tests in `utils/evaluation_suite/_tests/`:

1. `test_completion_record_shape` / `test_completion_record_default_metadata` (nlu) —
   `append_completion` emits the schema-conformant record under the flow's origin.
2. `test_update_amends_newest_under_origin` (nlu) — NLU-only `update` appends the amendment so
   the newest entry under the origin wins.
3. `TestScratchpadReview` (nlu) — `review_scratchpad` repairs a non-conformant entry losslessly
   and leaves a conforming pad alone.
4. `test_read_and_append_scratchpad_tools` (pex) — the tool rejects an originless entry and
   stamps the contract fields on the LLM-authored one.
5. `TestSessionScratchpad` origin-stamping + filter rows; `TestPolicyCompletion` /
   `TestDispatchFlow` completion asserts updated to the new record shape.

Command: `python3 utils/evaluation_suite/run_suite.py --tests` — green, 246 passed. (The bare
command now also runs the paid sampled evals+traces level, per commit ca22a39.)

## Acceptance criteria (met)

- All new scratchpad entries written by PEX, policies, recovery, and completion carry `origin`,
  `version`, `turn_number`, and `used_count`.
- The pad is the session's `scratchpad.jsonl` on disk, bound at `open_session`.
- NLU runs a synchronous review pass once per turn (end of `understand`).
- PEX has no update/mutate tool for existing scratchpad entries.
- Existing deterministic NLU and PEX tests pass.
- Live behavior change is limited to the pad now persisting on disk (it silently ran in-memory
  before), the richer entry metadata, and the review diagnostics.

---

## Shipped fixes folded into this round (were rounds 3.6 / 3.7)

Both are slot-fill robustness fixes in the same NLU territory; their standalone files are merged
here so the round record stays in one place.

### fill_slots schema violations on the gemini family (was 3.6) — FIXED 2026-07-03

Slot-fill calls resolve `med` to Gemini Flash preview, whose `response_json_schema` is best-effort
(the anthropic `output_config` path enforces). A non-conforming response — e.g. a bare entity dict
instead of `{reasoning, slots{...}}` — tripped NLU's guard and every extracted slot value was
silently dropped. Fix shipped: a one-retry guardrail in `nlu.py::_fill_slots` — on a shape
violation, retry the same call once; the give-up path keeps the loud warnings.

Not built: route `fill_slots` to an enforcing family/model (`models.overrides.*.model_id` is not
consulted by `PromptEngineer.__call__` — wiring overrides into call sites is its own small design
question); re-check enforcement when `gemini-3-flash` leaves preview.

### Slot-fill response missing the `slots` key (was 3.7) — DONE 2026-07-08

Root cause was the parser, not the model: on a failed `json.loads` (e.g. truncation at
`max_tokens=2048`), `_parse_json`'s regex fallback returned the first innermost brace-free object —
a nested fragment like `{'post': ...}` with no `slots` key — so NLU gave up and the detected flow
ran with every slot empty. Fixes shipped: (A) the fallback regex is now outermost-greedy
(`r'\{.*\}'`), so it can only recover the full object and returns None on truncation, never a
nested fragment; (B) `_fill_slots` retries once on a bad shape, keeping log+return as the final
resort. Tests: `TestParseJson` (pex) + two `_fill_slots` retry tests (nlu).
