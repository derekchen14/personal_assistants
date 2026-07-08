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
**World** object — beside the [Ambiguity Handler](./ambiguity_handler.md), not on any single module. It is an
**append-only** log of thoughts and observations. Three methods:

| Method | Caller | Effect |
|---|---|---|
| `scratchpad(op='append', entry)` | any sub-agent / the PEX loop | append a new entry; the `writer` is stamped **in code** so authorship can't be forged. Appending **triggers NLU** to review. |
| `read_from_scratchpad(...)` | any sub-agent / the PEX loop | read entries (by key, by writer, or walk the pad) — read-only |
| `update_scratchpad(key, entry)` | **NLU only** | revise or correct a prior entry during review (merge duplicates, fix a stale note) |

Only NLU may mutate existing entries — everyone else appends. This keeps the log honest while letting NLU
repair it.

## Storage Format — Entry Schema

Entries are dicts. The required fields are intentionally minimal — far fewer than the Dialogue
State — and producers add whatever payload keys they need. Producers and consumers depend on the payload
shape; the shape is the contract.

- **Key** = bare flow name (e.g., `'inspect'`, `'audit'`, `'outline'`). One entry per flow.
- **Value** = `dict` with a few required fields plus flow-specific payload keys.
- **Type** of the whole pad: `dict[str, dict]` (serializable).

| Required field | Type | Purpose |
|---|---|---|
| `version` | `int` | Schema version of the payload; bump when payload shape changes |
| `turn_number` | `int` | The turn at which this entry was written (= `context.turn_id`) |
| `used_count` | `int` | Incremented each time a downstream flow reads this entry |
| _(payload keys)_ | varies | Flow-specific findings / output |

```python
# Producer — append at policy entry
world.append_to_scratchpad(flow.name(), {
    'version': 1, 'turn_number': context.turn_id, 'used_count': 0,
    'findings': [...],
})

# Consumer — read by key (read-only)
entry = world.read_from_scratchpad('audit')
findings = entry['findings'] if entry else []
```

Hard cap of 64 entries; typically fewer than 16. Entries are appended by producers as soon as the finding
exists, not buffered until end-of-flow. `used_count` bookkeeping is maintained by NLU as it reviews the pad
(via `update_scratchpad`), so consumers stay read-only and never race on a rewrite.

## Cross-Turn Contract

When designing a flow, decide whether it:

- **Writes findings.** Produces output another flow will consume (research-style flows). Append at policy entry.
- **Reads findings.** Read by key (or walk the pad) — read-only.
- **Neither.** Most flows don't touch the scratchpad.

A self-check / verify failure also appends here, as a `violation` entry. This is one of the channels that
notifies NLU (appending triggers NLU review) — the other limbs of the same fan-out are a `TaskArtifact`
carrying the violation and a Context Coordinator `system`-action event that notifies MEM.

## Race conditions & NLU review

The Dialogue State is single-writer and never at risk of merge collisions. The scratchpad is the opposite:
PEX sub-agents can run in parallel and write into it concurrently, so it is the surface that has to worry
about **race conditions**. We resolve this through [NLU](../modules/nlu.md): NLU is triggered to **review the
scratchpad whenever it is updated**, and it is the NLU loop's responsibility to keep the scratchpad operating
smoothly and uncorrupted — merging duplicates, reconciling contradictions, and pruning stale notes using its
deeper view of the user's true intent.

Writes are **non-blocking** (fire-and-forget): a producer appends and proceeds without waiting for that
review, and readers **tolerate un-reconciled entries**. NLU's reconciliation runs as background housekeeping
and settles by the turn boundary, so no one blocks an LLM review on the critical path.

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

When approaching the 64-entry cap, evict least-recently-used entries first. Promoted entries are already
persisted to higher tiers, so eviction is safe.
