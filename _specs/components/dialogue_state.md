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

> Memory work is **not** an intent. There is no `Internal` intent — `recap` / `recall` / `retrieve` are MEM skills (see [mem.md](../modules/mem.md)), and other deterministic operations are plain tools. The Dialogue State is written only by NLU's belief writes, so it is single-writer and never at risk of merge collisions; the surface that guards against race conditions is the [Session Scratchpad](./session_scratchpad.md), maintained by NLU.

### Flows (skills)
- Also known as dialog acts, workflows, or skills
- Maximum of 64 flows per domain
- Each flow carries a unique `flow_id`
- Each flow holds a list of `turn_id` pointers referencing the Context Coordinator turns in which it was active
- This one-directional mapping (flows → turns) lets developers reconstruct which turns belong to a flow by inspecting dialogue state snapshots

## Predicting the Belief State

How the belief gets written each turn (the round-3.1 model: flow detection is the authoritative write;
a dedicated intent call is a tie-break only).

```
user turn
    │
    ▼
Assistant ────────────────────────────┬───────────────────────────────────────────
    │                                 │  (parallel)
    ▼                                 ▼
PEX orchestrator                   NLU.think()
forms an initial intent sense      detects the flow over the full FLOW_ONTOLOGY,
in its own reasoning (System 1,    then derives the authoritative intent from
prose — no tool call)              FLOW_ONTOLOGY[flow]['intent'] (System 2) and
    │                              writes the belief
    │                                 │
    ├── intent clear ─────────────────┤
    │   (Research / Draft /           ▼
    │    Revise / Publish)         NLU compares its intent to PEX's choice
    │     │                        (without interrupting PEX)
    │     ▼                           ├── agree  → NLU stays silent
    │   PEX proceeds; its             └── differ → NLU intervenes at one of
    │   selection is NLU's                         PEX's hook points
    │   intent hint
    │
    └── intent unclear (PEX chose Plan, Clarify, or Converse — no real signal, hint stays blank)
          │
          ▼
        Plan / Clarify: PEX calls understand(op='read') and WAITS for NLU's answer
          │
          ▼
        Workflow Planner orchestrates the flows
        (manage_flows: stackon → … → pop)
```

Step by step:

1. **The Assistant starts by calling the PEX agent**, whose first reasoning step forms an initial
   intent sense (System 1). This is prompt guidance in the orchestrator's own reasoning, not a tool
   call — no LLM call is spent on a separate classification pass.
2. **If the intent is clear, PEX proceeds.** NLU runs in parallel as System-2 thinking. It detects the flow and derives
   the authoritative intent from the detected flow. **The hint rule:** when PEX's first pass selects
   a domain intent (Research, Draft, Revise, Publish, Continue), NLU receives that selection as an intent hint
   and narrows its candidate flows to it; when PEX selects Plan, Clarify, or Converse, the hint stays
   blank — PEX's guidance offers no real signal there, so NLU detects over the full set of flows. The
   hint is derived by the **Assistant's code, deterministically** — PEX's selection is
   the flow it committed to the stack, and the code reads that stack top; it is never a tool argument
   the orchestrator has to remember. NLU
   then compares its intent against the one PEX picked — a comparison NLU does on its own, without
   interrupting PEX. If (and only if) there is a discrepancy, PEX has multiple hook points where NLU
   intervenes — see
   [PEX § Policy hook points](../modules/pex.md#policy-hook-points--the-6-hook-sub-agent-framework).
   *Why parallel:* on the common turn the two agree, so the user never waits on a second model call;
   the hook points exist so a wrong first impression is corrected before destructive action.
3. **If the intent is not clear** — PEX chose Plan or Clarify — PEX calls `understand(op='read')`
   and waits for NLU's answer before proceeding. These are the only two intents that block on NLU.
   *Why these two:* Plan decomposes into other flows and Clarify questions the user, so both need the
   settled belief; every other intent can start its read-only work safely while NLU confirms.
4. **PEX orchestrates the flows using the Workflow Planner** — stack ops, fallback, and
   plan sequencing all live in [Workflow Planner](./workflow_planner.md); this document only covers
   the belief that routing reads.

Inside NLU, `think()` implements the authoritative write (round 3.1; the separate `predict()` was
folded into it): `_detect_flow(text, hint)` runs over the hinted intent's flows, or the full ontology
when the hint is blank; the detected flow fixes the intent. Only when the ranked flows are
low-confidence **and** span more than one intent does `_classify_intent` run as a tie-break, followed
by one narrowed re-detect with the classified intent as the `hint`.

## Slot-Filling

Each flow defines slots that must be resolved before the policy can execute. Slots are what NLU
extracts from the user's utterance; they drive ambiguity detection and determine *what* the user wants
to act on (the flow's tools determine *how* — see [Workflow Planner](./workflow_planner.md)).

### Slot Priority

A slot's priority is one of: `required`, `elective`, `optional`.

- **required** — must be filled before execution. Missing → `specific` ambiguity with
  `metadata={'missing': '<slot_name>'}`.
- **elective** — at least one of N elective slots must be filled (choice among alternatives). A flow
  with elective slots must have ≥2 elective options — single-elective is invalid (convert to required
  or optional).
- **optional** — nice-to-have. With a defensible default, commit it inline at policy entry. Without,
  treat absence as OK.

`flow.is_filled()` already encodes "all required filled AND ≥1 elective filled (if any)." Trust it;
don't re-derive.

### Slot Type Hierarchy — 12 Universal + 4 Domain-Specific

Every domain defines exactly **16 slot types**: 12 universal types shared across all assistants, plus
4 domain-specific types selected by that domain. Each domain's `flow_stack/slots.py` contains all 16
class definitions directly (self-contained, no cross-module slot imports). During domain creation,
estimate the 4 novel slots needed; these can be refined during development.

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

`BaseSlot` is the shared abstract parent — it is never used directly. Concrete single-value behavior
lives on the specific subclasses (`ExactSlot`, `CategorySlot`, `LevelSlot` and its descendants).

#### Grounding Slots

**SourceSlot** references existing entities. Each entity is a dict whose fields are domain-specific,
matching the domain's `KEY_ENTITIES`. The hierarchy is built into a single slot.

Each domain defines its own grounding entity vocabulary:

| Domain | Entity fields |
|--------|---------------|
| Dana (Data Analysis) | `{tab, col, row, ver, rel}` — tab=table, col=column, row=row |
| Hugo (Blog Writing) | `{post, sec, snip, chl, ver}` — post=post, sec=section, snip=snippet, chl=channel |

`ver` is a **verified bool**, not a version int — it marks whether the entity was user-approved vs.
agent-predicted. NLU does not predict `ver`; it is set by the grounding layer.

**Canonical name.** A flow's grounding slot is always named `'source'` (matching
`BaseFlow.entity_slot`). One SourceSlot per flow — do not split entity parts into separate slots. Not
every flow requires a grounding slot (e.g., `chat`, `brainstorm`).

**`entity_part` is optional.** `SourceSlot(min_size=1, entity_part='', priority='required')` accepts
any entity type. Setting `entity_part='post'` constrains the slot to that single field.

When a flow needs both a SourceSlot and a FreeTextSlot, name the FreeText something other than
`'source'` (e.g., `'context'`).

**TargetSlot → SourceSlot**: Entities being created (new columns, new rows, new posts).

**RemovalSlot → SourceSlot**: Entities being deleted or removed.

#### Domain-Specific Slots (4 per domain)

Each domain selects 4 additional slot types. Two are typically common options (`ProbabilitySlot`,
`ScoreSlot`) that most domains include; the remaining two are truly unique to the domain. All are real
`BaseSlot` subclasses.

| Domain | Common options | Domain-unique |
|--------|---------------|---------------|
| Dana | ProbabilitySlot, ScoreSlot | **ChartSlot** (chart reference), **FunctionSlot** (executable code) |
| Hugo | ProbabilitySlot, ScoreSlot | **ChannelSlot** (publishing destination), **ImageSlot** (hero image, diagram) |

This 12+4 pattern is the scalable architecture for adding new domains. When creating a new assistant:
1. Copy the 12 universal slot classes from any existing domain's `slots.py`.
2. Select common options (ProbabilitySlot, ScoreSlot) if the domain needs them.
3. Define domain-unique slot types as `BaseSlot` subclasses (total domain-specific = 4).
4. Define the domain's grounding entity vocabulary.

#### CategorySlot Constraints

A CategorySlot's options list must be:
- **Mutually exclusive** — selecting one option rules out all others.
- **At most 8 options** — if you need more than 8, the taxonomy is too fine-grained; consider grouping
  or using FreeTextSlot instead.

#### ExactSlot as Category Extension

When a CategorySlot covers the common cases but users may need values beyond the predefined set, pair
it with an ExactSlot as electives. The user fills either the category (pick from the list) or the
exact slot (provide a custom value):

```python
self.slots = {
    'custom_tone': ExactSlot(priority='elective'),
    'chosen_tone': CategorySlot(['formal', 'casual', 'technical', ...], priority='elective'),
}
```

This preserves structured options for NLU prediction while allowing open-ended input when needed.

### Validation

Validation happens at the dialogue state level — a slot is not marked as filled until its value passes
type validation.

### Slot-Filling Methods

Two `BaseFlow` methods fill slots, distinguished by **prompt scope** and **when they run**:

**`fill_slot_values(values: dict)`** — Bulk fill from a full-flow prediction.

The upstream prompt sees the entire flow (all slots, descriptions, types) and produces a dict of
`{slot_name: value}` pairs for every slot it can extract. The method then routes each value to the
correct slot object based on type:

- Lists → `slot.add_one()` per item (for GroupSlot variants)
- Dicts → `slot.add_one(**value)` (for entity dicts, key-value pairs)
- Scalars → `slot.assign_one(value)` or `slot.value = str(value)`

Also resolves **aliases** (e.g., the LLM says `'post'` but the slot is named `'source'`). Does not
return a value. Used primarily by **NLU** — after `think()`, `contemplate()`, and `react()` predict a
flow, the extracted slots dict is passed here for bulk transfer.

**`fill_slots_by_label(labels: dict)`** — Targeted fill for a specific slot.

The upstream prompt is shorter and more focused: it knows exactly which slot it needs to fill (e.g.,
"Extract the topic the user wants to outline") and produces a single `{slot_name: value}` pair. The
method routes entity-slot values through `extract_entity()` — the entity-extraction hook that domain
parent flows can override for early validation (e.g., checking that a post exists before filling the
source slot). Non-entity slots delegate to `fill_slot_values` for the actual storage. Returns
`is_filled()` status.

Used primarily by **policies in PEX** — when a policy knows a specific slot is missing, it runs a
targeted extraction prompt and fills just that slot:

```python
# In a policy: targeted extraction of a single slot
text = self.engineer.call(history, system="Extract the topic the user wants to outline.")
flow.fill_slots_by_label({'topic': parsed_value})
if not flow.slots['topic'].filled:
    self.ambiguity.recognize('specific', metadata={'missing': 'topic'})
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

Industry NLU draws a line between **entity extraction** (identifying which entity the user is
referring to — e.g. "this post", "the second section") and **slot filling** (writing a value into a
structured variable). Hugo follows this distinction:

| Layer | Action verb | Subject |
|---|---|---|
| NLU | classifies | intent |
| NLU | detects | flow |
| NLU | extracts | entity (`entities are extracted`) |
| NLU | fills | slot (`slots are filled`) |

**Entity extraction** is a sub-task of slot filling, focused on grounding:

- In **NLU**, the `_extract_entities(flow, entity_dict)` helper (called from `_fill_slots`) routes
  entity payload values (`post`, `sec`, `snip`, `chl`) into the flow's grounding slots — its
  `SourceSlot` / `TargetSlot` / `RemovalSlot`, or into the `query` / `word` `ExactSlot` for
  snippet-scoped flows like `find` and `reference`.
- In **flows**, the `BaseFlow.extract_entity(entity)` hook is what `fill_slots_by_label` invokes when
  the slot being filled is the flow's `entity_slot`. Domain parents may override `extract_entity` to
  add validation (e.g. confirming the post exists before committing).

**Failure mapping:**
- `partial` ambiguity = entity extraction failed (the entity the user was referring to could not be
  resolved). The flow's `entity_slot` is still unfilled after extraction attempts.
- `specific` ambiguity = slot filling failed for some other (non-entity) slot.

Both share the same runtime contract — `parts={'missing': <slot_name>, 'entity': <entity_type>?,
'reason': <code>?}` — so consumers reading an artifact's `parts` have a uniform "what was missing?"
key regardless of which sub-task failed.

### Idea (future) — recursive self-verifying slot values

> **Status: future idea, not adopted.** Today a `SourceSlot` grounds a *flat* set of entity parts, each carrying
> a `ver` bool. A legacy data-analysis system generalized this to a **recursive** slot value: a metric held a
> tree of sub-expressions down to leaf clauses, where (a) `ver` **cascaded** — a node is verified only when all
> its children are; (b) a `drop_unverified` pass **pruned** unconfirmed branches; and (c) every node could
> **self-describe** in natural language and **self-render** to SQL. This is the right model for a complex
> artifact built up and confirmed piece-by-piece (a formula, a deeply nested outline). We are **not** building
> it now — flat `{post, sec, snip, chl, ver}` grounding covers the current content domains, and the recursive
> machinery only pays off in formula-heavy domains (e.g. Dana). Recorded so the grounding contract can
> scale to a tree later without re-deriving it.

## Flow Stack block

The dialogue state's `flow_stack` block holds the stacked flows, which manage multiple workflows at once. The
routing/progress layer that drives them is PEX's [Workflow Planner](./workflow_planner.md) — see it for full
details.

## Belief Tools

Shipped 2026-07-08. PEX has **one** tool for reading and consulting the belief, and one tool for the
flow stack — nothing else touches the Dialogue State:

| Tool | Owner | What it does |
|---|---|---|
| `understand(op)` | NLU | PEX's one belief tool. `op='read'` returns the serialized belief (flow, intent, confidence, slots, grounding), joining the parallel NLU thread first — this is where Plan/Clarify wait. `op='think'` re-runs prediction over the latest turn; `op='contemplate'` re-routes over a failed flow. |
| `manage_flows(op)` | Workflow Planner | The flow stack only — ops `update` (flow slots/stage/status, any depth via `flow_name`; a status write of `'Active'` re-runs the flow), `stackon` (push and run — `active` defaults true; `active: false` queues a plan step), `fallback` (replace and run), `pop` (remove Completed AND Invalid flows all at once, then run the surfaced Pending flow). There is no `activate` op — policy execution is runtime-owned. The old belief-fields update op is gone — PEX cannot manipulate the belief, that is NLU's job. |

The intent hint is **deterministic coordination code in the Assistant, never a tool argument**: the
flow PEX committed to the stack IS its first-pass selection, so on an NLU consult the code reads the
stack top — a domain intent (Research/Draft/Revise/Publish) becomes the candidate-narrowing hint;
Plan/Clarify/Converse (or an empty stack) carry no real signal, so the hint stays blank. The
orchestrator prompt carries no hint instructions.

`classify_intent`, `detect_flow`, and `fill_slots` are **internal steps of `NLU.think()`** — not
tools. Detection is the authoritative write (the detected flow fixes the intent via
`FLOW_ONTOLOGY[flow]['intent']`); `_classify_intent` runs only as the low-confidence cross-intent
tie-break (round 3.1).

One flow write is **not** the Dialogue State's: a flow's lifecycle `status` is set by PEX's
`complete_flow` (which requires the grounding checks to pass).

## No Flags

The state carries **no flag block**. The four former flags are gone:

- `natural_birth` — a deterministic property of each flow (user- vs agent-created), held on the flow and
  answered by the [Workflow Planner](./workflow_planner.md); PEX, as the central orchestrator, already has the
  full view and never needs a state flag for it.
- `has_plan` — computed from the agenda (pending sub-flows stacked beneath the active one).
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
