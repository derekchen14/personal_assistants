# Workflow Planner

Two things share this spec: the **FlowStack** data structure that stores the flows (code: `flow_stack.py`),
and **Workflow Planning** (equivalently, **Sub-agent Routing**) — the activity [PEX](../modules/pex.md)'s LLM
performs over it. PEX plans: it decides which sub-agents to run, handles fallbacks and stack-ons, and tracks
how far through a complex request the agent is. Its **primary input is NLU's detected flow** (the flow fixes
the intent — see [Dialogue State § Predicting the Belief State](./dialogue_state.md#predicting-the-belief-state))
— the planner routes from that belief, not the raw utterance. The flows it plans across are stored in the
FlowStack, whose contents are serialized in the Dialogue State document's `flow_stack` block — the one block
the Workflow Planner owns and writes via the `manage_flows(op)` tool (`update` / `stackon` / `fallback` /
`activate` / `pop`; replaces the old `write_state` + `activate_flow` pair), distinct from the belief NLU
maintains.

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
| `fill_slot_values(values)` | Bulk slot fill from a predictions dict — see [Dialogue State § Slot-Filling Methods](./dialogue_state.md#slot-filling-methods) |
| `fill_slots_by_label(labels)` | Targeted single-slot fill with entity validation — same reference |
| `slot_values_dict()` | Read all filled slot values as a flat `{name: value}` dict |
| `is_filled()` | Check if all required slots and at least one elective (if any) are filled |
| `needs_to_think()` | Determine if further contemplation is needed before execution |
| `to_dict()` | Full flow serialization including runtime state (flow_id, status, slots, turn_ids, result) |
| `get(key, default)` | Attribute access helper — reads from flow attributes with a default fallback |
| `name(full=False)` | Flow name helper — returns `flow_type` by default, or fully qualified name with intent prefix when `full=True` |
| `serialize()` | Serialize the flow for persistence |

These methods are distinct from the lifecycle states below — they describe *how* a flow prepares for execution, while lifecycle states describe *where* a flow is in the stack.

### Slot Filling and Entity Extraction

Moved to [Dialogue State](./dialogue_state.md) — the canonical home for everything slot-related:
priorities, the 12+4 type hierarchy, grounding slots, the two filling methods (`fill_slot_values` /
`fill_slots_by_label`), and entity extraction with its ambiguity failure mapping.

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

Slot types, priorities, and grounding rules live in
[Dialogue State § Slot-Filling](./dialogue_state.md#slot-filling).

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
| **Completed** | Successfully finished; will be popped by the Workflow Planner (`pop`). |
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
  ontology (flows by intent), current grounding, and recent context.
- **What it tells PEX to do** — map each sub-task to an **existing** flow (never invent one), order by
  dependency, keep it minimal, then `stackon` the sub-flows in that order and share a one-line plan.
- **Result** — PEX emits the `stackon` calls in its loop plus a short plan for the user; the decomposition is
  PEX's reasoning + tool calls, not a value the skill returns.

### Execution
On approval the Planner stacks the sub-flows in order with `stackon` and runs them through the ordinary flow
lifecycle (Active → Completed → `pop`). Each completed flow appends its completion record
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

Three transition channels, each with different UX. Inside an active Plan, PEX continues to the next flow on the same turn; outside a Plan, a sub-flow pushed by stack-on exits for user review. **`keep_going` is PEX's loop-control behavior**, *not* a stored state flag: each round PEX emits tool calls and/or a user-facing message and loops again until it chooses to stop. Continuation is just running another round — e.g., `activate` to run the next flow, a stack op (`stackon` / `fallback` / `pop`), a consult, or a progress message. (`complete_flow` is the flow's own policy marking itself done — not a planner op.) Whether to continue or exit for review is PEX's call, read from the agenda (are we mid-Plan?).

### Activate Flow (pending → active)

`activate` turns a **pending** flow into an **active** one and runs its policy as a sub-agent. Two rules:

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

### Confirmation turns

When a flow is awaiting the user's accept/decline, the answer belongs to that flow's resolution turn:
the active flow stays on the stack, the user's yes/no arrives as an utterance or button payload, and
PEX resolves it on the active flow. `endorse` / `dismiss` are **tools** PEX may call to record the
outcome — never a second flow stacked on top, so nothing competes with the active flow for the turn.
(Historical: when endorse/dismiss were Converse flows, they had to yield to the flow beneath them; the
flow audit converted them to tools and removed that case.)

## Worked Examples — Flow-Stack Scenarios

Four exemplars of stack management in concert. Stacks are shown **bottom → top**; the **top** is the next flow
to run. `complete_flow` is the flow's own policy marking itself done (not a planner op); `pop` then
removes it.

**1 — Single flow (baseline lifecycle).** *"Outline a post on tide-pool ecology."* → intent **Draft**, flow `outline`.

| Op | Stack after |
|---|---|
| `stackon(outline)` | `[outline·pending]` |
| `activate(outline)` | `[outline·active]` — sub-agent runs |
| policy `complete_flow` (grounded) | `[outline·completed]` |
| `pop` | `[]` → **TaskArtifact delivered** |

**2 — Prerequisite stack-on (yield → run prereq → re-activate from scratch).** *"Publish it to Substack."* — but
the post isn't drafted → flow `publish`.

| Op | Stack after |
|---|---|
| `stackon(publish)` | `[publish·pending]` |
| `activate(publish)` → finds no draft, `stackon(draft)`, **yields** (no L4) | `[publish·pending, draft·pending]` |
| `activate(draft)` → drafts, writes scratchpad, `complete_flow` | `[publish·pending, draft·completed]` |
| `pop` | `[publish·pending]` |
| `activate(publish)` → **re-activated from scratch**, reads draft from scratchpad, publishes, `complete_flow` → `pop` | `[]` → **delivered** |

`publish` reverts to pending while its prerequisite owns the top; on return it runs fresh, picking up state from
the scratchpad.

**3 — Multiple ACTIVE flows, same type (parallel batch).** *"Draft the intro, methods, and results sections."* →
three `draft` flows, different targets.

| Op | Stack after |
|---|---|
| `stackon` ×3 | `[draft·intro·pending, draft·methods·pending, draft·results·pending]` |
| `activate(...)` — **same type ⇒ batch together** | `[…·active, …·active, …·active]` — 3 sub-agents in parallel |
| each policy `complete_flow`; `pop` ×3 | `[]` |

PEX curates the **3 same-type artifacts into one** (origin trivially `draft`). This is the case the same-type
activation rule exists for.

**4 — A Plan of DIFFERENT-type flows (sequential, top-only).** *"Research the topic, draft a post, then publish
it."* → Plan, 3 different-type sub-flows run in order.

| Op | Stack after |
|---|---|
| `stackon(publish)`, `stackon(draft)`, `stackon(research)` | `[publish·pending, draft·pending, research·pending]` |
| `activate(research)` — top only, **can't batch (different types)** → complete → pop | `[publish·pending, draft·pending]` |
| `activate(draft)` → complete → pop | `[publish·pending]` |
| `activate(publish)` → complete → pop | `[]` → **delivered** |

Mid-Plan PEX keeps going across all three on one turn (Plan = the sanctioned chaining path). The contrast with
example 3 pins down both `activate` rules: **same type → activate together; different types → one at a
time, top first.**

## Failure Recovery

Failure recovery is owned by [PEX](../modules/pex.md), not the Workflow Planner itself. The flow of recovery:

1. **Policy classifies the failure** — tool-call failure → error artifact with `parts={'violation': 'tool_error', ...}`; ambiguous user intent → `ambiguity.declare(level, observation=, metadata=)` (note: `declare()`'s `metadata=` parameter stays — it's the ambiguity component's input, not the artifact attribute); malformed skill output → error artifact with `parts={'violation': 'parse_failure'}`.
2. **PEX decides** based on what was returned:
   - Tool error and transient → retry once via `BasePolicy.retry_tool(tools, name, params, max_attempts=2)`.
   - Ambiguity that may indicate the wrong flow → `understand(op='contemplate')` to re-route; mark current flow Invalid; best-effort slot mapping to the new flow.
   - Otherwise → PEX surfaces the clarification so the user can answer.

Tool failures are infrastructure, not user-facing questions — never declare ambiguity for them. Ambiguity is the only channel that produces a clarification question. Conflating the two channels hides root cause.
