# Session Scratchpad

[NLU](../modules/nlu.md)'s open-ended working ledger — the cross-flow channel where the swarm shares findings
within a single conversation. It is the **loosely-structured** counterpart to the
[Dialogue State](./dialogue_state.md): the state holds ontology-typed belief with many required fields, while
a scratchpad entry carries only a **few required fields** plus whatever flow-specific payload a producer
chooses to write. That contrast is the point — the state is what the agent *believes* (typed, queryable); the
scratchpad is what the swarm is currently *working on* (minimal schema, free to grow).

## Scope & purpose

- **Scope**: a single conversation, shared across flows within that session.
- **Purpose**: the canonical cross-flow channel for findings and produced output — what each flow discovered
  or produced, so downstream flows can read it deterministically. It is not a verbose log of every step, and
  it does not hold user intent or policy trajectories (those live in the Dialogue State).
- **Latency**: instantaneous, in-context — no retrieval call.

## Code home & API

The scratchpad is a **shared resource** that many components read from and write to, so it lives on the
**World** object — beside the [Ambiguity Handler](./ambiguity_handler.md), not on any single module. Every
writer reaches it directly (`world.scratchpad` / PEX's `session_scratchpad`) — there is no NLU write proxy.
It is an **append-only** log of thoughts and observations. Four methods (plus `attach`, which
`World.open_session` calls to bind the pad to its session file):

| Method | Caller | Effect |
|---|---|---|
| `append_entry(origin, entry)` | any sub-agent / the PEX loop / NLU | append a new entry; `origin` is stamped **in code** so it can't be forged |
| `read(origin=None, keys=None)` | any sub-agent / the PEX loop | read entries (by origin, by present keys, or walk the pad) — read-only |
| `update_entry(origin, turn_number, entry)` | **NLU only** | modify the EXISTING entry identified by origin + turn_number (the pad's unique ID) in place; raises when no entry carries that ID |
| `prune_entry(origin, turn_number)` | **NLU only** | remove the entry identified by origin + turn_number — a stale note, a merged duplicate |

Only NLU may mutate existing entries — everyone else appends. This keeps the log honest while letting NLU
repair it. NLU reviews the pad once per turn at its own turn point (the end of `understand`), which also
covers the previous turn's PEX/policy appends; a per-append review trigger is designed-not-built.

## Storage Format — Entry Schema

Entries are dicts. The required fields are intentionally minimal — far fewer than the Dialogue
State — and producers add whatever payload keys they need. Producers and consumers depend on the payload
shape; the shape is the contract. Each CODE writer stamps the required fields itself — nothing is added
behind its back; the one exception is the LLM-authored `append_to_scratchpad` tool entry, which PEX's
dispatch handler normalizes in code (and rejects when it lacks an `origin`).

- **Storage**: always the append-only JSONL file `<session dir>/scratchpad.jsonl` (one stamped entry per
  line), bound at `World.open_session` — the disk file is what makes the pad automatically shared across
  all agents and sub-agents. When an origin is written more than once, the **newest entry wins** on read.

| Required field | Type | Purpose |
|---|---|---|
| `origin` | `str` | What the entry is from / about — a bare flow name (`'find'`, `'audit'`, `'propose'`), `'orchestrator'`, or a stable topic (`'recovery'`). Stamped **in code** by `append_entry`; with `turn_number` it forms the pad's unique ID |
| `version` | `int` | Schema version of the payload; bump when payload shape changes |
| `turn_number` | `int` | The turn at which this entry was written (= `context.turn_id`) |
| `used_count` | `int` | `0` at append; bumped by a consumer that explicitly reports using the entry |
| _(payload keys)_ | varies | Flow-specific findings / output |

Completion records add `summary` and `metadata` on top of the required fields; their `origin` is the
completed flow's name. There is no dedicated completion method — `complete_flow` (and
`activate_flow`'s fallback) build the record and call `append_entry` like any other producer.

```python
# Producer — append at policy entry (the producer stamps the required fields itself)
self.scratchpad.append_entry(flow.name(), {
    'version': 1, 'turn_number': context.turn_id, 'used_count': 0,
    'findings': [...],
})

# Consumer — read by origin (read-only; newest entry under the origin wins)
entries = self.scratchpad.read(origin='audit')
findings = entries[-1]['findings'] if entries else []
```

Target cap of 64 entries (typically fewer than 16); cap enforcement is designed-not-built — see
Eviction below. Entries are appended by producers as soon as the finding
exists, not buffered until end-of-flow. Reads never mutate `used_count` — a consumer that actually uses an
entry (e.g. a Revise skill reporting `used` keys) writes the bump back explicitly; automatic `used_count`
maintenance by NLU review is designed-not-built.

## Cross-Turn Contract

When designing a flow, decide whether it:

- **Writes findings.** Produces output another flow will consume (research-style flows). Append at policy entry.
- **Reads findings.** Read by key (or walk the pad) — read-only.
- **Neither.** Most flows don't touch the scratchpad.

A self-check / verify failure also appends here, as a `violation` entry. NLU sees it at its next review
pass — the other limbs of the same fan-out are a `TaskArtifact` carrying the violation and a Context
Coordinator `system`-action event that notifies MEM.

## Race conditions & NLU review

The Dialogue State is single-writer and never at risk of merge collisions. The scratchpad is the opposite:
PEX sub-agents can run in parallel and write into it concurrently, so it is the surface that has to worry
about **race conditions**. We resolve this through [NLU](../modules/nlu.md): `NLU.review_scratchpad()` runs
**once per turn at NLU's own turn point** (the end of `understand`) and keeps the pad conformant. The
current pass is conservative — it losslessly repairs entries missing the required fields via the NLU-only
`update_entry` and returns diagnostics `{reviewed, size, repaired}`; the semantic pass (merging duplicates
via `update_entry` + `prune_entry`, reconciling contradictions, pruning stale notes) and the per-append /
background review trigger are designed-not-built.

Writes are **non-blocking** (fire-and-forget): a producer appends and proceeds without waiting for any
review, and readers **tolerate un-reconciled entries** (newest entry under a key wins).

## Promotion Triggers

When a user explicitly saves a finding, or when an entry meets one of the criteria below, the entry is
evaluated for promotion to [User Preferences](./user_preferences.md) (L2) or
[Business Context](./business_context.md) (L3).

| Criterion | Metric |
|---|---|
| Importance (frequency) | Entry read by ≥N flows — tracked by the `used_count` field |
| Salience + surprisal | A single LOW-tier LLM-judge call scores generalizability and unexpectedness |
| Importance (explicit) | User-directed save via `store_preference` |

Auto-promotion (the frequency counter plus the low-tier LLM-judge) runs as a **background MEM task**, off the
turn's critical path; explicit saves go through `store_preference`. Promoted business context is written to
`agent.md`.

## Eviction

Designed-not-built. When approaching the 64-entry cap, evict least-recently-used entries first — in the
JSONL form this is an NLU review job (rewrite minus the evicted origins), not an in-place pop. Promoted
entries are already persisted to higher tiers, so eviction is safe.
