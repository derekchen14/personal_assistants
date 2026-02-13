# Context Coordinator

The conversation log. Stores the complete turn history exactly as it happened and holds summaries computed by Memory Manager. CC does not perform summarization itself — it is the storage layer for both raw turns and MM-produced summaries.

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

A single turn may involve multiple flows (e.g., when `keep_going` chains flows within one turn), and a single flow may span multiple user turns. The Context Coordinator and Dialogue State each own one side of this relationship:

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

## Boundary with Memory Manager

The Context Coordinator and Memory Manager serve complementary roles:

- **Context Coordinator**: Stores the raw turn log and holds MM-computed conversation summaries as special turn entries. CC is the storage layer — it does not summarize, but it is the source of truth for both raw turns and their summaries.
- **Memory Manager**: Owns all summarization of conversation history for context-limit management. MM calculates rolling summaries (using scratchpad insights for higher quality) and writes them to CC. The Session Scratchpad stores flow-level insights (what each flow discovered), not raw turns.
