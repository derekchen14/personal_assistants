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
- Distribution: 7–10 flows per intent in the full catalog

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

**Balance check**: Each intent should have 7–10 flows in the full 48-flow catalog.

### Step 4 — Select Edge Flows

Edge flows are adjacent flows from neighboring intents commonly confused during NLU prediction. Used to expand the candidate set during flow prediction.

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

**Slot type hierarchy** — each domain has exactly 16 slot types (~12 universal + 4 domain-specific):

| Type | Description |
|---|---|
| `BaseSlot` | Single value (base class) |
| `GroupSlot` | List of values |
| `SourceSlot` | Group with min_size |
| `TargetSlot` | Destination entity |
| `RemovalSlot` | Entity to remove |
| `FreeTextSlot` | Open-ended text |
| `LevelSlot` | Numeric with range |
| `RangeSlot` | Min/max pair |
| `ExactSlot` | Must match precisely |
| `DictionarySlot` | Key-value pairs |
| `CategorySlot` | Value from category set |
| `ChecklistSlot` | Multi-select from list |

Plus 4 domain-specific types (e.g., FormulaSlot, ChartSlot for data analysis).

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

## Files to Modify/Create

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
- [ ] Each intent has 7–10 flows (balanced distribution)
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
- [ ] 16 slot types defined (~12 universal + 4 domain-specific)
