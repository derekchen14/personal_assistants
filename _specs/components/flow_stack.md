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

### BaseFlow as the Stack Entry

There is no separate `FlowEntry` wrapper. **BaseFlow IS the entry** — each flow instance carries both its domain definition (slots, tools, intent) and its runtime state (flow_id, status, plan_id, turn_ids, result). When a flow is pushed onto the stack, the FlowStack instantiates the flow class directly and sets the runtime fields.

Runtime state fields on every BaseFlow instance:
- `flow_id` — unique 8-char identifier, set by FlowStack on push
- `status` — lifecycle state (active, pending, completed, invalid)
- `plan_id` — which plan this flow belongs to (if any)
- `turn_ids` — conversation turns associated with this flow
- `result` — execution result dict, set on completion

### Flow Methods

Every flow inherits these methods from `BaseFlow`:

| Method | Purpose |
|---|---|
| `fill_slot_values(values)` | Bulk slot fill from a predictions dict — see Slot Filling below |
| `fill_slots_by_label(labels)` | Targeted single-slot fill with entity validation — see Slot Filling below |
| `slot_values_dict()` | Read all filled slot values as a flat `{name: value}` dict |
| `is_filled()` | Check if all required slots and at least one elective (if any) are filled |
| `needs_to_think()` | Determine if further contemplation is needed before execution |
| `to_dict()` | Full flow serialization including runtime state (flow_id, status, slots, plan_id, turn_ids, result) |
| `get(key, default)` | Attribute access helper — reads from flow attributes with a default fallback |
| `name(full=False)` | Flow name helper — returns `flow_type` by default, or fully qualified name with intent prefix when `full=True` |
| `serialize()` | Serialize the flow for persistence |

These methods are distinct from the lifecycle states below — they describe *how* a flow prepares for execution, while lifecycle states describe *where* a flow is in the stack.

### Slot Filling

Two methods fill slots, distinguished by **prompt scope** and **when they run**:

**`fill_slot_values(values: dict)`** — Bulk fill from a full-flow prediction.

The upstream prompt sees the entire flow (all slots, descriptions, types) and produces a dict of `{slot_name: value}` pairs for every slot it can extract. The method then dispatches each value to the correct slot object based on type:

- Lists → `slot.add_one()` per item (for GroupSlot variants)
- Dicts → `slot.add_one(**value)` (for entity dicts, key-value pairs)
- Scalars → `slot.assign_one(value)` or `slot.value = str(value)`

Also resolves **aliases** (e.g., the LLM says `'post'` but the slot is named `'source'`). Does not return a value. Used primarily by **NLU** — after `think()`, `contemplate()`, and `react()` predict a flow, the extracted slots dict is passed here for bulk transfer.

**`fill_slots_by_label(labels: dict)`** — Targeted fill for a specific slot.

The upstream prompt is shorter and more focused: it knows exactly which slot it needs to fill (e.g., "Extract the topic the user wants to outline") and produces a single `{slot_name: value}` pair. The method routes entity-slot values through `validate_entity()` — a hook that domain parent flows can override for early validation (e.g., checking that a post exists before filling the source slot). Non-entity slots delegate to `fill_slot_values` for the actual storage. Returns `is_filled()` status.

Used primarily by **policies in PEX** — when a policy knows a specific slot is missing, it runs a targeted extraction prompt and fills just that slot:

```python
# In a policy: targeted extraction of a single slot
text = self.engineer.call(history, system="Extract the topic the user wants to outline.")
flow.fill_slots_by_label({'topic': parsed_value})
if not flow.slots['topic'].filled:
    self.ambiguity.declare('specific', metadata={'missing_slot': 'topic'})
```

**Summary of the distinction:**

| | `fill_slot_values` | `fill_slots_by_label` |
|---|---|---|
| **Prompt scope** | Full flow — all slots at once | Single slot — focused extraction |
| **Primary caller** | NLU (after flow detection) | Policies in PEX (during execution) |
| **Entity handling** | Direct to slot | Via `validate_entity()` hook |
| **Alias resolution** | Yes | No |
| **Returns** | Nothing | `is_filled()` boolean |

### Flow Registration: `flow_classes` Dict

Flows are registered via a `flow_classes` dict that maps **flow names** (not DAX codes) to **flow classes** (not instances). The FlowStack receives this dict at construction and uses it to instantiate flows on push.

```python
# In flow_stack/__init__.py
from backend.components.flow_stack.flows import *

flow_classes: dict[str, type] = {
    'query': QueryFlow,
    'chat': ChatFlow,
    'browse': BrowseFlow,
}

# In world.py
from backend.components.flow_stack import FlowStack, flow_classes
self.flow_stack = FlowStack(config, flow_classes=flow_classes)
```

The FlowStack's `push(flow_name)` method looks up the class by name, instantiates it, and sets runtime state fields. Slots are NOT filled during push — NLU fills them separately.

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
BaseSlot                  # abstract base — never instantiated directly
├── GroupSlot             # holds a list of items
│   ├── SourceSlot        # references existing entities (grounding)
│   │   ├── TargetSlot    # new entities being created
│   │   └── RemovalSlot   # entities being removed
│   ├── FreeTextSlot      # free-form text or operations
│   ├── ChecklistSlot     # ordered steps to check off
│   └── ProposalSlot      # candidate options for confirmation
├── LevelSlot             # single numeric value with range constraints
│   ├── PositionSlot      # non-negative integer position
│   ├── ProbabilitySlot   # 0–1 range [domain-specific, common option]
│   └── ScoreSlot         # any numeric value [domain-specific, common option]
├── CategorySlot          # exactly one from a predefined set (≤8, mutually exclusive)
├── ExactSlot             # specific token or phrase
├── DictionarySlot        # key-value pairs
└── RangeSlot             # start/stop interval (often date range)
```

`BaseSlot` is the shared abstract parent — it is never used directly. Concrete single-value behavior lives on the specific subclasses (`ExactSlot`, `CategorySlot`, `LevelSlot` and its descendants).

#### Grounding Slots

**SourceSlot** references existing entities. Each entity is a dict whose fields are domain-specific, matching the domain's `KEY_ENTITIES`. The hierarchy is built into a single slot.

Each domain defines its own grounding entity vocabulary:

| Domain | Entity fields |
|--------|---------------|
| Dana (Data Analysis) | `{tab, col, row, ver, rel}` — tab=table, col=column, row=row |
| Hugo (Blog Writing) | `{post, sec, snip, chl, ver}` — post=post, sec=section, snip=snippet, chl=channel |

`ver` is a **verified bool**, not a version int — it flags whether the entity was user-approved vs. agent-predicted. NLU does not predict `ver`; it is set by the grounding layer.

**Canonical name.** A flow's grounding slot is always named `'source'` (matching `BaseFlow.entity_slot`). One SourceSlot per flow — do not split entity parts into separate slots. Not every flow requires a grounding slot (e.g., `chat`, `brainstorm`).

**`entity_part` is optional.** `SourceSlot(min_size=1, entity_part='', priority='required')` accepts any entity type. Setting `entity_part='post'` constrains the slot to that single field.

When a flow needs both a SourceSlot and a FreeTextSlot, name the FreeText something other than `'source'` (e.g., `'context'`).

**TargetSlot → SourceSlot**: Entities being created (new columns, new rows, new posts).

**RemovalSlot → SourceSlot**: Entities being deleted or removed.

#### Domain-Specific Slots (4 per domain)

Each domain selects 4 additional slot types. Two are typically common options (`ProbabilitySlot`, `ScoreSlot`) that most domains include; the remaining two are truly unique to the domain. All are real `BaseSlot` subclasses.

| Domain | Common options | Domain-unique |
|--------|---------------|---------------|
| Dana | ProbabilitySlot, ScoreSlot | **ChartSlot** (chart reference), **FunctionSlot** (executable code) |
| Hugo | ProbabilitySlot, ScoreSlot | **ChannelSlot** (publishing destination), **ImageSlot** (hero image, diagram) |

This 12+4 pattern is the scalable architecture for adding new domains. When creating a new assistant:
1. Copy the 12 universal slot classes from any existing domain's `slots.py`.
2. Select common options (ProbabilitySlot, ScoreSlot) if the domain needs them.
3. Define domain-unique slot types as `BaseSlot` subclasses (total domain-specific = 4).
4. Define the domain's grounding entity vocabulary.

### Slot Priority

A slot's priority is one of: `required`, `optional`, `elective`.

- **required** — must be filled before execution. Missing → `specific` ambiguity with `metadata={'missing_slot': '<name>'}`.
- **elective** — at least one of N elective slots must be filled (choice among alternatives). A flow with elective slots must have ≥2 elective options — single-elective is invalid (convert to required or optional).
- **optional** — nice-to-have. With a defensible default, commit it inline at policy entry. Without, treat absence as OK.

`flow.is_filled()` already encodes "all required filled AND ≥1 elective filled (if any)." Trust it; don't re-derive.

### CategorySlot Constraints

A CategorySlot's options list must be:
- **Mutually exclusive** — selecting one option rules out all others.
- **At most 8 options** — if you need more than 8, the taxonomy is too fine-grained; consider grouping or using FreeTextSlot instead.

### ExactSlot as Category Extension

When a CategorySlot covers the common cases but users may need values beyond the predefined set, pair it with an ExactSlot as electives. The user fills either the category (pick from the list) or the exact slot (provide a custom value):

```python
self.slots = {
    'custom_tone': ExactSlot(priority='elective'),
    'chosen_tone': CategorySlot(['formal', 'casual', 'technical', ...], priority='elective'),
}
```

This preserves structured options for NLU prediction while allowing open-ended input when needed.

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

## Transitions

Three transition channels, each with different UX. Always set `state.keep_going = True` when chaining so PEX continues to the next flow on the same turn — but **`keep_going` is only valid inside an active Plan**. Outside a Plan, sub-flows pushed by stack-on exit for user review.

### Stack On (prerequisite setup)

The current flow needs another flow's output before it can run. Push the prerequisite, resume after.

```python
self.flow_stack.stackon('<prereq_flow>')
state.keep_going = True
frame = DisplayFrame(flow.name(), thoughts='<reason — surfaces to user via RES>')
```

### Fallback (re-route to sibling)

The user's intent maps to a different flow than NLU detected. Pop current, push sibling.

```python
self.flow_stack.fallback('<sibling_flow>')
state.keep_going = True
frame = DisplayFrame(flow.name(), thoughts='<why we re-routed>')
```

The fallback process: a new flow is created for the target; best-effort slot mapping transfers slot values where names match (unmatched slots are discarded); flow metadata transfers; the previous flow is marked Invalid and popped; the new flow is pushed on top.

Use only when the intent genuinely belongs elsewhere — never for skill errors (use error frames) or tool failures (use error frames).

### Yield-When-Stacked (Converse on top of an active flow)

When a Converse intent (`endorse`, `dismiss`) pushes onto an already-active flow during a confirmation resolution turn, the Converse policy should **yield** rather than respond with its own chit-chat skill output. The underlying flow's resolution turn consumes the user's accept/decline.

```python
def endorse_policy(self, flow, state, context, tools):
    if self.flow_stack.stack_size() > 1:
        flow.status = 'Completed'
        state.keep_going = True
        # Optional scratchpad note so the resumed flow knows the user accepted.
        self.memory.write_scratchpad(flow.name(), {'accepted': True})
        return DisplayFrame(flow.name())  # empty yield-frame
    # ...fall through to the normal chit-chat path
```

Without yielding, the user's "yes" gets answered by Converse with a generic acknowledgement, the underlying flow stays paused, and the originally-promised work never lands. Applies to `endorse` and `dismiss` — the flows that consume explicit accept/decline. Other Converse flows (`chat`, `suggest`, `explain`, `preference`, `undo`) don't carry an accept/decline contract and should not yield.

PEX `_validate_frame` allows empty frames when `keep_going=True` — the empty frame here is intentional, not a bug for the retry mechanism to chase.

## Failure Recovery

Failure recovery is owned by the Agent, not the flow stack itself. The flow of recovery:

1. **Policy classifies the failure** — tool-call failure → error frame with `metadata={'violation': 'tool_error', ...}`; ambiguous user intent → `ambiguity.declare(level, observation=, metadata=)`; malformed skill output → error frame with `metadata={'violation': 'parse_failure'}`.
2. **Agent decides** based on what was returned:
   - Tool error and transient → retry once via `BasePolicy.retry_tool(tools, name, params, max_attempts=2)`.
   - Ambiguity that may indicate the wrong flow → `NLU.contemplate()` to re-route; mark current flow Invalid; best-effort slot mapping to the new flow.
   - Otherwise → escalate to RES so the user can clarify.

Tool failures are infrastructure, not user-facing questions — never declare ambiguity for them. Ambiguity is the only channel that produces a clarification question. Conflating the two channels hides root cause.
