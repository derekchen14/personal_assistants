# Phase 2 — Flow Selection

Design the agent's compositional dact grammar and define all flows. This phase populates the flow catalog in `ontology.py` — the vocabulary the agent uses to understand and act on user requests.

## Context

Flow selection is the most consequential design phase. Every flow becomes a policy the agent executes — a real task a user can request. The compositional grammar ensures flows are structured and bounded: 16 core dacts (8 universal + 8 domain-specific) compose into up to 64 flows per domain.

**Prerequisites**: Phase 1 complete — intents, key entities, persona defined. `ontology.py` stub exists with Intent enum.

**Outputs**: Fully populated `ontology.py` with flow catalog (target 48 flows), seed data file, helper utilities.

**Spec references**: [flow_selection.md](../utilities/flow_selection.md), [dialogue_state.md § Predicted State](../components/dialogue_state.md), [dialogue_state.md § Slot-Filling](../components/dialogue_state.md)

---

## Steps

### Step 1 — Choose Core Dacts (Step C of Builder Process)

Define 16 core dacts: 8 universal (fixed) + 8 domain-specific.

**Universal dacts** (same for all domains):

| Dact | POS | Hex | Role |
|---|---|---|---|
| chat | noun | varies | Non-domain conversation |
| insert | verb | varies | CRUD: create |
| update | verb | varies | CRUD: update |
| delete | verb | varies | CRUD: delete |
| user | adj | varies | User perspective / preferences |
| agent | adj | varies | Agent perspective / actions |
| positive | adj | E | Positive feedback (domain-named: confirm/hot/approve/boost) |
| negative | adj | F | Negative feedback (domain-named: deny/cold/decline/cut) |

**Domain-specific dacts** (8 per domain): typically 4 verbs + 3 entity nouns + 1 adjective/noun. Distribution is flexible.

**Design rules**:
1. No overlap with intent names
2. No near-synonyms (each dact must be clearly distinct)
3. Decompose complex actions into composable primitives (e.g., "cook" → "heat" + "mix")
4. Each flow = a real user task
5. Flows defined by their slots (unique slot signature = unique flow)
6. Flows can invoke flows from any intent

Assign hex digits 0–F to the 16 core dacts. `positive` and `negative` always occupy E and F.

**Worked example** (Chef domain):

| POS | Cores | Hex |
|---|---|---|
| Verbs | heat, search, serve, mix, insert, update, delete | 1, 2, 3, 4, 5, 6, 7 |
| Nouns | chat, recipe, ingredient, step | 0, A, B, C |
| Adjectives | user, agent, wet, hot, cold | 8, 9, D, E, F |

### Step 2 — Compose Flows (Step D of Builder Process)

Combine 2–3 core dacts to form composite flows. The dax code is the sorted hex digits padded to 3 digits:
- 2-component: `{0XY}` (leading zero)
- 3-component: `{XYZ}` (no padding)

**Targets**:
- Draft: 3 flows per intent (21 total)
- v1: 32 flows (good starting point)
- Full: 48 flows (16 below 64 max, leaving room for expansion)
- Distribution: 5–10 flows per intent in the full catalog (minimum 5, target 7)

**Beam search expansion process**:
1. Start with 21 initial flows (3 per intent)
2. Walk Common Composition Patterns — for each, ask "does this domain need this?"
3. Brainstorm 10 candidate flows with description, slots (2–3, max 5), and output block
4. Compare each to existing flows — find its closest neighbor and verify clear differentiation
5. Cull 0–2 early, 5–7 later as design space crowds
6. Repeat until reaching 48 flows
7. After each round, verify: no duplicate slot signatures, every flow is a distinct task, flows are well-scoped

**Common Composition Patterns**:

| Pattern | User task | Composition |
|---|---|---|
| Scoped operation | Act on a specific entity | verb + entity-noun |
| Confirm gate | Approve before destructive action | operation + positive |
| Reject gate | Decline/cancel | operation + negative |
| Save preference | Remember user settings | memory-verb + user |
| Agent explain | Agent explains an entity | read-verb + agent + entity |
| Agent suggest | Agent recommends | agent + positive |
| Copy | Duplicate something | create-verb + read-verb + entity |
| Filter | Narrow results | read-verb + modifier + batch |

**Anti-patterns — reject on sight**:
1. Intent name collision (flow named same as intent)
2. Vague umbrella terms ("strategy", "context" without specifying which kind)
3. Ambiguity handler overlap ("clarify" is handled by the component, not a flow)
4. Same slot signature (two flows with identical slots = same flow)
5. Domain-irrelevant negative feedback
6. Near-synonym flows
7. Agent behavior disguised as a flow
8. Slot masquerading as a flow
9. Compound flow names — flow names must be single tokens (e.g., `browse` not `browse_topics`, `rework` not `deep_revise`). When a single token would collide with an intent name or another flow, pick a synonym
10. Module-level overlap — don't create flows that duplicate module-level functionality (e.g., a "think" flow overlaps with NLU's `think()` method)

---

### Iteration Lessons from Dana & Hugo

The flow catalog is never right on the first pass. Below are patterns observed across two full domain builds (Data Analysis, Blogging), organized by the round of iteration in which they emerged. Use these to shortcut future builds.

**Round 1 — Establish cross-domain patterns first**

Before designing domain-specific flows, copy in the mandatory universal flows. These are the same in every domain:

- *Internal*: `recap` (L1 scratchpad read), `recall` (L2 user prefs), `retrieve` (L3 unvetted business context), `search` (vetted FAQs/curated content — strongly recommended), `calculate` or domain equivalent (quick internal computation)
- *Plan*: A mandatory orchestrator that sequences flows across all domain intents (named `outline` in Dana, `blueprint` in Hugo — pick the domain-appropriate term)
- *Converse*: `chat`, `preference`, `explain` (process transparency), `undo`, approve/reject pair, and a proactive suggestion flow (`recommend`/`suggest`)

Lesson: Starting from universal patterns avoids rediscovering them through trial and error. Domain-specific intents are where the real design work happens.

**Round 2 — Absorb trivially simple flows**

After the initial draft, audit for flows that are just constrained versions of a more general flow. These should be absorbed:

| Absorbed flow | Absorbed into | Reasoning |
|---|---|---|
| `rename` | `update` | Renaming a column is just updating its name — a slot value, not a distinct task |
| `filter` | `query` | Filtering is a WHERE clause — a parameter on query, not a separate action |
| `aggregate` | `query` | SUM/AVG/COUNT are GROUP BY operations — query handles them |
| `trim` | `update` | Trimming whitespace is a single edit — slot masquerading as a flow |
| `sort` | `query` | Sorting is ORDER BY — trivially expressed as a query parameter |

Lesson: If the candidate flow can be fully expressed by setting a parameter on an existing flow, it's a slot, not a flow.

**Round 3 — Place flows by output, not trigger**

Flows sometimes end up under the wrong intent because the *trigger phrase* sounds like one intent but the *output* belongs to another:

| Flow | Wrong intent | Correct intent | Why |
|---|---|---|---|
| `explain` (process) | Research/Report | Converse | Output is agent transparency, not domain analysis |
| `summarize` (artifact) | Converse | Report | Output is grounded to a specific chart/table |
| `validate` | Plan | Clean | Output is corrected data, not a diagnostic plan |
| `retrieve` | Converse | Internal | Output is agent-side context, never shown to user |
| `survey` (platforms) | Research | Publish | Output is platform status, part of publishing workflow |

Lesson: Ask "what does the user get back?" — the output determines the intent, not the phrasing of the request.

**Round 4 — Split flows that serve two distinct axes**

When a single flow name covers two fundamentally different operations, split it:

| Original flow | Split into | Distinction |
|---|---|---|
| `check` (posts) | `check` + `inspect` | Workflow status (draft/published/scheduled) vs content metrics (word count, readability, completeness) |
| `validate` (data) | `validate` + `format` | Valid options from a set (enum constraints) vs correct form (emails, phones, dates) |
| `fill` (nulls) | `fill` + `interpolate` | Row-wise flash fill (carry value down from rows above) vs column-wise inference (infer from neighboring columns, e.g., city→state) |
| `explain` (overloaded) | `explain` + `summarize` | Process transparency ("what did you do?") vs artifact-level analysis ("what does this chart show?") |

Lesson: If a flow's description requires "and/or" to cover its scope, the two halves likely need separate flows. The descriptions should draw explicit boundaries with cross-references (e.g., "use format for correcting form").

**Round 5 — Write descriptions that draw boundaries**

Terse descriptions ("Remove duplicate rows") create ambiguity at NLU time. Every flow description should be at least one full sentence and must:
1. State what the flow *does* with concrete examples
2. State what the flow does *not* do, referencing the neighboring flow by name
3. Include the axis or dimension it operates on, when relevant

Good: *"Flash fill — each cell looks at the row(s) above it to decide the new value. Forward fill, backward fill, rolling average, or carry-down. Operates row-wise; use interpolate when inferring from neighboring columns"*

Bad: *"Fill null cells"*

Lesson: Descriptions are a design tool, not documentation. If you can't draw a clear boundary in the description, the flow is either too vague or overlapping with a neighbor.

**Round 6 — Respect the parallel structure of vetted vs general**

Two recurring parallel pairs appear across every domain. Recognizing this structure early prevents confusion:

| Structured data | Unstructured data | Dimension |
|---|---|---|
| `lookup` — vetted definitions in semantic layer | `search` — vetted FAQs and curated content | Curated, team-approved |
| `query` — general SQL against any data | `retrieve` — general business context from anywhere | Unvetted, broad scope |

Lesson: "Vetted vs general" is a first-class axis. Curated content (lookup, search) has been reviewed by someone on the team. General content (query, retrieve) pulls from any available source without quality guarantees.

**Round 7 — Merge hierarchical entity parts into one SourceSlot**

A SourceSlot entity is `{tab, col, row, ver, rel}` — a single entity already encodes the full hierarchy. Separate slots for different levels of the same hierarchy (e.g., `'table'` + `'column'`, or `'post'` + `'section'`) split what is naturally one grounding reference.

| Before | After | Why |
|---|---|---|
| `'table': SourceSlot(1, 'table')` + `'column': SourceSlot(1, 'column')` | `'source': SourceSlot(1)` | `{tab: 'sales', col: 'revenue'}` is one reference |
| `'post_id': SourceSlot(1, 'post')` + `'section': SourceSlot(1, 'section')` | `'source': SourceSlot(1)` | `{tab: 'my-post', col: 'intro'}` is one reference |
| `'table': SourceSlot(1, 'table')` (alone) | `'source': SourceSlot(1)` | Canonical name is `'source'` |

**When separate SourceSlots are justified:**
- Multiple entities with *different semantic roles* (e.g., CompareFlow's column_a vs column_b → `'source': SourceSlot(2)`)
- Multiple entities of the *same type* at the *same level* (e.g., JoinFlow's left table vs right table)
- TargetSlot/RemovalSlot alongside SourceSlot (different slot types, different purposes)

Lesson: If two SourceSlots describe different levels of the same entity hierarchy, merge them. If they describe genuinely different entities (two tables, two columns being compared), keep them separate — but consider using `SourceSlot(N)` with min_size > 1 instead of separate named slots.

### Step 3 — Assign Intents

Each flow belongs to exactly one intent. Assignment rules:

| If the flow... | Intent |
|---|---|
| Retrieves/reads existing data | Domain read intent |
| Gathers/cleans/prepares data | Domain prepare intent |
| Modifies/creates/processes data | Domain transform intent |
| Creates time-based events or multi-session outputs | Domain schedule intent |
| Open-ended conversation, Q&A | Converse |
| Decomposes into sub-flows | Plan |
| Gathers supporting info invisibly | Internal |

**Composite intent guidelines**:
- One domain verb → that verb's intent applies
- Multiple domain verbs → the primary user-facing action determines intent
- Universal verbs (insert/update/delete) take standard intent unless a domain verb overrides
- Nouns and adjectives specialize but don't override

**Balance check**: Each intent should have 5–10 flows in the full 48-flow catalog (minimum 5, target 7).

### Step 4 — Select Edge Flows

Edge flows are adjacent flows from neighboring intents commonly confused during NLU prediction. Used to expand the candidate set during flow detection.

- Pick 1–3 edge flows per flow
- Prefer flows from adjacent intents
- Composites sharing core dacts are natural candidates
- Start with best guesses, refine from evaluation data (Phase 8)

### Step 5 — Define Slots and Outputs

For each flow, specify:

**Slot signature** (the flow's ground-truth identity):
- `dataset (req)` — required, must be filled before execution
- `column (opt)` — optional, has a reasonable default
- `chart_type (elective)` — pick from a predefined set
- `—` — no slots (context only)

[dataset, column and chart_type] are just examples of slots. The actual slot names should be domain-specific.

**Slot design rules**:
1. 2–3 slots typical, 5 max
2. Name slots after domain entities
3. Default to optional — only `(req)` if literally cannot execute without it
4. Use `(elective)` for enumerated values
5. Unique signatures across the domain

**Output block** (what goes to Display Frame):
- Choose from domain block palette: `table`, `chart`, `card`, `list`, `timer`, `diff`, `terminal`, `form`, `toast`, `confirmation`, `(internal)`
- Internal flows → `(internal)`; Plan flows → `list`; Delete flows → `confirmation`

**Slot type hierarchy** — each domain has exactly 16 slot types (12 universal + 4 domain-specific):

| Type | Description |
|---|---|
| `SourceSlot` | Grounding: existing entities (entity_part: table/column/row, post/section/note) |
| `TargetSlot` | Grounding: new entities being created (→ SourceSlot) |
| `RemovalSlot` | Grounding: entities to remove (→ SourceSlot) |
| `FreeTextSlot` | Open-ended text input |
| `ChecklistSlot` | Ordered steps to check off |
| `ProposalSlot` | Selectable options (≥2 choices) |
| `LevelSlot` | Numeric threshold |
| `ProbabilitySlot` | 0–1 confidence score (→ LevelSlot) |
| `ScoreSlot` | Ranking/sorting score (→ LevelSlot) |
| `PositionSlot` | Non-negative integer position (→ LevelSlot) |
| `CategorySlot` | Exactly one from a predefined set (8 max, mutually exclusive) |
| `ExactSlot` | Specific token or phrase |
| `DictionarySlot` | Key-value pairs |
| `RangeSlot` | Start/stop interval (often date range) |

Plus 4 domain-specific types: 2 common options (ProbabilitySlot, ScoreSlot) + 2 domain-unique (e.g., ChartSlot + FunctionSlot for Dana, PlatformSlot + ImageSlot for Hugo). See [flow_stack.md § Slot Type Hierarchy](../components/flow_stack.md) for the full 12+4 architecture.

### Step 6 — Populate Ontology and Seed Data

Update `ontology.py` with the full flow catalog:

```python
FLOW_CATALOG = {
    'browse': {
        'dax': '{02A}',
        'intent': Intent.SOURCE,        # domain-specific intent name
        'description': 'Browse recipes by category, cuisine, or dietary label',
        'slots': {
            'category': {'type': 'CategorySlot', 'priority': 'optional'},
            'cuisine': {'type': 'CategorySlot', 'priority': 'optional'},
        },
        'output': 'list',
        'edge_flows': ['search', 'inventory'],
        'policy_path': 'policies.source_policies.browse',
    },
    # ... all 48 flows
}
```

Create `database/seed_data.json` with:
- 7 intents (3 universal + 4 domain-specific)
- All dialogue act entries with hex dax codes
- Flow definitions (48 for v1)

Create `utils/helper.py` with:
- `dax2dact(dax_code)` — convert hex code to dact name
- `flow2dax(flow_name)` — convert flow name to hex code
- `find_nearest_valid_option(target, options)` — entity matching
- `find_nearest_lexical(candidate, options)` — Levenshtein distance
- `serialize_for_json(value)` — safe JSON serialization
- `sanitize_entities(entities, valid_set)` — normalize entity references

---

## File Changes Summary

| Action | File | Description |
|---|---|---|
| Modify | `<domain>/schemas/ontology.py` | Full flow catalog, slot type hierarchy, type hierarchy |
| Create | `<domain>/database/seed_data.json` | Intents, dialogue acts, flow definitions |
| Create | `<domain>/utils/helper.py` | dax2dact, flow2dax, entity matching, serialization |

---

## Verification

- [ ] 16 core dacts defined (8 universal + 8 domain-specific) with hex assignments
- [ ] 48 flows composed from core dacts with valid 3-digit hex codes
- [ ] No duplicate dax codes
- [ ] No duplicate flow names
- [ ] No intent name collisions with dact names
- [ ] Each intent has 5–10 flows (minimum 5, target 7)
- [ ] All flows have slot signatures defined (2–3 typical, never more than 5)
- [ ] No two flows share the same slot signature
- [ ] All flows have output blocks from the domain's palette
- [ ] Internal flows use `(internal)` output
- [ ] Plan flows produce `list` output
- [ ] Delete flows produce `confirmation` output
- [ ] 1–3 edge flows selected per flow
- [ ] `FLOW_CATALOG` in `ontology.py` has all 48 entries
- [ ] `seed_data.json` has all intents and flows
- [ ] `helper.py` has dax2dact, flow2dax, and utility functions
- [ ] 16 slot types defined (12 universal + 4 domain-specific)
- [ ] Grounding entities defined for domain (e.g., table/column/row, post/section/note/platform)
- [ ] Grounding slot (when present) named 'source' — one SourceSlot per flow, not split across entity hierarchy levels
- [ ] No separate SourceSlots for different levels of the same entity (e.g., table + column → single source)
- [ ] Multiple same-level references use `SourceSlot(N)` with min_size > 1 (e.g., compare needs 2 columns)
- [ ] CategorySlot options are mutually exclusive, 8 max per slot
