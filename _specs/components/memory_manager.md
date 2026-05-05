# Memory Manager

Three-tier memory system modeled as a cache hierarchy.

## Public API

`MemoryManager` exposes flat methods, not nested inner classes:

```python
self.memory.write_scratchpad(name, payload)   # append/update a scratchpad entry
self.memory.read_scratchpad(name)             # retrieve an entry (None if absent)
self.memory.clear_scratchpad(name)            # drop an entry

self.memory.read_preference(key)              # retrieve a user preference
self.memory.write_preference(key, value)      # update a user preference

self.memory.should_summarize()                # rolling-summary trigger predicate
self.memory.dispatch_tool(name, params)       # tool-call entry point for skills
```

Domain config defines the available preference types as a starting point (e.g., analysis depth, time horizon); the runtime values stored by the manager are the source of truth.

## Session Scratchpad (L1)

- **Scope**: Single conversation, shared across flows within that session.
- **Purpose**: The canonical cross-flow channel for findings and produced output. Maintains continuity across different flows within a conversation. This is *not* a verbose log of every agent step (which adds noise), nor does it hold user intent or policy trajectories (managed by dialogue state). Instead, it stores structured per-flow records — what each flow discovered or produced — that downstream flows can read deterministically.
- **Latency Target**: Instantaneous (in-context access, no retrieval call).

### Storage Format — Structured Envelope

Scratchpad entries are dicts, not natural-language sentences. Producers and consumers depend on the shape; the shape is the contract.

- **Key** = bare flow name (e.g., `'inspect'`, `'audit'`, `'outline'`). One entry per flow.
- **Value** = `dict` with a required envelope plus flow-specific payload keys.
- **Type** of the whole pad: `dict[str, dict]` (serializable).

| Envelope field | Type | Purpose |
|---|---|---|
| `version` | `int` | Schema version of the payload; bump when payload shape changes |
| `turn_number` | `int` | The turn at which this entry was written (= `context.turn_id`) |
| `used_count` | `int` | Incremented each time a downstream flow reads this entry |
| _(payload keys)_ | varies | Flow-specific findings / output |

```python
# Producer — write at policy entry
self.memory.write_scratchpad(flow.name(), {
    'version': 1, 'turn_number': context.turn_id, 'used_count': 0,
    'findings': [...],
})

# Consumer — read by key, increment used_count
entry = self.memory.read_scratchpad('audit')
if entry:
    findings = entry['findings']
    entry['used_count'] += 1
    self.memory.write_scratchpad('audit', entry)
```

Hard cap of 64 entries; typically fewer than 16. Entries are written by producers as soon as the finding exists, not buffered until end-of-flow.

### Cross-Turn Contract

When designing a flow, decide whether it:

- **Writes findings.** It produces output another flow will consume (research-style flows). Write at policy entry with the structured envelope above.
- **Reads findings.** Read by key (or walk the whole pad) and increment `used_count` for entries you consume.
- **Neither.** Most flows don't touch the scratchpad.

Keep payloads structured (lists of dicts, not freeform prose) — downstream consumers depend on the shape.

### Promotion Triggers

When a user explicitly saves a finding, or when a snippet meets one of the criteria below, the system evaluates the entry for promotion to User Preferences or Business Context.

| Criterion | Definition |
|---|---|
| Salience | Contains a generalizable principle applicable to future situations |
| Importance (surprisal) | Unexpected or poignant finding |
| Importance (frequency) | Same finding appears repeatedly across flows |
| Importance (explicit) | User directly requests saving something to memory |

Promoted business context is written to `agent.md`.

### Eviction

When approaching the 64-entry cap, evict least-recently-used entries first. Promoted entries are already persisted to higher tiers, so eviction is safe.

## User Preferences (L2)

- **Scope**: Single user account, persists across all conversations.
- **Purpose**: Store discrete rules that override default agent behavior — effectively lambda functions that modify slot-filling or response templates. These are binary: either applicable to the current situation or not.
- **Storage Format**: Key-value pairs where the key is found by:

| Key Type | Description |
|---|---|
| Graph search | Semantically designed vector with discrete hops |
| ID | Explicit identifier for known flows where a preference always applies |

Values are discrete rules (lambda functions) that modify agent behavior when triggered.

- **Retrieval**: Hybrid lookup — embedding similarity for open-ended situations, direct ID lookup when inside a known flow.
- **Write Triggers**:
  - User onboarding (like Netflix seeding recommendations, or Lyft distinguishing drivers from riders)
  - Promotion from Session Scratchpad when patterns are detected
  - Explicit user configuration
- **Example**: User persona classification (data practitioner, data savvy, data consumer) determines response verbosity and technical depth.
- **Latency Target**: Sub-second retrieval; 1 second maximum.

### Trajectory Playbooks

User Preferences also stores successful flow trajectories as "playbooks" — reusable patterns for similar future requests. A playbook records a complete successful flow execution:

| Field | Content |
|---|---|
| `flow_name` | The flow that was executed |
| `slots` | Slot names and their filled values |
| `tool_calls` | Ordered list of tool calls made |
| `outcome` | Summary of the successful result |
| `user_query` | The original user utterance (for semantic indexing) |

**Promotion trigger**: When a flow completes successfully and the user expresses satisfaction (explicit positive feedback or continued engagement without correction), the trajectory is promoted from the scratchpad to User Preferences as a playbook.

**Retrieval**: On future requests, after NLU detects a flow, the policy checks User Preferences for playbooks with high semantic similarity to the current query. If found above threshold, the playbook is written deterministically to the scratchpad before skill invocation. The skill receives the playbook as context — a proven recipe for this type of request — and can follow or adapt it.

## Business Context (L3)

- **Scope**: Tenant or client organization, shared across all users within that tenant.
- **Purpose**: Provide organizational knowledge — documents, emails, Slack messages, call transcripts — that explains business decisions, product launches, or contextual events.
- **Storage Format**: Documents embedded in a shared vector space.

| Component | Approach |
|---|---|
| Chunking | Needs design for optimal chunk size and overlap |
| Embedding | Optimize for precision and recall |
| Retrieval | Vector search returning ~100 candidates |
| Re-ranking | Reduce to top 10 documents for context window |

- **Retrieval**: Triggered via explicit tool call (not every turn). Tenants may share anonymized industry patterns.
- **Write Triggers**:
  - Ingestion from connected data sources (docs, email, Slack, call transcripts)
  - Manual upload to `agent.md` (solves cold-start, similar to Claude Code's agent.md)
  - Promotion from Session Scratchpad for salient patterns

## Conversation Summarization

Rolling summary of older conversation turns, produced by the Memory Manager and stored in Context Coordinator.

- **Trigger**: When session scratchpad size or turn count grows too large (specific threshold TBD).
- **Ownership split**: MM calculates the summary — it has access to scratchpad insights, enabling higher-quality summaries than raw turn compression. CC stores the result as a special turn entry in its log.
- **Effect**: Replaces older turns in the context window, freeing space while preserving key information.
- **Relationship to scratchpad**: The scratchpad captures per-flow findings; conversation summarization captures the broader narrative across turns. Both inform context but serve different purposes.
