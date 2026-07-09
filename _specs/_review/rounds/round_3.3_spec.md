# Round 3.3 — Session Scratchpad contract + synchronous NLU review

Status: **draft for alignment**. Implements §3.3 of `round_3_nlu.md`, with the already-landed
World-owned `SessionScratchpad` as the starting point. Scope is NLU/PEX scratchpad wiring only;
intent routing (§3.1), ambiguity binding (§3.2), and flag cleanup (§3.4) are separate sub-rounds.

---

## The change in one paragraph

Hugo already has a shared `SessionScratchpad` on the World, but the write contract is still loose:
some entries omit the required minimal schema, PEX writes directly to the component, and appends do
not notify NLU. This round makes the scratchpad a real NLU-owned working ledger: every producer
append carries `version`, `turn_number`, and `used_count`; writers append through an NLU-facing
contract so NLU can run a synchronous review pass at safe turn points; and only NLU can mutate or
normalize existing entries. The continuous background review loop remains designed-not-built.

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

### 1. Entry schema is enforced at append time

Every scratchpad entry must contain:

- `version`: integer schema version for that payload.
- `turn_number`: current conversation turn id.
- `used_count`: integer counter, initially `0`.

The component should normalize simple producer entries by adding missing defaults from code, not
trust the LLM to remember bookkeeping fields. That keeps the PEX tool surface ergonomic while making
the persisted ledger conformant.

Recommended helper:

```python
def _normalize_entry(self, entry: dict, *, turn_number: int | None = None) -> dict:
    normalized = dict(entry)
    normalized.setdefault('version', 1)
    normalized.setdefault('turn_number', turn_number or 0)
    normalized.setdefault('used_count', 0)
    return normalized
```

`version` should be an `int`, not the current string `'1'` used by `save_findings`.

### 2. Writers append through NLU-facing methods

Add thin methods on `NLU`:

```python
def append_to_scratchpad(self, entry: dict, writer: str = 'orchestrator') -> dict: ...
def read_from_scratchpad(self, key: str | None = None, writer: str | None = None,
                         keys: list[str] | None = None): ...
def review_scratchpad(self) -> dict: ...
```

`append_to_scratchpad` normalizes the entry, writes it with the code-stamped writer, and runs the
synchronous review pass. PEX should call this method for orchestrator and component appends instead
of writing the component directly.

Do **not** expose a general scratchpad updater to PEX. If an update method is added to the component,
it is NLU-only and private to the review pass.

### 3. Review is synchronous for now

The full continuous event-triggered loop stays deferred. For this round, review runs synchronously
after each append and is deliberately conservative:

- Drop or quarantine malformed entries only if they cannot be normalized.
- Merge obvious duplicate keys in in-memory mode only if it is lossless.
- Leave semantic contradiction resolution as `# designed-not-built`.
- Return a small diagnostic result, e.g. `{'reviewed': True, 'size': ...}`.

This is enough to prove the entry contract and give future NLU review a single hook without adding a
background worker.

### 4. Reads stay read-only

`read_from_scratchpad` and PEX's `read_scratchpad` tool must not increment `used_count` in this
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

## Implementation sketch

### `backend/components/session_scratchpad.py`

Add code-side normalization and, if needed, a private update helper for NLU:

- `write(entry, writer='orchestrator', turn_number=None)` normalizes required fields before stamping
  `writer`.
- `write_completion(flow, summary, metadata=None, turn_number=None)` writes a schema-conformant
  completion record.
- Optional: `update(key, entry)` with a docstring stating NLU-only. If this is not needed for the
  synchronous no-op review, do not add it yet.

### `backend/modules/nlu.py`

Add the NLU scratchpad surface:

- `append_to_scratchpad(...)` calls `self.world.scratchpad.write(...)`, passing
  `self.world.context.turn_id`.
- `read_from_scratchpad(...)` delegates to `self.world.scratchpad.read(...)`.
- `review_scratchpad(...)` performs the conservative synchronous pass and returns diagnostics.

This keeps NLU as the owner of scratchpad health while the physical component stays on the World.

### `backend/modules/pex.py`

Route appends through NLU where PEX has access to it. Because `World` currently stores components,
not modules, there are two acceptable designs:

1. **Recommended:** add `world.nlu = nlu` in `World.__init__`, then PEX calls
   `self.world.nlu.append_to_scratchpad(...)`.
2. **Fallback:** add `World.append_to_scratchpad(...)` as a delegating method during construction.

Use the recommended design unless there is a clear import-cycle or test-fixture issue.

Update direct writers:

- `_dispatch_append_scratchpad`
- `_dispatch_save_findings_tool`
- `_dispatch_recover_ambiguity`
- `activate_flow` completion fallback if it writes through `write_completion`

Policy-owned completion records can still be written through PEX, but the final write should pass
through the NLU append contract or a normalized `write_completion(..., turn_number=...)`.

## Decisions

### D1 — Where should normalization live?

**Recommendation: component + NLU wrapper.**

Normalize in `SessionScratchpad.write` so every writer is protected, including tests and future
callers. Keep the NLU wrapper because it is the review trigger and ownership boundary.

Alternative: normalize only in NLU. Rejected because direct component writes would remain footguns
and existing code already has several direct write paths.

### D2 — Should PEX see `update_scratchpad`?

**Recommendation: no.**

PEX and sub-agents append only. Mutating existing scratchpad entries is NLU-only. If the component
gets an update helper, do not add it to orchestrator or sub-agent tool definitions.

### D3 — Should read increment `used_count` now?

**Recommendation: no.**

Read counting sounds simple but changes persistence semantics and can create races in JSONL mode.
Leave `used_count` initialized and stable in this round; wire real counting when NLU review becomes
stateful.

## Tests

Add deterministic tests in `utils/evaluation_suite/_tests/nlu_unit_tests.py` and/or
`pex_unit_tests.py`:

1. `SessionScratchpad.write` adds `version`, `turn_number`, and `used_count` when omitted.
2. `write_completion` emits a schema-conformant completion record.
3. `_dispatch_append_scratchpad` routes through NLU and triggers `review_scratchpad`.
4. `save_findings` writes `version` as an integer and includes the required fields.
5. `read_scratchpad` remains read-only and does not mutate `used_count`.

Expected command:

```bash
python3 utils/evaluation_suite/run_suite.py --tests nlu,pex
```

Note: the local system Python may need the project test dependencies installed (`pytest` at
minimum) before this command can run.

## Acceptance criteria

- All new scratchpad entries written by PEX, policies, recovery, and completion contain
  `version`, `turn_number`, and `used_count`.
- Appends trigger a synchronous NLU review hook.
- PEX has no general update/mutate tool for existing scratchpad entries.
- Existing deterministic NLU and PEX tests pass.
- Live behavior is unchanged except for better scratchpad metadata and review diagnostics.
