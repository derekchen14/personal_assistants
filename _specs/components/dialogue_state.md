# Dialogue State

[NLU](../modules/nlu.md)'s **structured** belief — the ontology-filled, directly-queryable half of what the
agent thinks (the open-ended half is NLU's [Session Scratchpad](./session_scratchpad.md)).
Ground the agent back to its beliefs: explicitly define a set of categories in an ontology, predict the active
user intent, and track this belief over time.

## Predicted Belief State

Hierarchical with two levels:

### Intent (modes)
- **3 universal intents**: Plan, Converse, Clarify
- **4 domain-specific intents** (roughly): Read, Prepare, Transform, Schedule

Descriptions:
- **Plan**: Stacks multiple flows or kicks off sub-agents. Requires a user feedback phase.
- **Converse**: Does not touch the data. Reserved for chatting, FAQs, general discussion.
- **Clarify**: The agent immediately recognizes the request is unclear, underspecified, or ambiguous, and routes to the [Ambiguity Handler](./ambiguity_handler.md) to resolve internally or ask — rather than guessing a domain flow.
- **Domain-specific 4**: Each domain defines its own labels, but they roughly map to: (1) reading/querying data, (2) cleaning/preparing data, (3) transforming/manipulating data and creating mappings, (4) scheduled updates or multi-session tasks like reports.

> Memory work is **not** an intent. There is no `Internal` intent — `recap` / `recall` / `retrieve` are MEM skills (see [mem.md](../modules/mem.md)), and other deterministic operations are plain tools. The Dialogue State is written only by NLU's belief tools, so it is single-writer and never at risk of merge collisions; the surface that guards against race conditions is the [Session Scratchpad](./session_scratchpad.md), maintained by NLU.

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
| Elective | At least one of *N* elective slots must be filled. A flow with elective slots must have ≥2 — single-elective is invalid (convert to required or optional) |
| Optional | Not required, but helpful. Typically has a defensible default that policies commit at entry |

### Slot Type Hierarchy

Each domain has exactly **16 slot types** — 12 universal types shared across all domains, plus 4 domain-specific types. During domain creation, estimate the 4 novel slots needed; these can be refined during development. Full tree, grounding rules, and domain-specific examples live in [Workflow Planner § Slot Type Hierarchy](./workflow_planner.md).

**Universal slot types (12)** — `BaseSlot` is the abstract parent (never instantiated directly):

| Type | Parent | Description |
|---|---|---|
| `GroupSlot` | BaseSlot | Holds a list of items |
| `SourceSlot` | GroupSlot | References existing entities (grounding); `entity_part` optional |
| `TargetSlot` | SourceSlot | New entities being created |
| `RemovalSlot` | SourceSlot | Entities being removed |
| `FreeTextSlot` | GroupSlot | Open-ended text or operations |
| `ChecklistSlot` | GroupSlot | Ordered steps to check off |
| `ProposalSlot` | GroupSlot | Candidate options for confirmation |
| `LevelSlot` | BaseSlot | Single numeric value with range constraints |
| `PositionSlot` | LevelSlot | Non-negative integer position |
| `CategorySlot` | BaseSlot | Exactly one from a predefined set (≤8, mutually exclusive) |
| `ExactSlot` | BaseSlot | Specific token or phrase |
| `DictionarySlot` | BaseSlot | Key-value pairs |
| `RangeSlot` | BaseSlot | Start/stop interval (often date range) |

`ProbabilitySlot` and `ScoreSlot` are common LevelSlot subclasses included in most domains' 4 domain-specific picks.

**Domain-specific examples**: Dana (data analysis) — `ChartSlot`, `FunctionSlot`. Hugo (blog writing) — `ChannelSlot`, `ImageSlot`.

Validation happens at the dialogue state level — a slot is not marked as filled until its value passes type validation.

### Idea (future) — recursive self-verifying slot values

> **Status: future idea, not adopted.** Today a `SourceSlot` grounds a *flat* set of entity parts, each carrying
> a `ver` flag. A legacy data-analysis system generalized this to a **recursive** slot value: a metric held a
> tree of sub-expressions down to leaf clauses, where (a) `ver` **cascaded** — a node is verified only when all
> its children are; (b) a `drop_unverified` pass **pruned** unconfirmed branches; and (c) every node could
> **self-describe** in natural language and **self-render** to SQL. This is the right model for a complex
> artifact built up and confirmed piece-by-piece (a formula, a deeply nested outline). We are **not** building
> it now — flat `{post, sec, snip, chl, ver}` grounding covers the current content domains, and the recursive
> machinery only earns its keep in formula-heavy domains (e.g. Dana). Recorded so the grounding contract can
> scale to a tree later without re-deriving it.

## Flow Stack block

The dialogue state's `flow_stack` block holds the stacked flows, which manage multiple workflows at once. The
routing/progress layer that drives them is PEX's [Workflow Planner](./workflow_planner.md) — see it for full
details.

## Belief Tools

The Dialogue State (NLU) exposes one **read** tool — `understand`, which returns the serialized state (flow,
intent, confidence, slots, grounding) — and three purpose-specific **write** tools. There is **no generic
`write_state`**:

| Tool | Signature | Writes |
|---|---|---|
| `classify_intent` | `classify_intent(text, hint=None)` | the predicted intent |
| `detect_flow` | `detect_flow(text, intent=None)` | the detected flow + close candidates (the [Workflow Planner](./workflow_planner.md) stacks it) |
| `fill_slots` | `fill_slots(flow, payload=None)` | slot values; entity extraction (its sub-task) writes the `grounding` block |

Two writes that touch a flow are **not** the Dialogue State's: a flow's lifecycle `status` is set by PEX's
`complete_flow` (grounding-gated), and stack structure (`stackon` / `fallback` / `pop_completed`) is the
[Workflow Planner](./workflow_planner.md)'s.

## No Flags

The state carries **no flag block**. The four former flags are gone:

- `natural_birth` — a deterministic property of each flow (user- vs agent-created), held on the flow and
  answered by the [Workflow Planner](./workflow_planner.md); PEX, as the central orchestrator, already has the
  full view and never needs a state flag for it.
- `has_plan` — computed from the agenda (any pending flow carries a `plan_id`).
- `has_issues` — already carried by the violation / error channel.
- `keep_going` — PEX loop control, not stored belief; PEX is a tool-calling loop that each round issues tool
  calls and/or a user-facing message and loops again until it chooses to stop. Not a flag PEX reads — an
  emergent property of whether it runs another round.

## Implementation

- Implemented as a class with JSON serialization methods:
  - `serialize()` — convert the full state to a JSON-compatible dict for database persistence
  - `from_dict(labels)` — reconstruct a DialogueState from a persisted dict or NLU prediction labels

### State History
- **Snapshots**: The state persists as a per-turn snapshot — a hybrid record of the full serialized JSON doc
  plus a few promoted, indexed columns for querying. No bespoke diff machinery.
- **Rollback**: The existing `undo` flow replays snapshots — already working in Hugo, kept as-is. No new
  rollback machinery.

## Confidence Tracking

- Store top-N detections with confidence scores for logging and debugging, N=top 3 flows.
- No automatic fallback trigger — the NLU is responsible for deciding when to engage the ambiguity handler
- Confidence data is available for inspection but does not drive state transitions
