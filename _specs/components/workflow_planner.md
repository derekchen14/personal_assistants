# Workflow Planner

Two things share this spec: the **FlowStack** data structure that stores the flows (code: `flow_stack.py`),
and **Workflow Planning** (equivalently, **Sub-agent Routing**) — the activity [PEX](../modules/pex.md)'s LLM
performs over it. PEX plans: it decides which sub-agents to run, handles fallbacks and stack-ons, and tracks
how far through a complex request the agent is. Its **primary input is NLU's detected flow** (the flow fixes
the intent — see [Dialogue State § Predicting the Belief State](./dialogue_state.md#predicting-the-belief-state))
— the planner routes from that belief, not the raw utterance. The flows it plans across are stored in the
FlowStack, whose contents are serialized in the Dialogue State document's `flow_stack` block — the one block
the Workflow Planner owns and writes via the `manage_flows(op)` tool (`update` / `stackon` / `fallback` /
`pop`; replaces the old `write_state` flow ops), distinct from the belief NLU maintains. Policy
execution is **not** a separate planner op: `stackon` (whose `active` flag defaults to true), `fallback`,
and a `pop` that surfaces a Pending flow hand the top flow to the runtime, which runs its policy and
feeds the result back to PEX. Passing `active=false` queues a plan step as Pending without running it
(see [Automatic Policy Dispatch](#automatic-policy-dispatch-pending--active--policy-result)).

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
| **Pending** | Stacked but not yet finished: a plan step waiting its turn, a parent that yielded to a prerequisite, or a flow reverted beneath a detour. |
| **Active** | Claimed the conversation: executing now, OR stalled awaiting the user's answer. Top region of the stack. |
| **Completed** | Successfully finished; removed by the same-turn `pop` from the PEX agent. |
| **Invalid** | Wrong flow (a fallback replaced it), abandoned by the user, or hit a hard failure; removed by the same-turn `pop`. |

## Stack Invariants — Turn-Boundary Discipline (round 3.3)

The stack is only useful if every turn starts from a known shape. These invariants define that shape;
round 3.3 (`round_3.3_spec.md`: when detection returns the flow that is already Active, NLU fills
that flow in place instead of stacking a new one) and PEX's pop discipline both depend on them. This
section is the current best understanding — where the code deviates, the gap is named at the end.

NLU's order of operations never changes: all three ops (`react` / `think` / `contemplate`) run flow
detection first (which indirectly classifies the intent), then slot-filling. A stalled Active flow
does not reorder anything — it only changes where the fill lands.

### What Active and Pending actually mean

- **Active is a claim on the conversation, not a CPU state.** When detection lands on the flow that
  is already Active — which it should, since the conversation history carries the open question —
  slot-filling applies to that same flow rather than stacking a duplicate. This holds whether or not
  a policy is executing at this instant: a flow that asked a clarification question and is waiting
  for the answer is still Active.
- **Pending means queued and not yet completed**: plan steps awaiting their turn, a parent that
  yielded to a prerequisite, or a flow reverted beneath a detour. A Pending flow never talks to the
  user, and NLU never fills its slots.

### The turn-boundary invariant

At the END of every turn (equivalently, the start of the next), exactly one of two shapes holds:

1. **Empty stack** — all work completed and popped; the next turn starts with fresh detection.
2. **Active-incomplete top** — an Active flow on top waiting on the user (missing slot, confirmation,
   plan checkpoint), with only Pending flows beneath it.

Corollaries:

- **No Pending flow is ever on top at turn start.** After `pop`, the runtime clears terminal flows
  until it exposes a Pending flow, promotes that Pending flow to Active, and immediately runs its
  policy. PEX never calls an `activate` tool to do this. That is what guarantees NLU's detection is
  always compared against a live Active flow, never a stale one.
- **No Completed or Invalid entry survives a turn.** They exist only transiently, between a policy's
  `complete_flow` and the planner's `pop`, inside a single turn.
- The legal shape is always `[bottom: Pending…, top: Active(s)]` — Actives contiguous on top. With
  parallel same-type batches, the planner should still end the turn with at most ONE stalled Active
  (the batch either finishes in-turn or its open question is a single question).

### Turn-start decision table — who gets the utterance

Detection always runs first; the table keys on how its result relates to the stack:

| Stack top at turn start | The turn is read as | Stack op |
|---|---|---|
| empty | a fresh task | `stackon` the detected flow |
| Active flow; detection returns the SAME flow | an answer or elaboration for that task | none — nlu.think() fills that flow; its policy resumes |
| Active flow; detection returns a DIFFERENT flow | a side task the user will return from (the default) | `stackon` the detected flow; the stalled flow reverts to Pending beneath it |
| Active flow; explicit discard signal | a cancellation | `update` the flow to Invalid, `pop`, then the detected flow is stacked |

`fallback` deliberately has no row here: it is not a turn-start response to the user. Fallback
re-routes a wrongly predicted flow discovered DURING execution (see the Fallback section) —
abandonment never needs it, since PEX can mark the flow Invalid directly and move on.

### The Continue intent

PEX's intent choice set has eight options: the six task intents (Research, Draft, Revise, Publish,
Converse, Plan), Clarify, and **Continue**. Continue means: this turn advances the flow that is
already Active — no new flow, no re-route. It is the intent-level twin of the decision table's
second row: detection lands on the Active flow, slot-filling applies to it in place, and the
runtime runs its policy.

Continue changes nothing about NLU's process — nlu.think() runs flow detection then slot-filling,
exactly as on every turn. It only changes two config inputs: `hint` carries the currently Active
flow, and detection runs with TWO medium voters instead of three, because PEX's Continue selection
seeds the votes list as the third, flow-level vote — the tally and confidence math run unchanged
over three votes. The two voters are the medium tiers of the families PEX is NOT running on: PEX
on Claude → Gemini and GPT vote; PEX on GPT → Gemini and Claude; PEX on Gemini → GPT and Claude.

Continue is only a legal choice while an Active flow exists; on an empty stack it degenerates to a
normal task intent.

The detour row is what makes the stack a stack: the stalled flow keeps its position, its filled
slots, and its open question (still unresolved in the AmbiguityHandler); the detour runs above it;
the `pop` after the detour completes re-surfaces the stalled flow, whose policy re-asks its question.
Nothing about the original task is re-derived.

**Detour vs. abandonment is a judgment call, and the default is detour (`stackon`)** — it is
reversible (an abandoned flow beneath eventually gets marked Invalid and popped), while cancelling
destroys the stalled flow's slot state. Treat as abandonment only on an explicit discard signal:
"forget the outline", "cancel it", "never mind". Never `stackon` a duplicate of the Active flow —
the Active flow IS that task (the FlowStack's same-type dedupe enforces this mechanically).

### Three writers, one owner

- **NLU stages**: NLU programmatically places the detected flow onto the stack so PEX can see the
  change directly. During the same pass, NLU also runs slot-filling on this flow before handing
  control back to PEX. NLU never pops or runs fallback.
- **Policies self-report**: a policy pushes its own prerequisites onto the stack (`stackon`) and marks
  itself Completed (`complete_flow`) — it never touches flows other than itself and its prereqs.
- **PEX (the Workflow Planner) owns lifecycle decisions**: update, stackon, pop, fallback, and the
  judgment calls in the decision table.
- **The runtime owns policy execution**: an internal `activate()` function may exist, but it is not a
  tool and is not part of the Workflow Planner's choice set. The runtime promotes the top Pending
  flow to Active and executes its policy automatically; it does not need PEX to activate a flow
  that is already Active.

### Current implementation gaps

The contract above is the target, not yet fully the code. The gap list and the tasks that close
each one are temporary state and live in `_specs/_review/rounds/round_2.12_spec.md`.

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

Three transition channels, each with different UX. There is no `keep_going` flag anywhere: the PEX
orchestrator ALWAYS keeps going to the next flow, applying one rule per stack top until it runs out
of work or must ask the user:

- **Completed** → `pop` it off. Remember the details — they may inform the agent response.
- **Invalid** → `pop` it off. Remember the details — they may inform the agent response.
- **Pending** → the runtime promotes it to Active and runs its policy (automatic, not a tool call).
- **Active** → try to make progress. Escalate to the user only after exhausting the reasonable
  recovery options (`recover_from_ambiguity`, a tool retry, `understand(op='contemplate')`).

(`complete_flow` is the flow's own policy marking itself done — not a planner op.) A turn therefore
ends in exactly two ways: no flows left on the stack, or an Active flow that needs information only
the user can provide.

### Automatic Policy Dispatch (pending → active → policy result)

`activate()` is an internal runtime function, not a planner tool. PEX never asks to activate a flow.
Exactly three stack events hand the top flow to the runtime, which runs its policy and returns the
result to PEX:

1. **`stackon`** — pushes the flow and, by default (`active=true`), runs it immediately, so most
   turns never mention the flag. Pass `active=false` to queue a plan step as Pending without
   running it — that is what lets a plan stack several steps without running each one prematurely.
2. **`fallback`** — the replacement takes over the conversation immediately, so it runs.
3. **`pop` that surfaces a Pending flow** — the runtime promotes it to Active and runs it.

The policy result is returned to PEX, which decides whether to ask the user, `pop`, `fallback`,
`stackon` another flow, or conclude. When PEX calls `pop`, the tool runs the
cleanup-and-policy-run loop itself:

```python
while top.status in ('Completed', 'Invalid'):
    remove(top)
if top.status == 'Pending':
    top.status = 'Active'
    return run_policy(top)
return {'status': top.status}
```

This keeps the Workflow Planner focused on lifecycle judgment. It should never issue a separate
activation command, and it should never "activate" a flow already in the Active state.

### Stack On (prerequisite setup)

The current flow needs another flow's output before it can run. Push the prerequisite, resume after.

```python
self.flow_stack.stackon('<prereq_flow>')
artifact = TaskArtifact(flow.name(), thoughts='<reason — surfaces to user via PEX>')
```

### Fallback (re-route a wrongly predicted flow)

The most common fallback cause: the originally predicted flow was wrong, and execution proved it.
The typical lifecycle:

1. The sub-agent hits an issue mid-execution.
2. The policy has a hard-coded fallback target, or it triggers `understand(op='contemplate')` to
   re-route.
3. Given the new fallback flow, the original flow is marked Invalid.
4. Useful slot values transfer to the new flow (matching names, best-effort; unmatched discarded),
   and the new flow is stacked on top.
5. When the task is done, the new flow is marked Completed; PEX pops Completed and Invalid flows
   until none remain on the stack — the Invalid original leaves in that same-turn sweep.

```python
self.flow_stack.fallback('<sibling_flow>')
artifact = TaskArtifact(flow.name(), thoughts='<why we re-routed>')
```

Fallback is NOT for user abandonment — if the user walks away from a task, PEX just marks the flow
Invalid and moves on; no replacement push, no slot transfer. And it is never for skill errors or
tool failures (those use error artifacts).

### Confirmation turns

When a flow is awaiting the user's accept/decline, the answer belongs to that flow's resolution turn:
the active flow stays on the stack, the user's yes/no arrives as an utterance or button payload, and
PEX resolves it on the active flow. `endorse` / `dismiss` are **tools** PEX may call to record the
outcome — never a second flow stacked on top, so nothing competes with the active flow for the turn.
(Historical: when endorse/dismiss were Converse flows, they had to yield to the flow beneath them; the
flow audit converted them to tools and removed that case.)

## Planner Scenario Matrix — Push, Pop, Fallback, Update

These scenarios are the cases the Workflow Planner skill should explicitly reason through. They are written
against the current FlowStack implementation as the starting point, but the behavioral contract is the more
important part: keep a single clear owner for lifecycle decisions, preserve unresolved work under detours, and
avoid re-deriving state that is already on the stack.

Stacks are shown **bottom → top**. Each scenario names the concrete user turn, the state the planner sees, the
stack operation it should choose, and the bug the rule is meant to prevent. This matrix replaces the older
"Worked Examples" section: the baseline single-flow case is scenario 1, prerequisite yielding is scenario 10,
same-type batching is scenario 12, and different-type sequential plans are scenario 11.

**1 — Fresh single-flow request with enough information.**

- User turn: "Outline a post about tide-pool ecology for a general audience."
- Before: `[]`; NLU predicts `Draft(outline)` with `topic=tide-pool ecology` and perhaps `depth=medium`.
- Planner action: `manage_flows(op="stackon", flow_name="outline")`; the runtime promotes the new top
  Pending flow to Active and runs the policy automatically.
- Expected result: the outline policy runs immediately. If it creates the post/outline and calls
  `complete_flow`, PEX calls `pop` before replying.

```
[] → stackon(outline)
→ runtime runs outline policy
→ [outline·active topic=tide-pool ecology]
→ complete_flow
→ [outline·completed]
→ pop
→ []
```

This is the baseline case. The important detail is that a completed one-shot task should not leave
`outline·completed` on the stack for the next turn.

**2 — Fresh single-flow request missing an elective-or-required slot.**

- User turn: "Outline a post."
- Before: `[]`; NLU predicts `Draft(outline)` but does not fill `topic` or `source`.
- Planner action: stack `outline`; the runtime runs its policy, which should declare ambiguity
  rather than complete.
- Expected result: the stack remains `[outline·active]`; PEX asks the clarification and stops.

```
[] → stackon(outline)
→ runtime runs outline policy
→ [outline·active source missing, topic missing]
→ policy declares ambiguity: "What should the outline be about?"
→ [outline·active source missing, topic missing]
```

For `outline`, topic and source are electives, but at least one should be filled. That makes this different
from an entity-grounded edit flow: the policy can create a new post from a topic if the source is absent, but it
cannot proceed if both are absent.

**3 — User answers an active clarification with only the missing value.**

- User turn: "tide-pool ecology."
- Before: `[outline·active source missing, topic missing]`; AmbiguityHandler has an open question for
  `outline`.
- Planner action: do not `stackon`. nlu.think() runs detection as always; the history carries the
  open question, so detection lands on `outline` — the flow already Active — and slot-filling writes
  the value into that same flow. The runtime then continues its policy.
- Expected result: `outline` receives `topic=tide-pool ecology`; the same stack entry runs.

```
[outline·active source missing, topic missing]
+ "tide-pool ecology"
→ update top slots: topic=tide-pool ecology
→ [outline·active topic=tide-pool ecology]
→ runtime continues outline policy
→ complete_flow
→ [outline·completed]
→ pop
→ []
```

Then proceed as normal to complete the flow.

**4 — User answers an active entity clarification by pointing to a visible choice.**

- User turn: "Use the second one."
- Before: `[release·active source missing]`; the UI has just shown several candidate posts from a prior
  `find_posts` block.
- Planner action: nlu.think() detects `release` (matching the Active flow) and fills the selected
  entity into its `source` slot (the candidates live in `grounding.choices`). The runtime then
  continues the `release` policy.
- Expected result: the stack remains one `release` entry; no `find`, `inspect`, or new `release` is pushed.

```
[release·pending source missing, find·active]
→ searches for 3 plausible options
→ completes `find` flow 
→ pop
[release·active source missing]
+ "Use the second one"
→ update top slots: source={post: <selected post id>, ...}
→ [release·active source=<selected post>]
→ runtime continues release policy
```

The utterance is not semantically rich by itself — the meaning comes from the active flow plus the
open ambiguity context (and the shown candidate list). Detection still runs first, as it does on
every turn; that context is what steers it back to `release` instead of a fresh flow.

**5 — Same-dax follow-up after a completed flow: a NEW flow, not an update (counter-example).**

- User turn: "Actually make it a detailed outline."
- Before: `[]`. The brief tide-pool outline ran and COMPLETED last turn — a satisfied flow pops the
  same turn, so it is no longer on the stack. The created post is the active entity in the dialogue
  state's grounding.
- Planner action: this is a fresh `outline` flow whose dialogue act happens to match the previous
  one. Detection stacks it; `source` auto-fills from the active post (grounding transfer), and
  `depth` fills as detailed.
- Expected result: a second outline flow runs against the same post; the first one stays popped.

```
previous turn: "Give me a quick outline for a post on tide-pool ecology"
[] → stackon(outline)
→ [outline·active topic=tide-pool ecology depth=brief]
→ outline policy creates the post, generates the outline, completes
→ pop
→ []   (the new post is now the active entity in grounding)

this turn: "Actually make it a detailed outline"
→ stackon(outline)
→ [outline·active source=<the new post> depth=detailed]
→ runtime runs outline policy
```

What should NOT happen: treating this as an update to a still-Active outline. The outline never
stalled — it completed. A flow only remains Active across a turn boundary when it is missing
information; if it genuinely were stalled (rare here), decision-table row two applies and the fill
lands on it in place.

Note on `depth`: it is the outline's depth (section, sub-section, bullet, sub-bullet), NOT the
number of sections. "Six sections" would fill `sections`; "detailed" deepens `depth`.

**6a — Detour from a stalled flow: run it, then resume with its results.**

- User turn: "The one I want updated is my outline about oceans."
- Before: `[outline·active source missing]`; the user has provided details to fill the missing slot
- Planner action: `stackon(find)`; `outline` reverts to Pending beneath it and the runtime runs the
  new top `find` policy. After `find` completes, `pop` promotes `outline` and re-runs its policy —
  and if `find` returned exactly one strong candidate, PEX fills `outline.source` with it.
- Expected result: the original flow is preserved rather than re-created, and when the detour's
  result is unambiguous, no extra clarification is needed.

```
[outline·active source missing]
→ stackon(find); outline reverts to Pending
→ runtime runs find policy
→ [outline·pending, find·active query=oceans]
→ complete `find` flow with one candidate post-A, writes the result to session scratchpad
→ pop → runtime promotes outline, and fills its missing slot
→ manage_flows(op="update", fields={slots: {source: post-A}})
→ [outline·active source=post-A]
→ runtime continues outline policy
→ complete `outline` flow 
```

The open source ambiguity belongs to `outline` the whole time. The detour is not the end goal — it
exists to gather information for the flow underneath it.

**6b — Detour result does not satisfy the stalled flow.**

- User turn: "The one I want updated is my outline about oceans."
- Before: `[outline·active source missing]`. the user has provided details to fill the missing slot
- Planner action: stack `find`; if it returns too many plausible candidates; `find` has done its job, so it can be marked complete and pop
- However `outline` remains active with ambiguity.
- Expected result: PEX asks the user to choose or refine; it should not complete `outline`.

```
[outline·active source missing]
→ stackon(find); outline reverts to Pending
→ runtime runs find policy
→ [outline·pending, find·active query=oceans]
→ find complete_flow with 6 candidates (too many)
→ pop → runtime promotes outline and runs its policy
→ [outline·active source missing]
→ ask: "Which post should I use?"
```

The edge here is that `find` completed successfully but the parent did not. Popping the child is correct;
popping the parent is not.

**7 — Explicit abandonment: mark Invalid and move on, no fallback.**

- User turn: "Forget the revision. Just publish the current post to Substack."
- Before: `[rework·active]`.
- Planner action: the user explicitly abandons the active task, so PEX marks `rework` Invalid
  directly and stacks the new task. No `fallback` — fallback re-routes a wrongly predicted flow;
  abandonment needs no replacement semantics and no slot transfer.
- Expected result: `rework` leaves in the same-turn `pop`; `release` runs as a fresh flow.

```
[rework·active]
→ manage_flows(op="update", fields={status: Invalid})
→ [rework·invalid]
→ pop
→ []
→ stackon(release)
→ runtime runs release policy
→ [release·active]
```

Default to detour when abandonment is unclear. Treat as abandonment only on an explicit discard
phrase ("forget that", "cancel it", "never mind").

**8 — NLU detects a sibling flow but the active flow context explains the utterance.**

- User turn: "Make it sharper and less academic."
- Before: `[compose·active source=post-A]`; compose has asked for guidance.
- NLU might predict: `Revise(rework)` because the utterance sounds like an edit.
- Planner action: nlu.think() fills `compose.guidance`, since `compose` is waiting for guidance.
- Expected result: update/resume `compose`, not fallback to `rework`. This especially true because compose operates on outlines, whereas rework operates on prose. So if we are still dealing with outlines, then `rework` clearly doesn't apply.

```
[compose·active source=post-A guidance missing]
→ update compose.guidance="sharper and less academic"
→ [compose·active source=post-A guidance=...]
→ runtime continues compose policy
```

This case is why a detection that differs from the Active flow is a judgment call, never
automatically authoritative. The same words can either be a new edit request or an answer to a
compose clarification.

**9 — NLU detects a different intent and the active context does not explain it.**

- User turn: "Once it is cleaned up, schedule it for next Friday morning."
- Before: `[rework·active suggestions missing]` — rework asked what to change; no open
  scheduling-related question. (The stalled flow is a Revise flow on purpose: a filled outline would
  have completed and popped, and revise-then-publish is the realistic sequence.)
- NLU predicts: `Publish(schedule)`.
- Planner action: if the user had said "forget the edits, just schedule it as is",
  that is abandonment — mark `rework` Invalid, pop, and stack `schedule`. Instead, the user said "once it is cleaned up, schedule it for next Friday" so it should be treated as a plan extension.

```
extension:
[rework·active suggestions missing] + "once it's cleaned up, schedule it for Friday"
→ keep rework as current work
→ record the future schedule step in the scratchpad or planner context
→ Push the user again to clarify the missing 'suggestions' slot about what to clean up
→ after rework completes and pops, stackon(schedule)
→ runtime runs schedule policy
```

This is one of the highest-risk judgment calls for the Workflow Planner: same detected flow, different stack
operation depending on discourse markers. With the current stack primitive, a new flow can only be pushed on
top; PEX cannot directly insert `schedule` underneath an already Active `rework`.

**10 — Policy discovers a prerequisite and yields to it.**

- User turn: "Compose the post."
- Before: `[compose·active source=post-A]`.
- Policy observation: post-A has no outline bullets, so compose cannot convert outline to prose yet.
- Planner/policy action: make `compose` wait, stack `outline` above it, and run `outline`.
- Expected result: after `outline` completes, `compose` resumes and reads the new outline from the post or
  scratchpad.

```
[compose·active source=post-A]
→ compose yields: stackon(outline) demotes it to Pending
→ [compose·pending source=post-A, outline·active source=post-A]
→ runtime runs outline policy, but immediately raise 'specific' ambiguity
→ missing content, so ask the user for details about what goes in the outline
→ [compose·pending source=post-A, outline·active source=post-A]
→ [compose·pending source=post-A, outline·completed source=post-A]
→ pop
→ runtime promotes compose and runs its policy
→ [compose·active source=post-A]
```

Mechanically, `FlowStack.stackon()` pushes the child and demotes the parent to Pending.

**11 — Multi-step plan that should run in one continuous chain.**

- User turn: "Research tide-pool ecology, outline the post, write the draft, then publish it."
- Before: `[]`.
- Planner action: map to existing flows, order by dependency, then stack in reverse execution order. Once the
  first-to-run flow is on top, the runtime runs its policy automatically.
- Expected result: PEX keeps going after each completion because this is an explicit Plan turn.

```
desired execution: find → outline → compose → release
stackon(release, active=False)
→ [release·pending]
stackon(compose, active=False)
→ [release·pending, compose·pending]
stackon(outline, active=False)
→ [release·pending, compose·pending, outline·pending]
stackon(find)                # default active=true: push and run
→ [release·pending, compose·pending, outline·pending, find·active]
→ runtime runs find policy
```

After `find` completes, `pop` promotes `outline` and runs its policy; after `outline` completes, `pop`
promotes `compose` and runs its policy; after `compose` completes, `pop` promotes `release` and runs its policy. The
planner should not ask for review between each step unless the plan hits ambiguity, approval checkpoint, or a policy returns a user-facing checkpoint. 

**12a — Multi-section request on ONE post: one flow with steps, not a stack batch.**

- User turn: "Write prose for the intro, the comparison section, and the takeaways of this post."
- Before: `[]`; post-A is the active entity in grounding.
- Planner action: ONE `compose` flow — Do not push three compose entries because the Compose already has a slot meant for holding multiple steps. The three sections land in its `steps` checklist (compose declares `steps: ChecklistSlot`). The reason has nothing to do with `stackon` deduplication or non-terminal same-types in the stack.
- Expected result: a single compose works through the three sections and completes once.

```
[] + "write prose for the intro, the comparison section, and the takeaways"
→ stackon(compose)
→ [compose·active source=post-A steps=[intro, comparison, takeaways]]
→ policy converts each section in turn, complete_flow
→ pop
→ []
```

The merge depends on the flow's slot schema, not on the request: compose declares a `steps`
ChecklistSlot, so the three sections fold into one flow. A flow without such a multi-item slot
spins off one instance per unit of work — see 12b.

**12b — Same dialogue act, DIFFERENT targets: multiple flows (the contrast).**

- User turn: "Summarize my three posts on tide-pools, frogs, and giraffes"
- Before: `[]`; the three posts are known (a prior find, or named in the utterance).
- Planner action: three `summarize` flows, one per post — summarize typically runs on a single post, so in order to handle three, we must stack-on three different posts which each spins off as its own instance.
- Since all three flows share the same policy, this is the one exception where multiple flows can be active at the same time.
- Expected result: all three run in parallel today; then PEX curates the three same-origin artifacts into ONE reply.

```
[] + "summarize my three posts on tide-pools, frogs, and giraffes"
→ stackon(summarize)   # source=post-A
→ stackon(summarize)   # source=post-B
→ stackon(summarize)   # source=post-C
→ [summarize·active giraffes, summarize·active frogs, summarize·active tide-pools]
→ whenever summaries are complete, write to Session Scratchpad and mark itself complete
→ pop will clear out all three at once → []
→ PEX curates the three summaries into one reply
```

Two mechanics this leans on. First, the same-type rule: because all three flows share one dialogue
act, their results merge into one response at the end. Second, a fix to the duplicate check: today,
when a `summarize` flow is already on the stack and unfinished, calling `stackon('summarize')`
again does nothing — the stack assumes the user repeated the same task and returns the existing
flow. The check must also look at the entity slot to check if the flow is truly a duplicate: a summarize for a different post is a new task, not a duplicate (tracked in round 2.12).

**13 — Multi-step request where the planner should stop for review.**

- User turn: "Find posts about tide pools and suggest one I should expand."
- Before: `[]`.
- Planner action: run `find`; stop after presenting candidates because the user asked for a choice,
  not for automatic drafting.
- Expected result: do not stack `write` or `compose` speculatively.

```
[] → stackon(find)
→ runtime runs find policy
→ [find·active query=tide pools]
→ complete_flow with candidates
→ pop
→ []
→ ask/summarize candidates for user review
```

The skill should distinguish "do X, then Y" from "find something so I can decide." The latter is not an implicit plan continuation.

**14 — Completed and Invalid entries are transient cleanup targets.**

- User turn: internal planner cleanup after a sub-flow returns.
- Before: `[release·pending, compose·completed, find·invalid]`.
- Planner action: `pop`.
- Expected result: all terminal entries are removed in one sweep; the next Pending top becomes Active. PEX should continue forward to execute the `release` policy before returning to the user.
- Once PEX agent decides to pop(), it will likely not hear back until the `release` sub-agent completes its task.

```
[release·pending, compose·completed, find·invalid]
→ pop
→ runtime promotes release and runs its policy
→ [release·active]
→ attempt to complete `release`
```

Completed/Invalid tops are stale. `stackon` should not inherit slots from them, and NLU never fills
slots on a terminal flow.

**15 — Slot transfer helps on a fallback: the replacement flow keeps what the user already said.**

- User turn: "Tighten the wording in the intro — it rambles."
- Before: NLU predicted `Revise(rework)` and it is running; the policy finds the ask is
  sentence-level within one section — wrong flow, `write` owns that scope. This is the canonical
  fallback: a hard-coded fallback target in the policy, or a re-route via
  `understand(op='contemplate')`.
- Planner action: `fallback(write)`; `rework` is marked Invalid and the matching `source` +
  `suggestions` values transfer into `write`, so the user repeats nothing. NLU predicted only the
  post and section (had it captured the snippet, it would never have routed to `rework` in the
  first place). After the transfer, the `write` policy fills the missing detail itself: it reads
  the section, locates the rambling paragraph, and fills `source.snip`.
- Expected result: `write` runs with the transferred section, gains the snippet focus on its own,
  and applies the same instruction.

```
[rework·active source={post-A, sec=intro} suggestions=[tighten it]]
→ policy: scope is one paragraph → fallback(write)
→ [rework·invalid, write·active source={post-A, sec=intro} suggestions=[tighten it]]
→ write policy reads the intro, locates the rambling paragraph, fills source.snip=[2, 5]
→ [write·active source={post-A, sec=intro, snip=[2, 5]}]
→ write completes; the same-turn pop sweeps both
```

Just as `post` stores the post id (not the title), `snip` stores the snippet id, keyed on the
paragraph — never a description of the area like "the wording that rambles". The policy resolves
it by reading the section; NLU does not guess it from the utterance. Snippet-id semantics are
documented in `schemas/tools.yaml`: section content is an ordered list of sentences, and `snip_id`
is a sentence index or an end-exclusive `[start, end]` slice (`read_section` / `revise_content` /
`remove_content`); `read_metadata` returns each section's `sentence_count`, and
`read_section(include_sentence_ids=true)` numbers the sentences so the policy can pick valid ids.
The entity vocabulary itself lives in
[Dialogue State § Grounding Slots](./dialogue_state.md#grounding-slots).

This is the happy path for slot transfer — and the reason `fallback` transfers at all: the values
were never in question, only the flow choice was.

**16a — Ambiguity is not lifecycle failure: do nothing to the stack.**

- User turn: "Publish it."
- Before: `[]` or `[release·active source missing]`; grounding has no active post.
- Planner action: run/keep `release` Active; policy declares partial ambiguity for the missing post.
- Expected result: ask which post to publish. Do not pop; do not mark Invalid; do not invent a source.

```
[release·active source missing]
→ policy declares partial ambiguity: missing source/post
→ [release·active source missing]
→ nlu.think() fills release.source from the next user answer
```

This is especially important for entity-grounded flows: code-side completion validation rejects Completed when
the active post grounding is missing, but the planner behavior is to ask for the missing entity, not to invent a
new lifecycle state.

**16b — Tool failure is not ambiguity and not fallback: do nothing to the stack.**

- User turn: "Publish the current post."
- Before: `[release·active source=post-A channel=substack]`.
- Policy observation: `release_post` fails with a transient API error.
- Planner action: retry once if the tool/error policy allows; otherwise surface an error artifact. Keep the
  flow Active or fail the policy according to the error path, but do not ask "which post?" and do not fallback.

```
[release·active source=post-A channel=substack]
→ release_post fails
→ retry or error artifact
→ no fallback(release), no new ambiguity about source
```

The user provided the required semantic information; the failure is infrastructure or tool execution.

**17 — Stack depth pressure should defer, not branch unboundedly.**

- User turn: "For each of these 8 posts, audit, rewrite, and cite sources"
- This would amount to 8 x 3 = 24 flows, but that is beyond the max of 16 flows.
- Planner action: stack only the bounded next tranche of concrete flows for the 5 posts. This is 15 flows. Then write the next steps on the scratchpad for the 3 posts x 3 = 9 deferred flows.
- Expected result: no `RuntimeError` from exceeding max depth since we stay beneath the limit.

```
[]
→ planner adds 15 flows (in reverse order since we are dealing with a stack, rather than a queue)
[cite·pending post-5, rework·pending post-5, audit·pending post-5, cite·pending post-4, rework·pending post-4, audit·pending post-4, cite·pending post-3, rework·pending post-3, audit·pending post-3, cite·pending post-2, rework·pending post-2, audit·pending post-2, cite·pending post-1, rework·pending post-1, audit·pending post-1]
→ stack only 15 flows. We don't need to go to 16, since each set of flows naturally comes in batches of 3.
→ scratchpad note: remaining requested work still pending for 3 remaining posts.
```

The stack is an execution structure, not an unbounded project plan. The planner should use the scratchpad for
overflow memory.

**18 — One utterance both answers the open question and starts a new task.**

- User turn: "Use the guardrails one — oh and how many posts did I publish last month?"
- Before: `[release·active source missing]` with candidates shown.
- Resolution: detection keys on the NEW request and lands on `inspect` (post metrics/metadata). The
  answer clause is not lost — the resumed flow's slot-filling captures it later from the same
  conversation history.

```
[release·active source missing]
→ detection lands on inspect → stackon(inspect); release reverts to Pending
→ [release·pending, inspect·active]
→ inspect sub-agent reaches MEM for the answer, writes the result to the session scratchpad
→ policy marks inspect Completed; control returns to PEX
→ PEX reviews the TaskArtifact, runs pop
→ pop removes inspect, promotes release, runs its policy
→ the policy sees the missing slot → slot-filling runs → grabs "the guardrails one"
→ [release·active source=<guardrails post>]
→ release sub-agent publishes the post; complete_flow
→ PEX runs pop again → [] → PEX forms the agent response covering both clauses
```

**19 — Cancel everything while a detour is running.**

- User turn: "Never mind all of it."
- Before: `[outline·pending, find·active]`.
- Resolution: `pop`, `stackon`, `fallback`, and `get_flow` operate only on the flow on top, but
  `find_by_name()` reaches any depth — and so does `update_flow()`. PEX marks every doomed flow
  Invalid in place (no surfacing, no policy runs), then one `pop` sweeps them all.

```
[outline·pending, find·active] + "never mind all of it"
→ update_flow(find, status=Invalid); update_flow(outline, status=Invalid)
→ [outline·invalid, find·invalid]
→ pop → []
→ acknowledge the cancellation
```

`FlowStack.update_flow()` does not exist yet — it gets written in round 2.12.

**20 — Continuing an Active flow needs a trigger to run the policy.**

- User turn: "tide-pool ecology" (answering outline's open question).
- Before: `[outline·active topic missing]`; nlu.think() fills `topic` during `understand`, before
  the PEX loop starts, so no stack operation follows that could start the policy.
- Resolution: PEX selects the **Continue** intent, and that selection IS the trigger — the runtime
  runs the Active flow's policy. If PEX mispredicts a task intent instead (e.g. Draft, which maps
  back to `outline`), it recovers with `manage_flows(op="update", fields={status: "Active"})`,
  which re-runs the flow — a status write through `update` is the manual run button; an `update`
  that only touches slots still never triggers a run.

```
[outline·active topic missing] + "tide-pool ecology"
→ nlu.think() fills topic during understand
→ PEX picks Continue → runtime runs outline policy
→ complete_flow → pop → []
```

**21 — Two stalled questions, one ambiguity frame.**

- User turn: (mid-detour) `find` itself stalls: "What should I search for?"
- Before: `[outline·pending (open question: which draft?), find·active]`.
- Resolution: the Ambiguity Handler scales to concurrent ambiguities. `metadata` is a dict — new
  information is ADDED without kicking out what is already there — and `counts` increments to show
  several ambiguities are open at once. Only the `observation` string is immutable; it may be lost
  in the overlap, which is acceptable: the durable record is metadata plus each flow's own slot
  state, so a promoted flow re-asks from those.

```
find declares its ambiguity
→ metadata carries both questions' info; counts show two ambiguities open
→ user answers find's question → find completes → pop promotes outline
→ outline re-asks from its slot state and metadata
```

## Failure Recovery

Failure recovery is owned by [PEX](../modules/pex.md), not the Workflow Planner itself. The flow of recovery:

1. **Policy classifies the failure** — tool-call failure → error artifact with `parts={'violation': 'tool_error', ...}`; ambiguous user intent → `ambiguity.declare(level, observation=, metadata=)` (note: `declare()`'s `metadata=` parameter stays — it's the ambiguity component's input, not the artifact attribute); malformed skill output → error artifact with `parts={'violation': 'parse_failure'}`.
2. **PEX decides** based on what was returned:
   - Tool error and transient → retry once via `BasePolicy.retry_tool(tools, name, params, max_attempts=2)`.
   - Ambiguity that may indicate the wrong flow → `understand(op='contemplate')` to re-route; mark current flow Invalid; best-effort slot mapping to the new flow.
   - Otherwise → PEX surfaces the clarification so the user can answer.

Tool failures are infrastructure, not user-facing questions — never declare ambiguity for them. Ambiguity is the only channel that produces a clarification question. Conflating the two channels hides root cause.
