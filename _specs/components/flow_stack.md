# Flow Stack

Lives within the dialogue state, but is complex enough to warrant its own description.

## What is a Flow?

- Flows hold the slots, metadata, and other information about the action to take
  - Also known as "workflows" in extended form
  - Historic name: "dialog acts"; modern name: sometimes called "sub-agents"
- The **policy** is the code that actually executes the action
  - Implemented as a Skill (https://agentskills.io/what-are-skills) with access to tools (https://www.anthropic.com/engineering/writing-tools-for-agents)
  - Sometimes a tool is actually just a call to an MCP server

## Flow Class Hierarchy

Each intent has a lightweight **parent flow class** that defines shared hooks and common behavior for flows within that intent. Parent classes do not define shared slots — slots are flow-specific.

```
BaseFlow
  ├── [IntentA]ParentFlow    # e.g., AnalyzeParentFlow, SourceParentFlow
  │   ├── SpecificFlow1      # e.g., QueryFlow, BrowseFlow
  │   ├── SpecificFlow2
  │   └── ...
  ├── [IntentB]ParentFlow
  │   └── ...
  └── ...
```

### Flow Methods

Every flow inherits these methods from `BaseFlow`:

| Method | Purpose |
|---|---|
| `fill_slots_by_label(labels)` | **System 1**: Fast entity extraction from NLU prediction labels — deterministic slot-filling from model output |
| `fill_slot_values(context, memory)` | **System 2**: Deeper contemplation for remaining slots — uses LLM reasoning to fill from context and memory |
| `is_filled()` | Check if all required slots and at least one elective (if any) are filled |
| `needs_to_think()` | Determine if further contemplation is needed before execution |
| `serialize()` | Serialize the flow for persistence |

These methods are distinct from the lifecycle states below — they describe *how* a flow prepares for execution, while lifecycle states describe *where* a flow is in the stack.

## Slots, Tools, and the Flow-Execution Relationship

A flow binds two concerns together:

- **Slots** — what NLU extracts from the user's utterance. Slots drive ambiguity detection and slot-filling. They determine *what* the user wants to act on.
- **Tools** — what PEX can call to execute the action. Tools drive the policy's execution plan. They determine *how* the action gets carried out.

```
Flow
├── slots: {slot_name: SlotInstance, ...}    # NLU fills these
└── tools: [tool_name, ...]                 # PEX calls these
```

### Slot Type Hierarchy — 12 Universal + 4 Domain-Specific

Every domain defines exactly **16 slot types**: 12 universal types shared across all assistants, plus 4 domain-specific types selected by that domain. Each domain's `flow_stack/slots.py` contains all 16 class definitions directly (self-contained, no cross-module slot imports).

#### Universal Slots (12)

```
BaseSlot
├── GroupSlot            # multiple items in a list
│   ├── SourceSlot       # references existing entities (grounding)
│   │   ├── TargetSlot   # new entities being created
│   │   └── RemovalSlot  # entities being removed
│   ├── FreeTextSlot     # free-form text or operations
│   ├── ChecklistSlot    # ordered steps to check off
│   └── ProposalSlot     # options to select from
├── LevelSlot            # single numeric value
│   ├── PositionSlot     # non-negative integer position
│   ├── ProbabilitySlot  # 0-1 range [domain-specific, common option]
│   └── ScoreSlot        # any numeric value [domain-specific, common option]
├── CategorySlot         # exactly one from a predefined set (8 max, mutually exclusive)
├── ExactSlot            # specific token or phrase
├── DictionarySlot       # key-value pairs
└── RangeSlot            # start/stop interval (often date range)
```

#### Grounding Slots

**SourceSlot** references existing entities. Each entity is `{tab, col, row, ver, rel}` — the hierarchy is built into a single slot. The `entity_part` parameter is optional; when omitted, the slot accepts any entity type.

Each domain defines its own grounding entities:

| Domain | Grounding entities |
|--------|-------------|
| Dana (Data Analysis) | table, column, row |
| Hugo (Blog Writing) | post, section, note, platform |

A flow's grounding slot should be named **`'source'`** (matching `BaseFlow.entity_slot`). One SourceSlot handles the full entity hierarchy — do not split entity parts into separate slots, since a single entity `{tab, col, row}` already encodes the full reference. Not every flow requires a grounding slot (e.g., `chat`, `brainstorm`).

**TargetSlot → SourceSlot**: Entities being created (new columns, new rows, new posts).

**RemovalSlot → SourceSlot**: Entities being deleted or removed.

#### Domain-Specific Slots (4 per domain)

Each domain selects 4 additional slot types. Some are common options (like ProbabilitySlot, ScoreSlot) that most domains will include; others are truly unique to the domain. All are real `BaseSlot` subclasses.

| Domain | Common options | Domain-unique |
|--------|---------------|---------------|
| Dana | ProbabilitySlot, ScoreSlot | **ChartSlot** (chart reference), **FunctionSlot** (executable code) |
| Hugo | ProbabilitySlot, ScoreSlot | **PlatformSlot** (publishing destination), **ImageSlot** (hero image, diagram) |

This 12+4 pattern is the scalable architecture for adding new domains. When creating a new assistant:
1. Copy the 12 universal slot classes from any existing domain's `slots.py`
2. Select common options (ProbabilitySlot, ScoreSlot) if the domain needs them
3. Define domain-unique slot types as `BaseSlot` subclasses (total domain-specific = 4)
4. Define the domain's grounding entity vocabulary

### Elective Rule

A slot's priority is one of: `required`, `optional`, `elective`.

- **required** — must be filled before execution
- **optional** — enhances execution but not needed
- **elective** — at least one elective slot must be filled (choice among alternatives)

**The elective constraint**: A flow with elective slots must have ≥2 elective options. A single elective is meaningless — convert it to `required` (if the flow needs it) or `optional` (if it doesn't). The `summarize` flow with `chart` and `table` as electives is valid (pick at least one artifact to summarize). A flow with only `format: elective` is invalid — make it `required` or `optional`.

### CategorySlot Constraints

A CategorySlot's options list must be:
- **Mutually exclusive** — selecting one option rules out all others
- **At most 8 options** — if you need more than 8, the taxonomy is too fine-grained for a slot; consider grouping or using FreeTextSlot instead

### ExactSlot as Category Extension

When a CategorySlot covers the common cases but users may need values beyond the predefined set, pair it with an ExactSlot as electives. The user fills either the category (pick from the list) or the exact slot (provide a custom value):

```python
self.slots = {
    'custom_tone': ExactSlot(priority='elective'),
    'chosen_tone': CategorySlot(['formal', 'casual', 'technical', ...], priority='elective'),
}
```

This preserves the structured options for NLU prediction while allowing open-ended input when needed.

## Data Structure

The data structure is a **stack** (not a dict or list or queue) to ensure we only ever have one "active" flow:

- When issues get complicated, we **stack on** new flows
- When flows are completed, they get **popped off**
- When a flow is incorrectly detected, we may **fall back** to other flows

**Stack Depth**: There is no explicit stack depth limit. The 64-flow-per-domain cap in dialogue_state is an ontology limit (how many flow *types* exist in a domain), not a stack limit. In practice, stacks are shallow (2–5 flows).

## Flow Lifecycle

Each flow on the stack is in exactly one of four states:

| State | Description |
|-------|-------------|
| **Pending** | Stacked but not yet active — waiting its turn (e.g., queued in a plan). |
| **Active** | Top of the stack; currently being executed by the policy. |
| **Completed** | Successfully finished; will be popped during the RES pre-hook. |
| **Invalid** | Incorrectly detected or encountered a hard failure; will be popped during fallback. |

## Concurrency Model

All user-facing flows are **single-threaded** — they must wait for the active flow at the top of the stack to complete before the next flow can begin. This ensures the dialogue state is never corrupted by merge collisions.

Only **Internal** flows (system housekeeping such as memory cleanup, state repair, session summarization) can run as background sub-agents. At any given time there may be one active user-facing flow and multiple Internal flows running in parallel.

Internal flows can carry lightweight dependency annotations (e.g., "flow B depends on flow A") to allow the Agent to parallelize independent Internal tasks while preserving ordering for dependent ones.

## Plan Flow Lifecycle

When a Plan intent decomposes a task, the Plan flow itself sits at the bottom of the sub-flow stack. If Plan X adds sub-flows A, B, C:

```
Stack (top → bottom): [A (Active), B (Pending), C (Pending), X (Pending)]
```

After A completes and is popped by RES, the stack becomes `[B, C, X]`. The Agent then performs a **replanning check** before activating B:

1. **Continue** — if scratchpad findings align with the original plan, activate B normally
2. **Reorder** — if A's results suggest C should run before B, swap their positions
3. **Expand** — if A revealed a new requirement, push a new sub-flow D onto the stack
4. **Prune** — if A's results make B unnecessary, mark B as Invalid and skip to C

The replanning check reads the scratchpad (where A's findings were written) and the remaining plan state. It is a lightweight prompted decision, not a full re-invocation of the Plan policy.

### Plan Completion

The Plan flow (X) is the last flow on the stack. When all sub-flows complete and X becomes Active, PEX runs X's policy one final time. This final execution is a **prompted decision**: the Plan policy reviews the scratchpad (which now contains findings from all sub-flows) and decides whether the overall task is complete or requires further work. If further work is needed, it stacks new sub-flows and sets `keep_going`. If complete, it marks itself Completed and lets RES compile a final response from all accumulated findings.

This means Plan flow completion is never automatic — it always requires an explicit assessment that the user's objective has been satisfied.

### Plan-Aware Stack Tracking

The flow stack tracks which flows belong to which plan via a `plan_id` field on each sub-flow. This enables:

- **Replanning scope**: The Agent knows which Pending flows belong to the current plan vs. independently stacked flows
- **Plan progress**: The Agent can determine how far through a plan it is (e.g., 2 of 4 sub-flows completed)
- **Plan abandonment**: If the Plan flow itself is marked Invalid, all sub-flows with matching `plan_id` are also marked Invalid and popped

### LATS for Plan Decomposition

For complex decomposition decisions, the Plan policy can use Language Agent Tree Search (LATS) to explore multiple decomposition strategies before committing. The Plan policy generates 2-3 candidate decompositions (different orderings, different sub-flow selections), evaluates each against the user's stated objective, and selects the highest-scoring plan. This is optional — simple plans (2-3 obvious sub-flows) do not need tree search. LATS is warranted when:

- The decomposition has 4+ sub-flows with non-obvious ordering
- Multiple valid decomposition strategies exist with different trade-offs
- The task is ambiguous enough that the "right" decomposition is unclear

---

## Fallback

Fallbacks may (rarely) occur during policy execution when there are hard-coded fallbacks. The process is:

1. A new flow is created for the fallback target
2. **Best-effort slot mapping** transfers slot values where slot names match between the old and new flow; unmatched slots are discarded
3. Flow metadata is transferred to the new flow
4. The previous flow is marked as **Invalid** and popped
5. The new flow is pushed on top of the stack

## Failure Recovery

Failure recovery is owned by the Agent, not the flow stack itself. When a flow encounters a failure, the following process applies:

1. **Policy recovery** — The policy in PEX first tries flow-specific recovery (retry, alternative tool call, etc.)
2. **Declare ambiguity** — If recovery fails, the policy declares an ambiguity at the relevant level via the ambiguity handler
3. **Agent decides** — The Agent inspects the ambiguity and chooses one of:
   - **Re-route**: Send to NLU `contemplate` to re-detect and find a fallback flow
   - **Skip**: Skip the failed step and continue to the next flow in the plan (sets `keep_going`)
4. **Resolution** — If either method succeeds, the ambiguity is resolved
5. **Escalate** — If neither works, or if the Agent decides there is no recourse (often when the ambiguity level is `general`), go straight to RES to ask the user for clarification
