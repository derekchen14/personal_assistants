# Context Coordinator

[MEM](../modules/mem.md)'s **L1** memory — the append-only **event stream** that records the session exactly
as it happened: user utterances and actions, agent utterances and actions (PEX actions tagged), and system
events (NLU decisions, networking issues, code errors, anything harness-related). Self-check / verify failures
land here too, logged as `system` actions — this is the channel that notifies MEM of a violation (the parallel
limbs being a `TaskArtifact` carrying the violation and a Session-Scratchpad `violation` entry that notifies
NLU). It also holds the rolling summaries MEM computes; CC does not summarize itself — it is the durable
storage layer for both raw events and MEM-produced summaries.

## Turn Structure

Each turn has four attributes:

| Attribute | Values |
|---|---|
| `turn_id` | Unique identifier for cross-referencing with dialogue state snapshots |
| Role | `agent`, `user`, `system` |
| Form | `text`, `speech`, `image`, `action` |
| Content | The payload |

- `text` — standard text utterance (most common)
- `speech` — voice input (transcribed)
- `image` — image input (e.g., screenshot, photo)
- `action` — UI interaction (button click, selection, drag)

### Role-Form Matrix

| Role | Text | Speech | Image | Action |
|---|---|---|---|---|
| Agent | Yes | — | — | — |
| User | Yes | Yes | Yes | Yes |
| System | Yes | — | — | Yes |

### Turn–Flow Mapping

A single turn may involve multiple flows (e.g., when PEX chains flows within one turn), and a single flow may span multiple user turns. The Context Coordinator and Dialogue State each own one side of this relationship:

- **Context Coordinator** stores turns with `turn_id` — it knows nothing about flows.
- **Dialogue State** stores flows with `flow_id` — each flow holds pointers to the `turn_id`s in which it was active.
- The mapping is one-directional: **flows → turns**. To find which turns belong to a flow, look up the flow in a dialogue state snapshot and read its `turn_id` pointers.

## Fast-Access Window

CC maintains a `recent` list — the last 7 utterance-type turns, pre-filtered for fast access. This avoids scanning the full history for the most common retrieval pattern (recent conversation context for prompts).

CC also tracks `completed_flows` — a list of flows that finished during the current session. This is a convenience index; the canonical flow lifecycle data lives in Dialogue State.

## Core Capabilities

- **History access**: Retrieve prior turns for prompting and debugging
- **Query and filter**: Retrieve turns by role, form, `turn_id`, or content pattern
- **`compile_history(turns, keep_system)`**: Primary retrieval method. Returns the last N turns of conversation history. When `turns` is small (≤ 7), reads from the fast-access `recent` window. For larger lookbacks, falls back to scanning the full history. `keep_system` controls whether system turns are included (default: false for prompts, true for debugging).
- **Checkpoints**: Save full session state for debugging, replay, and long-term resumption (see below)

## Checkpoints

A checkpoint is a developer-facing snapshot of a full conversation session. It bundles:

- The complete turn history from the Context Coordinator
- A collection of dialogue state snapshots (see `dialogue_state.md` State History)

Checkpoints are created automatically at the end of a conversation session. They enable:

- **Debugging**: Inspect the exact state at any point in a past session
- **State replay**: Reconstruct and step through a session turn by turn
- **Long-term session resumption**: A user can return to a saved session days later

Checkpoints are not user-visible — they are a developer/system tool for diagnostics and recovery.

## Boundary with the higher MEM tiers

Within [MEM](../modules/mem.md), L1 (this event stream) is the per-session record; the higher tiers persist
beyond the session — [User Preferences](./user_preferences.md) (L2, per-account) and
[Business Context](./business_context.md) (L3, per-client). CC is the storage layer: it stores the raw event
log and holds rolling conversation summaries as special turn entries, but it does not compute them.

## Conversation Summarization

A rolling summary of older events keeps the context window bounded.

- **Trigger**: when turn count or token budget grows too large (specific threshold TBD).
- **Ownership**: MEM computes the summary; CC stores the result as a special turn entry in its log.
- **Effect**: replaces older turns in the context window, freeing space while preserving key information.

This complements [compaction](../modules/mem.md#1--context-coordinator-l1): compaction protects the message
window mid-run, while the rolling summary condenses the broader narrative across turns.
