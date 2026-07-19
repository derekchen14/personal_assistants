# Context Coordinator

[MEM](../modules/mem.md)'s **L1** memory — the append-only **event stream** that records the session exactly
as it happened, and the **single source of truth** for the conversation: the model-shaped message
list is a projection computed from it, never stored. Self-check / verify failures land here too, logged as
`system` actions — this is the channel that notifies MEM of a violation (the parallel limbs being a
`TaskArtifact` carrying the violation and a Session-Scratchpad `violation` entry that notifies NLU). It also
holds the summaries MEM computes; CC does not summarize itself — it is the durable storage layer for both raw
events and MEM-produced summaries.

## Turn Structure

Every turn is `{role, turn_type, content, turn_id, timestamp}`. The six kinds are the 2×3 grid of
`turn_type` (utterance, action) × `role` (user, agent, system); the role is a **speaker** on an
utterance and an **actor** on an action. `content` is a kind-shaped dict that **always carries
`text`**, so views render `content['text']` with no per-kind branching.

| # | role | turn_type | content | holds |
|---|---|---|---|---|
| 1 | user | utterance | `{text}` | the message the user typed |
| 2 | user | action | `{dax, payload, text}` | a click; `text` filled when typed alongside |
| 3 | agent | utterance | `{text}` | the final reply PEX produced this turn |
| 4 | agent | action | `{tool_uses, tool_results, text}` | one PEX loop round, calls and results together |
| 5 | system | utterance | `{text}` | compaction summaries, nudges, wrap-ups, [nlu]/[contemplate] notes |
| 6 | system | action | `{activity, result, text}` | compaction events, checkpoints, revisions, session start |

Speech and image inputs are designed-not-built; they would arrive as content fields on kinds 1/2,
never as new kinds.

### Turn–Flow Mapping

A single turn may involve multiple flows (e.g., when PEX chains flows within one turn), and a single flow may span multiple user turns. The Context Coordinator and Dialogue State each own one side of this relationship:

- **Context Coordinator** stores turns with `turn_id` — it knows nothing about flows.
- **Dialogue State** stores flows with `flow_id` — each flow holds pointers to the `turn_id`s in which it was active.
- The mapping is one-directional: **flows → turns**. To find which turns belong to a flow, look up the flow in a dialogue state snapshot and read its `turn_id` pointers.

## The three read surfaces

One per consumer; nothing else walks the store directly:

- **`full_conversation()`** — every turn, all six kinds, in order. For traces, debugging, and
  checkpoint slicing.
- **`compile_history(look_back, keep_system)`** — user and agent utterances rendered `Role: text`
  (system utterances included when `keep_system`). For NLU and expert prompts; the output variable
  is `convo_history`.
- **`compile_messages()`** — the API projection for the PEX agent's model calls, computed on
  demand: per-kind rendering, the latest compaction's summary spliced over its skip range, and old
  tool results rendered as the pruning placeholder. Kind 6 is invisible to the model.

## Storage

`history.jsonl` in the session dir — one turn per line, **strictly append-only**, bound and loaded
by `load_history(path)` on session open (an existing file rebuilds the turn list and seeds
`previous_summary`). Disk always matches memory once the first write lands. A user-utterance
revision follows the compaction pattern (designed-not-built): a kind-5 turn holds the revised
text, a kind-6 `revision` event `{target, revised_index}` points the views at it, and the
original turn is unchanged.

## Compaction

When PEX's real prompt-token usage passes the configured threshold, MEM triggers compaction: protect the
head and the recent tail (counted in turns), summarize the middle on a cheap auxiliary model, and **append**
two turns — nothing is destroyed or rewritten:

- **Summary — a kind-5 turn.** The summary text (`SUMMARY_PREFIX … END_OF_SUMMARY`). Summaries chain
  iteratively (`previous_summary`), so only the latest one is ever projected.
- **Compaction event — a kind-6 turn.** `{activity: 'compaction', result: {start, cut, summary_index,
  prompt_tokens}}`. `compile_messages()` reads the events, skips the compacted range, and splices the
  latest summary at its start.

Tool-result pruning is a **rendering rule**, not stored state: kind-4 turns older than the protected tail
render results over the size threshold as a placeholder, while the store (and `history.jsonl`) keeps the
full results for traces. Pair integrity is structural — a kind-4 turn holds its calls and results
together, so no boundary can split them.

## Checkpoints

A **checkpoint** is a named marker at a position in the stream — a kind-6 system action
`{activity: 'checkpoint', result: {label, turn_id, data}}` — never a copy of the stream: history as of a
checkpoint is the slice of turns up to its `turn_id`. A **snapshot** is the other thing — a passive copy
of state at a moment (`state.json`); the two never mix. `save_checkpoint(label, data, text)` writes the
marker (MEM's per-turn `turn_wrap` is the standing example); `get_checkpoint(label)` returns the newest
match, exposed to the PEX agent through `coordinate_context`.

## Boundary with the higher MEM Levels

Within [MEM](../modules/mem.md), L1 (this event stream) is the per-session record; the higher tiers persist
beyond the session — [User Preferences](./user_preferences.md) (L2, per-account) and
[Business Knowledge](./business_context.md) (L3, per-client). CC is the storage layer: it stores the raw event
log and holds MEM-produced summaries as kind-5 turns, but it does not compute them.
