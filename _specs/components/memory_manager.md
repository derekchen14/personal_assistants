# Memory Manager

Three-tier memory system modeled as a cache hierarchy.

## Access Pattern

Memory Manager exposes its tiers through lightweight inner classes:

- `memory.scratchpad.write('snippet text')` — append to session scratchpad
- `memory.scratchpad.read()` — retrieve all snippets
- `memory.preferences.update('preference key', value)` — update a user preference
- `memory.preferences.get('preference key')` — retrieve a preference

Domain config defines the available preference types as a starting point (e.g., analysis depth, time horizon); the code in Memory Manager is the runtime source of truth for stored values.

## Session Scratchpad (L1/L2 Cache)

- **Scope**: Single conversation, shared across flows within that session.
- **Purpose**: Maintain continuity across different analysis flows within a conversation. This is *not* a verbose log of every agent progress message (which adds noise), nor does it hold user intent or policy trajectories (managed by dialogue state). Instead, it stores 3-5 summarized snippets capturing what each flow discovered. For example, insights from peeking at the first 100 rows of a table, so subsequent flows can build on prior analysis.
- **Storage Format**: Natural language sentences. Each snippet is reflective and summarized, not raw observations. Hard cap of 64 snippets; typically fewer than 16. Snippets are written at the *end* of each flow, not during.
- **Retrieval**: Direct access (always in context) when the tool is called. No embedding lookup required, making this extremely fast.
- **Promotion Triggers**: When a user saves an ad-hoc analysis into a report, the system evaluates scratchpad snippets for promotion to Business Context or User Preferences.

| Criterion | Definition |
|---|---|
| Salience | Contains a generalizable principle applicable to future situations |
| Importance (surprisal) | Unexpected or poignant finding |
| Importance (frequency) | Same snippet appears repeatedly across analyses |
| Importance (explicit) | User directly requests saving something to memory |

Promoted business context is written to `agent.md`.

- **Eviction**: When approaching the 64-snippet cap, evict least-recently-used (LRU) snippets first. Promoted snippets are already persisted to higher tiers, so eviction is safe.

- **Latency Target**: Instantaneous (in-context access, no retrieval call).

## User Preferences (RAM)

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

### Trajectory Playbooks

User Preferences also stores successful flow trajectories as "playbooks" — reusable patterns for handling similar future requests. A playbook records a complete successful flow execution:

| Field | Content |
|---|---|
| `flow_dact` | The flow that was executed |
| `slots` | Slot names and their filled values |
| `tool_calls` | Ordered list of tool calls made (tool_id + key parameters) |
| `outcome` | Summary of the successful result |
| `user_query` | The original user utterance (for semantic indexing) |

**Promotion trigger**: When a flow completes successfully (Completed lifecycle state) and the user expresses satisfaction (explicit positive feedback or continued engagement without correction), the trajectory is promoted from the session scratchpad to User Preferences as a playbook.

**Retrieval**: On future requests, after NLU predicts a flow, the policy checks User Preferences for playbooks with high semantic similarity to the current query. If a matching playbook is found (similarity above threshold), it is written deterministically to the session scratchpad before skill invocation. The skill receives the playbook as context — a proven recipe for handling this type of request — and can follow or adapt it.

**Storage format**: Playbooks are indexed by semantic embedding of `user_query`, retrievable via the same hybrid lookup as other preferences (embedding similarity for open-ended, direct flow ID lookup for exact matches).

- **Latency Target**: Sub-second retrieval; 1 second maximum.

## Business Context (Hard Disk)

- **Scope**: Tenant or client organization, shared across all users within that tenant.
- **Purpose**: Provide organizational knowledge — documents, emails, Slack messages, call transcripts — that explains business decisions, product launches, or contextual events (e.g., "why did users spike on Nov 3rd?").
- **Storage Format**: Documents embedded in a shared vector space. We embrace unstructured data rather than forcing complex ontologies (per the Bitter Lesson). Structured data in databases should still leverage semantics, but unstructured retrieval relies on embeddings.

| Component | Approach |
|---|---|
| Chunking | Needs design for optimal chunk size and overlap |
| Embedding | Optimize for precision and recall |
| Retrieval | Vector search returning ~100 candidates |
| Re-ranking | Reduce to top 10 documents for context window |

- **Retrieval**: Triggered via explicit tool call (not every turn). Tenants may share anonymized industry patterns (e.g., "clients in this industry typically want X").
- **Write Triggers**:
  - Ingestion from connected data sources (docs, email, Slack, call transcripts)
  - Manual upload to `agent.md` file (solves cold-start problem, similar to Claude Code's agent.md)
  - Promotion from Session Scratchpad for salient/important patterns

## Conversation Summarization

Rolling summary of older conversation turns, produced by the Memory Manager and stored in Context Coordinator.

- **Trigger**: When session scratchpad size or turn count grows too large (specific threshold TBD).
- **Ownership split**: MM calculates the summary — it has access to scratchpad insights, enabling higher-quality summaries than raw turn compression. CC stores the result as a special turn entry in its log.
- **Effect**: Replaces older turns in the context window, freeing space while preserving key information.
- **Relationship to scratchpad**: The scratchpad captures per-flow insights; conversation summarization captures the broader narrative of what happened across turns. Both inform context but serve different purposes.
