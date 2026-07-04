# Workflow Planner

Two things share this spec: the **FlowStack** data structure that stores the flows (code: `flow_stack.py`),
and **Workflow Planning** (equivalently, **Sub-agent Routing**) — the activity [PEX](../modules/pex.md)'s LLM
performs over it. PEX plans: it decides which sub-agents to run, handles fallbacks and stack-ons, and tracks
how far through a complex request the agent is. Its **primary input is NLU's classified intent and detected
flow** (`classify_intent` / `detect_flow`) — the planner routes from that belief, not the raw utterance. The flows it plans across are stored in the FlowStack, whose
contents are serialized in the Dialogue State document's `flow_stack` block — the one block the Workflow
Planner owns and writes (`stackon` / `fallback` / `pop_completed`), distinct from the belief blocks NLU's
Dialogue State tools manage.

The stack admits **multiple active flows running in parallel** (bounded — see
[Data Structure](#data-structure)), so independent branches advance together while the stack discipline
prevents unbounded branching.

## Naming Map — A2A Alignment

For interop with the [A2A protocol](https://a2a-protocol.org/latest/specification/), the runtime vocabulary maps as follows. Our terms are kept because they're established in this codebase; the right column is the A2A equivalent so external readers can translate.

| Our term | A2A term | Notes |
|---|---|---|
| **flow** ↔ **policy** ↔ **task** | task | All three refer to the same thing: the work the sub-agent does. *Flow* is the declarative spec (slots, tools, parents); *policy* is the Python code executing it; *task* is A2A's framing of the unit of work. Use whichever fits the layer being discussed. |
| **artifact** (was: frame) | artifact | The structured output a policy hands to PEX for the turn. Class: `TaskArtifact` (renamed from `DisplayFrame`). |
| **parts** (was: metadata) | parts | The A2A v1.0 parts array on the artifact: `list[Part]`, each Part holding exactly one of `text` / `raw` / `url` / `data` (+ optional `metadata` extension). The classification dict lives inside the first `data` Part; agent reasoning lives inside a `text` Part tagged `metadata.kind='thoughts'`. Helper properties on `TaskArtifact` (`.data`, `.thoughts`, `.code`) unpack from this list for ergonomic reads. |
| **block** | (no direct A2A term) | Visual UI building block carried in `artifact.blocks` (cards, lists, selections, confirmations). We keep "block" — A2A's *Part* is a content container (text / raw / url / data) that maps to our `parts` field, not to our visual UI units. |

## What is a Flow?

- Flows hold the slots, metadata, and other information about the action to take
  - Also known as "workflows" in extended form
  - Historic name: "dialog acts"; modern name: sometimes called "sub-agents"
  - In A2A vocabulary: each flow is a **task** that the agent runs
- The **policy** is the code that actually executes the action
  - Implemented as a Skill (https://agentskills.io/what-are-skills) with access to tools (https://www.anthropic.com/engineering/writing-tools-for-agents)
  - Sometimes a tool is actually just a call to an MCP server
  - *Flow / policy / task* are interchangeable when discussing "the sub-agent's work" — see naming map above

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

There is no separate `FlowEntry` wrapper. **BaseFlow IS the entry** — each flow instance carries both its domain definition (slots, tools, intent) and its runtime state (flow_id, status, turn_ids, result). When a flow is pushed onto the stack, the FlowStack instantiates the flow class directly and sets the runtime fields.

Runtime state fields on every BaseFlow instance:
- `flow_id` — unique 8-char identifier, set by FlowStack on push
- `status` — lifecycle state (active, pending, completed, invalid)
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
| `to_dict()` | Full flow serialization including runtime state (flow_id, status, slots, turn_ids, result) |
| `get(key, default)` | Attribute access helper — reads from flow attributes with a default fallback |
| `name(full=False)` | Flow name helper — returns `flow_type` by default, or fully qualified name with intent prefix when `full=True` |
| `serialize()` | Serialize the flow for persistence |

These methods are distinct from the lifecycle states below — they describe *how* a flow prepares for execution, while lifecycle states describe *where* a flow is in the stack.

### Slot Filling

Two methods fill slots, distinguished by **prompt scope** and **when they run**:

**`fill_slot_values(values: dict)`** — Bulk fill from a full-flow prediction.

The upstream prompt sees the entire flow (all slots, descriptions, types) and produces a dict of `{slot_name: value}` pairs for every slot it can extract. The method then routes each value to the correct slot object based on type:

- Lists → `slot.add_one()` per item (for GroupSlot variants)
- Dicts → `slot.add_one(**value)` (for entity dicts, key-value pairs)
- Scalars → `slot.assign_one(value)` or `slot.value = str(value)`

Also resolves **aliases** (e.g., the LLM says `'post'` but the slot is named `'source'`). Does not return a value. Used primarily by **NLU** — after `think()`, `contemplate()`, and `react()` predict a flow, the extracted slots dict is passed here for bulk transfer.

**`fill_slots_by_label(labels: dict)`** — Targeted fill for a specific slot.

The upstream prompt is shorter and more focused: it knows exactly which slot it needs to fill (e.g., "Extract the topic the user wants to outline") and produces a single `{slot_name: value}` pair. The method routes entity-slot values through `extract_entity()` — the entity-extraction hook that domain parent flows can override for early validation (e.g., checking that a post exists before filling the source slot). Non-entity slots delegate to `fill_slot_values` for the actual storage. Returns `is_filled()` status.

Used primarily by **policies in PEX** — when a policy knows a specific slot is missing, it runs a targeted extraction prompt and fills just that slot:

```python
# In a policy: targeted extraction of a single slot
text = self.engineer.call(history, system="Extract the topic the user wants to outline.")
flow.fill_slots_by_label({'topic': parsed_value})
if not flow.slots['topic'].filled:
    self.ambiguity.declare('specific', metadata={'missing': 'topic'})
```

**Summary of the distinction:**

| | `fill_slot_values` | `fill_slots_by_label` |
|---|---|---|
| **Prompt scope** | Full flow — all slots at once | Single slot — focused extraction |
| **Primary caller** | NLU (after flow detection) | Policies in PEX (during execution) |
| **Entity handling** | Direct to slot | Via `extract_entity()` hook |
| **Alias resolution** | Yes | No |
| **Returns** | Nothing | `is_filled()` boolean |

### Entity Extraction (sub-task of slot filling)

Industry NLU draws a line between **entity extraction** (identifying which entity the user is referring to — e.g. "this post", "the second section") and **slot filling** (writing a value into a structured variable). Hugo follows this distinction:

| Layer | Action verb | Subject |
|---|---|---|
| NLU | classifies | intent |
| NLU | detects | flow |
| NLU | extracts | entity (`entities are extracted`) |
| NLU | fills | slot (`slots are filled`) |

**Entity extraction** is a sub-task of slot filling, focused on grounding:

- In **NLU**, the `_extract_entities(flow, entity_dict)` helper (called from `_fill_slots`) routes entity payload values (`post`, `sec`, `snip`, `chl`) into the flow's grounding slots — its `SourceSlot` / `TargetSlot` / `RemovalSlot`, or into the `query` / `word` `ExactSlot` for snippet-scoped flows like `find` and `reference`.
- In **flows**, the `BaseFlow.extract_entity(entity)` hook is what `fill_slots_by_label` invokes when the slot being filled is the flow's `entity_slot`. Domain parents may override `extract_entity` to add validation (e.g. confirming the post exists before committing).

**Failure mapping:**
- `partial` ambiguity = entity extraction failed (the entity the user was referring to could not be resolved). The flow's `entity_slot` is still unfilled after extraction attempts.
- `specific` ambiguity = slot filling failed for some other (non-entity) slot.

Both share the same runtime contract — `parts={'missing': <slot_name>, 'entity': <entity_type>?, 'reason': <code>?}` — so consumers reading an artifact's `parts` have a uniform "what was missing?" key regardless of which sub-task failed.

The canonical entity slot name is `'source'` (matching `BaseFlow.entity_slot`); the slot type is `SourceSlot` (or a `SourceSlot`-derived class like `TargetSlot` / `RemovalSlot`).

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

- **required** — must be filled before execution. Missing → `specific` ambiguity with `metadata={'missing': '<slot_name>'}`.
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

A **stack** holds the flows. Three operations drive it:

- When issues get complicated, we **stack on** new flows.
- When flows are completed, they get **popped off**.
- When a flow is incorrectly detected, we may **fall back** to other flows.

**Stack Depth**: there is a hard limit of **16 flows** on the stack. If the work needs more than that, the
planner does **not** branch unboundedly — it writes a note in the [Session Scratchpad](./session_scratchpad.md)
to revisit once some existing flows complete, then proceeds within the bound.

**Multiple active flows**: more than one flow can be **Active** at once, but **all Active flows must be
contiguous** at the top of the stack, with **Pending** flows strictly beneath them. The structure forbids a
Pending flow wedged among Actives, and forbids an Active (or Completed) flow buried among Pendings. This forces
the agent to start the Pending flows (or mark them Completed) before it can deal with anything beneath — which
is exactly what keeps branching bounded.

```
top → [ Active, Active, Active, Pending, Pending ]  ← legal
top → [ Active, Pending, Active, Pending ]           ← illegal (Pending wedged among Actives)
```

## Flow Lifecycle

Each flow on the stack is in exactly one of four states:

| State | Description |
|-------|-------------|
| **Pending** | Stacked but not yet active — waiting its turn (e.g., queued in a plan). |
| **Active** | Top of the stack; currently being executed by the policy. |
| **Completed** | Successfully finished; will be popped by the Workflow Planner (`pop_completed`). |
| **Invalid** | Incorrectly detected or encountered a hard failure; will be popped during fallback. |

## Concurrency Model

The contiguous block of Active flows runs concurrently as **asyncio tasks**. Flows can carry lightweight
dependency annotations (e.g., "flow B depends on flow A") so PEX parallelizes independent work while preserving
ordering for dependent ones. (There are no "Internal" flows — memory operations are MEM skills
[`recap`/`recall`/`retrieve`](../modules/mem.md), and purely deterministic operations are plain tools.)

The **Dialogue State** is not at risk here — it is written only by NLU's belief tools and never corrupted by
merge collisions. The surface that has to worry about **race conditions** is the
[Session Scratchpad](./session_scratchpad.md), into which parallel sub-agents append concurrently. That tension
is resolved by [NLU](../modules/nlu.md): NLU is triggered to review the scratchpad whenever it is updated, and
keeps it smooth and uncorrupted.

## Plan Lifecycle

A Plan is decomposed and sequenced by the Workflow Planner **itself** — there is **no separate Plan policy
sub-agent, and no Plan flow object on the stack**. Decomposition is a single prompted step (the `plan` skill);
execution is the ordinary flow stack; **the PEX orchestrator judges when the plan has met the user's goal**.

### The Workflow Planner skill
The **Plan** intent is served by the **Workflow Planner skill** (`backend/prompts/pex/skills/plan.md`). Like
every module skill it **returns nothing** — it is how-to guidance injected into the orchestrator's context, not
a flow policy and not a returning call. Following it, PEX issues the stack ops itself. Sketch:
- **Input** — NLU's detected intent/flow(s) (the orchestrator routes from belief, not raw text), the flow
  catalog (flows by intent), current grounding, and recent context.
- **What it tells PEX to do** — map each sub-task to an **existing** flow (never invent one), order by
  dependency, keep it minimal, then `stackon` the sub-flows in that order and share a one-line plan.
- **Result** — PEX emits the `stackon` calls in its loop plus a short plan for the user; the decomposition is
  PEX's reasoning + tool calls, not a value the skill returns.

### Execution
On approval the Planner stacks the sub-flows in order with `stackon` and runs them through the ordinary flow
lifecycle (Active → Completed → `pop_completed`). Each completed flow appends its completion record
`{flow, summary, metadata}` to the [Session Scratchpad](./session_scratchpad.md), so a later sub-flow can read
what an earlier one produced. Mid-plan, PEX keeps going across the sub-flows on the same turn — a Plan is the
sanctioned chaining path; a lone flow stacked outside a plan exits for user review instead.

### Goal completion — owned by PEX
There is **no completion-assessment flow** and **no automatic "all sub-flows popped ⇒ done" rule**: the PEX
orchestrator decides whether the user's goal has been met. After each sub-flow completes, PEX judges whether
the goal is satisfied — if not, it stages and runs the next flow (or stacks a new one the work revealed); if
so, it concludes and reports what was accomplished. This is the same judgment PEX makes on any multi-step
turn, stated here for plans; it is a prompted decision, never automatic.

---

## Transitions

Three transition channels, each with different UX. Inside an active Plan, PEX continues to the next flow on the same turn; outside a Plan, a sub-flow pushed by stack-on exits for user review. **`keep_going` is PEX's loop-control behavior**, *not* a stored state flag: each round PEX emits tool calls and/or a user-facing message and loops again until it chooses to stop. Continuation is just running another round — e.g., `activate_flow` to run the next flow, a stack op (`stackon` / `fallback` / `pop_completed`), a consult, or a progress message. (`complete_flow` is the flow's own policy marking itself done — not a planner op.) Whether to continue or exit for review is PEX's call, read from the agenda (are we mid-Plan?).

### Activate Flow (pending → active)

`activate_flow` turns a **pending** flow into an **active** one and runs its policy as a sub-agent. Two rules:

- **Top-of-stack only.** Only the flow(s) at the **top** of the stack can be activated — Active stays
  contiguous at the top, Pending strictly beneath.
- **Same type to batch.** Multiple flows activate **together only when they share a flow type** (so their N
  artifacts curate trivially into one). Different-type flows activate **one at a time**, top first.

### Stack On (prerequisite setup)

The current flow needs another flow's output before it can run. Push the prerequisite, resume after.

```python
self.flow_stack.stackon('<prereq_flow>')
artifact = TaskArtifact(flow.name(), thoughts='<reason — surfaces to user via PEX>')
```

### Fallback (re-route to sibling)

The user's intent maps to a different flow than NLU detected. Pop current, push sibling.

```python
self.flow_stack.fallback('<sibling_flow>')
artifact = TaskArtifact(flow.name(), thoughts='<why we re-routed>')
```

The fallback process: a new flow is created for the target; best-effort slot mapping transfers slot values where names match (unmatched slots are discarded); flow metadata transfers; the previous flow is marked Invalid and popped; the new flow is pushed on top.

Use only when the intent belongs elsewhere — never for skill errors (use error artifacts) or tool failures (use error artifacts).

### Yield-When-Stacked (Converse on top of an active flow)

When a Converse intent (`endorse`, `dismiss`) pushes onto an already-active flow during a confirmation resolution turn, the **single Converse sub-agent** (one `converse` policy serves all Converse flows, not a per-flow policy) should **yield** rather than respond with its own chit-chat skill output. The underlying flow's resolution turn consumes the user's accept/decline.

```python
def endorse_policy(self, flow, state, context, tools):
    if self.flow_stack.stack_size() > 1:
        flow.status = 'Completed'
        # Optional scratchpad note so the resumed flow knows the user accepted.
        self.memory.write_scratchpad(flow.name(), {'accepted': True})
        return TaskArtifact(flow.name())  # empty yield-artifact
    # ...fall through to the normal chit-chat path
```

Without yielding, the user's "yes" gets answered by Converse with a generic acknowledgement, the underlying flow stays paused, and the originally-promised work never lands. Applies to `endorse` and `dismiss` — the flows that consume explicit accept/decline. Other Converse flows (`chat`, `suggest`, `explain`, `preference`, `undo`) don't carry an accept/decline contract and should not yield.

PEX `_validate_artifact` allows empty artifacts on a yielding turn — the empty artifact here is intentional, not a bug for the retry mechanism to chase.

## Worked Examples — Flow-Stack Scenarios

Four exemplars of stack management in concert. Stacks are shown **bottom → top**; the **top** is the next flow
to run. `complete_flow` is the flow's own policy marking itself done (not a planner op); `pop_completed` then
removes it.

**1 — Single flow (baseline lifecycle).** *"Outline a post on tide-pool ecology."* → intent **Draft**, flow `outline`.

| Op | Stack after |
|---|---|
| `stackon(outline)` | `[outline·pending]` |
| `activate_flow(outline)` | `[outline·active]` — sub-agent runs |
| policy `complete_flow` (grounded) | `[outline·completed]` |
| `pop_completed` | `[]` → **TaskArtifact delivered** |

**2 — Prerequisite stack-on (yield → run prereq → re-activate from scratch).** *"Publish it to Substack."* — but
the post isn't drafted → flow `publish`.

| Op | Stack after |
|---|---|
| `stackon(publish)` | `[publish·pending]` |
| `activate_flow(publish)` → finds no draft, `stackon(draft)`, **yields** (no L4) | `[publish·pending, draft·pending]` |
| `activate_flow(draft)` → drafts, writes scratchpad, `complete_flow` | `[publish·pending, draft·completed]` |
| `pop_completed` | `[publish·pending]` |
| `activate_flow(publish)` → **re-activated from scratch**, reads draft from scratchpad, publishes, `complete_flow` → `pop_completed` | `[]` → **delivered** |

`publish` reverts to pending while its prerequisite owns the top; on return it runs fresh, picking up state from
the scratchpad.

**3 — Multiple ACTIVE flows, same type (parallel batch).** *"Draft the intro, methods, and results sections."* →
three `draft` flows, different targets.

| Op | Stack after |
|---|---|
| `stackon` ×3 | `[draft·intro·pending, draft·methods·pending, draft·results·pending]` |
| `activate_flow(...)` — **same type ⇒ batch together** | `[…·active, …·active, …·active]` — 3 sub-agents in parallel |
| each policy `complete_flow`; `pop_completed` ×3 | `[]` |

PEX curates the **3 same-type artifacts into one** (origin trivially `draft`). This is the case the same-type
activation rule exists for.

**4 — A Plan of DIFFERENT-type flows (sequential, top-only).** *"Research the topic, draft a post, then publish
it."* → Plan, 3 different-type sub-flows run in order.

| Op | Stack after |
|---|---|
| `stackon(publish)`, `stackon(draft)`, `stackon(research)` | `[publish·pending, draft·pending, research·pending]` |
| `activate_flow(research)` — top only, **can't batch (different types)** → complete → pop | `[publish·pending, draft·pending]` |
| `activate_flow(draft)` → complete → pop | `[publish·pending]` |
| `activate_flow(publish)` → complete → pop | `[]` → **delivered** |

Mid-Plan PEX keeps going across all three on one turn (Plan = the sanctioned chaining path). The contrast with
example 3 pins down both `activate_flow` rules: **same type → activate together; different types → one at a
time, top first.**

## Failure Recovery

Failure recovery is owned by [PEX](../modules/pex.md), not the Workflow Planner itself. The flow of recovery:

1. **Policy classifies the failure** — tool-call failure → error artifact with `parts={'violation': 'tool_error', ...}`; ambiguous user intent → `ambiguity.declare(level, observation=, metadata=)` (note: `declare()`'s `metadata=` parameter stays — it's the ambiguity component's input, not the artifact attribute); malformed skill output → error artifact with `parts={'violation': 'parse_failure'}`.
2. **PEX decides** based on what was returned:
   - Tool error and transient → retry once via `BasePolicy.retry_tool(tools, name, params, max_attempts=2)`.
   - Ambiguity that may indicate the wrong flow → `NLU.contemplate()` to re-route; mark current flow Invalid; best-effort slot mapping to the new flow.
   - Otherwise → PEX surfaces the clarification so the user can answer.

Tool failures are infrastructure, not user-facing questions — never declare ambiguity for them. Ambiguity is the only channel that produces a clarification question. Conflating the two channels hides root cause.
