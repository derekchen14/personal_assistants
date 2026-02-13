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

## Data Structure

The data structure is a **stack** (not a dict or list or queue) to ensure we only ever have one "active" flow:

- When issues get complicated, we **stack on** new flows
- When flows are completed, they get **popped off**
- When a flow is incorrectly predicted, we may **fall back** to other flows

**Stack Depth**: There is no explicit stack depth limit. The 64-flow-per-domain cap in dialogue_state is an ontology limit (how many flow *types* exist in a domain), not a stack limit. In practice, stacks are shallow (2–5 flows).

## Flow Lifecycle

Each flow on the stack is in exactly one of four states:

| State | Description |
|-------|-------------|
| **Pending** | Stacked but not yet active — waiting its turn (e.g., queued in a plan). |
| **Active** | Top of the stack; currently being executed by the policy. |
| **Completed** | Successfully finished; will be popped during the RES pre-hook. |
| **Invalid** | Incorrectly predicted or encountered a hard failure; will be popped during fallback. |

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
   - **Re-route**: Send to NLU `contemplate` to re-predict and find a fallback flow
   - **Skip**: Skip the failed step and continue to the next flow in the plan (sets `keep_going`)
4. **Resolution** — If either method succeeds, the ambiguity is resolved
5. **Escalate** — If neither works, or if the Agent decides there is no recourse (often when the ambiguity level is `general`), go straight to RES to ask the user for clarification
