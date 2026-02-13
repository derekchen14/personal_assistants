# Dialogue State

Ground the agent back to its beliefs. Explicitly define a set of categories in an ontology, predict the active user intent, and track this belief over time.

## Predicted State

Hierarchical with two levels:

### Intent (modes)
- **3 universal intents**: Plan, Converse, Internal
- **4 domain-specific intents** (roughly): Read, Prepare, Transform, Schedule

Descriptions:
- **Plan**: Stacks multiple flows or kicks off sub-agents. Requires a user feedback phase.
- **Converse**: Does not touch the data. Reserved for chatting, FAQs, general discussion.
- **Internal**: System-only housekeeping flows (memory cleanup, state repair, session summarization). Never user-triggered. **Only Internal flows can run as background sub-agents.** All other flows are single-threaded — they must wait for the active flow at the top of the stack to complete. This ensures the dialogue state is never corrupted by merge collisions.
- **Domain-specific 4**: Each domain defines its own labels, but they roughly map to: (1) reading/querying data, (2) cleaning/preparing data, (3) transforming/manipulating data and creating mappings, (4) scheduled updates or multi-session tasks like reports.

### Flows (skills)
- Also known as dialog acts, workflows, or skills
- Maximum of 64 flows per domain
- Each flow carries a unique `flow_id`
- Each flow holds a list of `turn_id` pointers referencing the Context Coordinator turns in which it was active
- This one-directional mapping (flows → turns) lets developers reconstruct which turns belong to a flow by inspecting dialogue state snapshots

## Slot-Filling

Each flow defines slots that must be resolved before the policy can execute.

### Slot Priority

| Priority | Description |
|---|---|
| Required | Must be filled before taking action |
| Elective | At least one of *N* elective slots must be filled. If an elective slot exists in a flow, at least 2 must be present. Multiple can be filled if desired |
| Optional | Not required, but helpful. Typically has a reasonable default |

### Slot Type Hierarchy

Each domain has exactly **16 slot types** — approximately 12 universal types shared across all domains, plus 4 domain-specific types. During domain creation, estimate the 4 novel slots needed; these can be refined during development.

**Universal slot types** (generic foundation):

| Type | Criteria | Description |
|---|---|---|
| `BaseSlot` | single | Single value slot (base class) |
| `GroupSlot` | multiple | Holds a list of values (e.g., multiple columns) |
| `SourceSlot` | multiple | Group slot with `min_size`; filled when `len(values) >= min_size` |
| `TargetSlot` | multiple | Destination entity (extends SourceSlot) |
| `RemovalSlot` | multiple | Entity to remove (extends SourceSlot) |
| `FreeTextSlot` | multiple | Open-ended text input |
| `LevelSlot` | numeric | Numeric value with range constraints |
| `RangeSlot` | range | Min/max range pair |
| `ExactSlot` | exact | Must match precisely (e.g., specific ID) |
| `DictionarySlot` | dictionary | Key-value pairs |
| `CategorySlot` | category | Value from a predefined category set |
| `ChecklistSlot` | multiple | Multi-select from a list |

**Domain-specific examples** (data analysis): `FormulaSlot` (expression trees for metric definitions), `ChartSlot` (visualization parameters), `ProposalSlot` (candidate values for confirmation), `ScoreSlot` (numeric with negative support).

Validation happens at the dialogue state level — a slot is not marked as filled until its value passes type validation.

## Flow Stack

The dialogue state contains the flow stack, which manages multiple workflows at once. See [flow_stack.md](./flow_stack.md) for full details.

## Flags

| Flag | Purpose |
|---|---|
| `keep_going` | Continue processing without waiting for user input |
| `has_issues` | Notifies that the state has an error (not just an ambiguity) |
| `has_plan` | We are processing a multi-step plan |
| `natural_birth` | Created by user, rather than by the agent |

`keep_going` details:
- Usually set by the policy during execution
- Agent can also set it based on the active plan and state
- Most common use: a plan has stacked multiple flows; the active flow completes its work, updates the session scratchpad in memory, RES clears things out, and the agent continues to the next flow on the stack without waiting for user input

## Implementation

- Implemented as a class with JSON serialization methods:
  - `serialize()` — convert the full state to a JSON-compatible dict for database persistence
  - `from_dict(labels)` — reconstruct a DialogueState from a persisted dict or NLU prediction labels

### State History
- **Diffs**: Store a lightweight diff after every turn
- **Snapshots**: During the RES pre-hook, all completed flows are popped off the stack. If the number of completed flows is > 1, take a full snapshot
- **Rollback**: Reconstruct any prior state by replaying diffs forward from the most recent snapshot

## Confidence Tracking

- Store top-N predictions with confidence scores for logging and debugging, N=top 3 flows.
- No automatic fallback trigger — the NLU is responsible for deciding when to engage the ambiguity handler
- Confidence data is available for inspection but does not drive state transitions
