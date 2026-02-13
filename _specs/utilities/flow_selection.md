# Flow Selection

A guide for domain builders on how to design a compositional dact grammar and define flows in `ontology.py`. Lives outside the agent — this is a design-time utility that produces the flow catalog consumed by [Configuration](./configuration.md) at startup.

> **Why all this structure?** Ultimately, the task of NLU is to predict the correct flow (and thus skill) to invoke. All this other stuff around intents, dacts, and key entities is to enforce some structure so that flows are not all over the place. It is all too common for the number of flows to explode as a company wants the agent to do more and more things. The structure of the dacts restricts this by saying that the language of an agent is composed of its core vocabulary. Since the vocabulary is limited, then the domain becomes well-scoped.

## Agent Scoping

Before designing flows, define the agent's scope. An agent is a job role — a specific professional persona with clear boundaries.

**Process:**

1. User provides a description of what the agent should do
2. Help narrow it to a specific job or task domain
3. Ask: "What does the agent NOT do?" to enforce boundaries
4. Reject agents whose scope spans more than one domain

**Good scope:**

- "Data analyst" — analyzes tabular data, creates reports and visualizations
- "Chef" — recipes, cooking techniques, meal planning, nutrition
- "Full-stack web developer" — web dev + DevOps, NOT AI/ML or mobile

**Too broad:**

- "General assistant" — no domain boundaries, can't specialize flows
- "Software engineer + data scientist" — two distinct domains with different tools
- "Marketing + sales" — overlapping but separate job roles

## Builder Process

Building a new agent's flow catalog follows 6 steps:

(a) Choose intents → (b) Choose key entities → (c) Choose core dacts → (d) Choose remaining dacts → (e) Define slots and outputs → (f) Iterate on code to finalize 64 dacts

Steps a–e produce a good first draft. Step f happens during implementation as real usage reveals gaps.

### Step A: Choose Intents

7 total: 3 universal (Converse, Plan, Internal) + 4 domain-specific.

The 4 domain intents map to abstract slots that describe the semantic role of each intent. Names should reflect domain activities, not generic operations:

- Good: "Analyze" (data analysis), "Cook" (cooking), "Deploy" (programming)
- Bad: "Read", "Transform" (too generic, not domain-reflective)

The 4 intents should form a natural pipeline — a sequence of events that represents the typical workflow. Avoid intents that overlap or are too similar.

Each domain names its own 4 intents; the abstract slot provides the semantic criterion but not the name.

**Intent names must not collide with dact names.** A dact named "cook" conflicts with a "Cook" intent. If the domain activity is an intent, find more specific verbs to represent it as dacts (e.g., "heat" and "mix" instead of "cook").

**Decision table for abstract slots:**

| Slot | If the flow... |
|---|---|
| Read | Retrieves or reads existing data without modification |
| Prepare | Gathers, cleans, or prepares data for a future action |
| Transform | Modifies, creates, or processes data |
| Schedule | Creates time-based events or multi-session outputs |
| Converse | Handles open-ended conversation, Q&A, chitchat |
| Plan | Decomposes a request into sub-flows (diagnose/plan) |
| Internal | Gathers supporting info invisibly (no user-facing output) |

### Step B: Choose Key Entities

3 grounding objects that make the task concrete. These are the things you'd ask "which one?" about. They often inspire the types of building blocks to develop. Not necessarily hierarchical — containment is incidental.

### Step C: Choose Core Dacts

16 total: 8 universal (fixed across all domains) + 8 domain-specific.

**Universal dacts:**

| Dact | POS | Role |
|---|---|---|
| chat | noun | Non-domain conversation |
| insert | verb | CRUD: create |
| update | verb | CRUD: update |
| delete | verb | CRUD: delete |
| user | adj | User perspective / preferences |
| agent | adj | Agent perspective / actions |
| positive | adj | Positive feedback |
| negative | adj | Negative feedback |

The `positive` and `negative` dacts always occupy hex E and F with the same semantic role, but each domain assigns its own flow name. The name should evoke positive/negative in context: confirm/deny (data analysis), hot/cold (cooking), approve/decline (programming), boost/cut (marketing).

**Domain-specific dacts** (8 per domain): typically 4 verbs + 3 entity nouns + 1 adjective/noun. The distribution is flexible — e.g., a chef domain has 4V + 1N + 3A.

- **4 domain verbs**: brainstorm "what categories of actions would I want this assistant to take?" One verb should serve as the domain's "read" operation, completing a CRUD-like set alongside insert/update/delete.
- **3 key entity nouns**: come from step B.
- **Remaining slot(s)**: meaningful modifier or additional entity.

Hex digit assignment is fluid — assign digits 0–F to the 16 core dacts in whatever arrangement makes sense for the domain.

**Design rules for domain dacts:**

1. **No overlap with intent names.** If "Cook" is an intent, don't use "cook" as a dact or flow name. Find more specific verbs. This applies to both core dact names and composite flow names — a flow named "plan" under the Plan intent is an auto-reject.
2. **No near-synonyms.** Each dact must represent a clearly distinct action category. "search" and "lookup" are too similar — pick one or replace both with more specific terms.
3. **Decompose complex actions into composable primitives.** Instead of one verb "cook", use "heat" and "mix" — this lets you compose specific methods (grill = heat + hot, steam = heat + wet, bake = heat + mix + ingredient). The compositionality of the grammar is its strength.
4. **Each flow = a real task.** Every flow is a policy the agent executes. It should match something a user would actually ask for — not a theoretical composition. Quality test: MECE (mutually exclusive, collectively exhaustive), well-scoped (not too trivial or too broad).
5. **Flows are defined by their slots.** Each flow is uniquely identified by its slot signature — the set of slots it needs to fill, with their types (required, elective, optional). If two flows have the exact same slots with the same types, they are the same flow. Different slot type assignments (e.g., Slot B required in one flow vs optional in another) make them distinct. This is the ground-truth test for flow uniqueness.
6. **Flows can invoke flows from any intent.** At runtime, any flow may call other flows across all 7 intents — not just Internal or Plan flows. For example, a Source flow like `timing` can invoke a Cook flow to resolve a cooking method's temperature. Plan flows are distinguished by *composing* multi-flow sequences, but cross-intent invocation is available to all flows.

### Step D: Choose Remaining Dacts

Compose 2–3 core dacts to form composite flows. Up to 64 total flows per domain. Start with 3 flows per intent (21 total) as a draft — enough to validate the grammar without overcommitting. Target **48 flows** per domain (16 below the max of 64, leaving breathing room for future additions). In practice, **32 flows** is a good v1 starting point — enough coverage without over-building.

The full catalog (64 flows) should distribute **7-10 flows per intent**. Fewer than 7 → the intent may be too narrow (merge or reclassify). More than 10 → too broad (split or move flows). At 32 flows (starting point), distribute proportionally (~4-5 per intent).

**Beam search process for expanding beyond the initial 21:**

1. Walk the Common Composition Patterns — for each pattern, ask "does this domain need this? What real task does it serve?"
2. **Brainstorm 10 candidate flows.** Each candidate must be fully specified:
   - **Description**: What does the flow accomplish? One sentence that draws the line against similar flows.
   - **Slots**: What information is needed? 2-3 slots typical, 5 max. Mark each as required, elective, or optional. Most flows have reasonable defaults, so few slots are truly required.
   - **Output**: What goes to the Display Frame? (e.g., a table, a confirmation, a generated artifact, a chart.)
3. **Compare each candidate to existing flows.** For each, identify its most similar existing flow and check for a clear point of differentiation: a different slot, a clear task division, or a distinct output. If none, either modify the existing flow to accommodate or skip the candidate and add it to a reject list.
4. Early rounds: expect to drop 0-2 candidates (most ideas are fresh). Later rounds: expect to drop 5-7, even 9 (the remaining design space is crowded).
5. **Brainstorm 10 more candidates** (fully specified), informed by gaps. Compare, cull, repeat until convergence at the target count (48 flows).
6. After each round of culling, verify: no two flows share the same slot signature, every flow maps to a distinct user task, and intent distribution stays balanced.
7. **Human-in-the-loop.** After each culling round, present the full list at that point and ask for feedback on the 3 weakest candidates. If the human keeps all 3, culling quality is high. If the human rejects all 3, culling quality is low — recalibrate. Use this signal to improve future rounds.

**Anti-patterns — flows to reject on sight:**

1. **Intent name collision.** Flow named the same as its intent ("plan" under Plan, "trace" under Trace). Auto-reject.
2. **Vague umbrella terms.** "strategy", "context", "diagnose" without specifying which kind. Real domains have specific types (e.g., 4 types of diagnosis in data analysis: outlier, anomaly, null, typo).
3. **Ambiguity handler overlap.** "clarify" is handled by the Ambiguity Handler component, not a standalone flow. Users don't request clarification — the agent detects ambiguity.
4. **Same slot signature.** Two flows with identical slots (allocate ≈ rebalance). If slots match, it's the same flow — keep one, drop the other.
5. **Domain-irrelevant negative feedback.** "dissuade" in cooking has no domain grounding. Negative-feedback flows must tie to a real domain task (e.g., "warn" in programming = code runs but produces a warning).
6. **Near-synonym flows.** "create" ≈ "scaffold", "scan" ≈ "query", "scorecard" ≈ "dashboard". If a user's utterance could plausibly trigger either, one must go.
7. **Agent behavior disguised as a flow.** Some agent actions (asking for clarification, gathering context) happen within other flows, not as standalone user-triggered tasks. Exception: when the agent's output is the task (e.g., "warn" produces a visible warning).
8. **Slot masquerading as a flow.** If the "flow" is really just a parameter value of another flow, it's a slot — not a flow. Examples: chart type (scatter, histogram) is a slot of `plot`; competitor name is a slot of `research`; time-of-day is a slot of `tune`.

**Good patterns — signs a flow is pulling its weight:**

1. **Broad task coverage.** Flows should cover the full semantic range of user requests, not just literal readings. A flow like `exist` should handle "do I have data about X?" broadly — scanning table names, column headers, and cell values — not just exact keyword matching. If users might phrase a task loosely, the flow should accommodate that.
2. **Similar flows as contemplate() candidates.** Near-similar flows are a feature, not a bug. When NLU `contemplate()` re-predicts, it narrows from 48 flows to 3-5 candidates. Flows that are legitimately similar (e.g., `freeze` vs `safety` in cooking, `read` vs `inspect` in programming) form each other's contemplate search space. If every flow were maximally distinct, contemplate would have no useful candidates.
3. **Temporal distinction.** Pre-action and post-action flows are legitimately different even when they touch the same entity. `review` (pre-launch assessment) and `troubleshoot` (post-launch diagnosis) have different slot signatures, different tools, and different outputs — even though both examine a campaign.
4. **Composed flows.** A flow that calls other flows as sub-steps is distinct from those sub-flows. `post` (review quality → then publish) is a Plan flow that invokes `publish` as a sub-step — it's not a duplicate of `publish`. The composed flow owns the orchestration; the sub-flow owns the action.
5. **Internal validation.** Validation and safety-check flows belong in the Internal intent. `caution` (check if spend is risky) and `safety` (check food safety) are lightweight gates that run before user-facing actions. They don't produce user-visible output — they set flags that other flows consume.
6. **Interaction granularity.** Flows that interact with different system components are distinct even when they seem similar. `read` (reads a file into the display frame) and `inspect` (reads a file into the scratchpad for agent reasoning) produce different outputs and serve different purposes — one is user-facing, the other is agent-facing.
7. **Test affordances.** Testing workflow flows are distinct from production flows. `mock` (generate test doubles) and `implement` (write production code) share a slot signature shape but serve different roles in the development lifecycle. The test flow's output is consumed by test runners, not by the application.

### Step E: Define Slots and Outputs

After finalizing all flows (Step D), fully specify each flow's **slot signature** (what input the flow needs) and **output block** (what goes to the Display Frame). This makes design rule 5 concrete — each flow's slot signature is its ground-truth identity.

**Slot notation** (compact, inline in the flow table):

- `dataset (req)` — required, must be filled before the flow can execute
- `column (opt)` — optional, has a reasonable default (e.g., "all columns")
- `chart_type (elective)` — pick from a predefined set (e.g., bar, line, pie)
- `—` — no slots (flow uses context only, e.g., `think`, `recommend`)

**Slot design rules:**

1. **2-3 slots typical, 5 max.** Most flows need just 2 slots. If a flow needs more than 5, it's probably two flows.
2. **Name slots after domain entities.** Use the key entities from Step B and the domain's natural vocabulary. Data Analysis uses `dataset`, `column`, `row`; Chef uses `recipe`, `ingredient`, `step`; Programmer uses `file`, `function`, `folder`.
3. **Default to optional.** Only mark a slot as `(req)` if the flow literally cannot execute without it. A `filter` needs a `condition`, but a `summarize` can default to "summarize everything."
4. **Use `(elective)` for enumerated values.** When the slot's value comes from a fixed set (chart types, join types, cooking methods), mark it `(elective)`. This signals the Ambiguity Handler to present options rather than ask open-ended questions.
5. **Unique signatures across the domain.** After assigning all slots, verify that no two flows share the same slot set + types. If two flows collide, differentiate by adding an optional slot to one, changing a type (req ↔ opt), or merging the flows.

**Slot patterns by flow type:**

| Flow type | Typical slots | Example |
|---|---|---|
| Single-entity read | entity (req) | `schema`: dataset (req) |
| Browse/search | query (opt), filter (opt) | `browse`: category (opt), cuisine (opt) |
| Multi-entity read | entity (req), grouping (opt) | `aggregate`: dataset (req), group_by (req), metric (elective) |
| Write/create | entity (req), content (req) | `write`: file (req), content (req) |
| Mutate/update | entity (req), field (req), value (req) | `update`: dataset (req), column (req), row (opt), value (req) |
| Delete | entity (req) | `discard`: recipe (req) |
| Agent explain | topic (req) | `explain`: topic (req) |
| Agent suggest | — | `recommend`: — |
| Confirm/reject | action (req) | `approve`: action (req) |
| Plan flow | goal (req), constraints (opt) | `insight`: question (req), dataset (req) |
| Internal flow | — or key (opt) | `think`: — |
| Memory L1 | key (opt) | `recap`: key (opt) |
| Memory L2 | key (opt), scope (opt) | `recall`: key (opt), scope (opt) |
| Memory L3 | key (opt), source (opt) | `context`: key (opt), source (opt) |

**Output blocks:**

Each flow produces exactly one output block — the visual frame type that RES renders for the user. The block set is domain-specific because different domains have different UX surfaces. A data analyst works in a dashboard; a chef controls a robot; a programmer works in a terminal and IDE; a marketer operates through CRMs and ad platforms.

Choose the domain's block palette before assigning outputs. Canonical categories:

| Category | Blocks | Notes |
|---|---|---|
| Data display | `table`, `chart`, `card`, `list` | Not all domains use all four. Chef has no `chart`; Programmer has no `chart` |
| Code display | `diff`, `terminal` | Programmer-specific. `diff` for code changes; `terminal` for command/test output |
| Physical action | `timer` | Chef-specific. Cooking operations with time and temperature |
| Input collection | `form`, `confirmation` | `form` for multi-field input (CRM setup, ad targeting); `confirmation` for approve-before-destructive-action |
| Feedback | `toast` | Brief confirmation message (saved, deleted, deployed) |
| No frame | `(internal)` | Internal flows that gather info invisibly — no user-facing output |

**Output assignment rules:**

1. **Match the UX surface.** A Programmer `patch` produces a `diff` (code change view), not a `card`. A Chef `grill` produces a `timer` (countdown with target temp), not a `table`.
2. **Internal flows always produce `(internal)`.** They gather context for other flows — the user never sees their output directly.
3. **Plan flows always produce `list`.** Plans are multi-step sequences — a list of sub-flows or action items.
4. **Confirm/reject flows produce `toast`.** Brief acknowledgment that the user's approval or rejection was recorded.
5. **Delete flows produce `confirmation`.** Destructive actions require explicit approval before executing.
6. **Flows that call external APIs** (CRM, CI/CD, ad platforms) often produce `form` (to collect API parameters) or `toast` (to confirm the API call succeeded). The output is what RES shows after the API returns — not the API call itself.

**Domain block palettes** (from the worked examples):

| Domain | Blocks |
|---|---|
| Data Analysis | `table`, `chart`, `card`, `list`, `toast`, `confirmation`, `(internal)` |
| Chef | `card`, `list`, `timer`, `toast`, `confirmation`, `(internal)` |
| Programmer | `card`, `list`, `diff`, `terminal`, `toast`, `confirmation`, `(internal)` |
| Digital Marketer | `table`, `chart`, `card`, `list`, `form`, `toast`, `confirmation`, `(internal)` |

**Verification checklist** (run after assigning all slots and outputs):

- [ ] All flows have Slots and Output columns filled
- [ ] Slot counts: 2-3 typical, never more than 5
- [ ] Each flow's slot signature is unique within its domain
- [ ] Output blocks come from the domain's chosen palette
- [ ] Internal flows use `(internal)` output
- [ ] Plan flows produce `list` output
- [ ] Delete flows produce `confirmation` output

## Grammar Design

Traditional dialogue act taxonomies (DAMSL, DIT++, ISO 24617-2) define flat or hierarchical tag sets. Our system composes primitives like parts of speech in a grammar. Inspired by:

- **Frege's compositionality**: the meaning of a composite is determined by its constituents and composition rules
- **Fillmore's frame semantics**: verbs evoke frames; nouns fill roles; modifiers refine
- **Searle's speech acts** (1976): illocutionary acts classified by dimensions — our intents serve a similar role

Each domain defines 16 core dacts occupying hex digits 0–F, distributed across verbs, nouns, and adjectives.

## Compositional Encoding

Composites combine 2–3 core dacts. The dax code is formed by sorting the component hex digits and padding to 3 digits:

- 2-component: `{0XY}` — leading zero is padding
- 3-component: `{XYZ}` — no padding

Canonical notation: `{XXX}` (always 3 digits, digits always sorted, no repeating cores).

**Three identifiers per flow:**

| Identifier | Example | Purpose |
|---|---|---|
| Dact | query + table | Compositional description showing which cores combine |
| Flow name | pivot | Single-token human-readable name (unique per domain) |
| Dax | `{01A}` | Hex code, primary ID used in code |

## Intent Assignment

Each flow (core or composite) belongs to exactly one intent. Assignment follows semantic guidelines:

**Decision table** (domain-specific intents vary by domain):

| If the flow... | Intent |
|---|---|
| Retrieves or reads existing data without modification | Domain read intent |
| Gathers, cleans, or prepares data for a future action | Domain prepare intent |
| Modifies, creates, or processes data | Domain transform intent |
| Creates time-based events or multi-session outputs | Domain schedule intent |
| Handles open-ended conversation, Q&A, chitchat | Converse |
| Decomposes a request into sub-flows (diagnose/plan) | Plan |
| Gathers supporting info invisibly (no user-facing output) | Internal |

**Composite intent guidelines:**

- When a composite contains one domain verb, that verb's intent usually applies
- When multiple domain verbs combine, the verb describing the primary user-facing action determines intent
- Universal verbs (insert/update/delete) take their standard intent unless a domain verb overrides
- Nouns and adjectives specialize the flow but don't typically override the verb-determined intent

**Balance check**: After assigning all flows, verify each intent has 7-10 in the full catalog. Rebalance by reclassifying borderline composites or revisiting intent boundaries.

## Edge Flow Selection

Edge flows are adjacent flows from neighboring intents that are commonly confused during NLU prediction. Used to expand the candidate set during flow prediction majority vote.

- Pick 1–3 flows that a user's utterance might plausibly map to instead of this flow
- Prefer flows from adjacent intents (e.g., a Read flow's edges might include a Prepare flow)
- Based on historical confusion patterns — start with best guesses, refine from evaluation data
- Composites sharing core dacts are natural edge flow candidates

Reference: [NLU](../modules/nlu.md)

## Common Composition Patterns

Recurring patterns across domains, described by role (not specific dact names). Each pattern maps to a real user task. Use these as inspiration when composing flows — not every pattern is expressible in every domain, depending on which core dacts the domain chose.

| Pattern | User task | Composition (by role) | System tie |
|---|---|---|---|
| **Scoped operation** | Act on a specific entity | verb + entity-noun | — |
| **Batch operation** | Act on many at once | verb + batch-modifier | — |
| **Deduplication** | Remove duplicates | delete-verb + entity + batch | — |
| **Preview** | See what will happen first | read-verb + mutation-verb + target | Self-check gate |
| **Confirm gate** | Approve before destructive action | operation + positive | — |
| **Reject gate** | Decline / cancel | operation + negative | — |
| **Save preference** | Remember user settings | memory-verb + user | Memory Manager L2 |
| **Save context** | Remember business info | memory-verb + user + batch | Memory Manager L3 |
| **Lookup cached** | Retrieve from session memory | read-verb + memory-verb | Memory Manager L1 |
| **Retrieve knowledge** | Deep knowledge search | read-verb + memory-verb + agent | Memory Manager L3 |
| **Agent explain** | Agent explains an entity | read-verb + agent + entity | Prompt Engineer |
| **Agent suggest** | Agent recommends action | agent + positive | — |
| **Copy** | Duplicate something | create-verb + read-verb + entity | — |
| **Move** | Relocate something | create-verb + delete-verb | — |
| **Filter** | Narrow or exclude results | read-verb + modifier + batch | — |
| **Sort** | Reorder results | update-verb + modifier + batch | — |
| **Execute** | Commit to running an action | link-verb + positive | PEX |
| **Cancel** | Abort an action | unlink-verb + negative | — |
| **Ambiguous** | Conflicting user signals | positive + negative | Ambiguity Handler |

## Worked Example: Data Analysis

**Scope**: Analyzes tabular data, creates reports and visualizations. NOT: machine learning model training, data engineering pipelines.

**Intents** (pipeline order): Clean → Transform → Analyze → Report

| Domain Intent | Abstract Slot |
|---|---|
| Clean | Read |
| Transform | Prepare |
| Analyze | Transform |
| Report | Schedule |

**Key entities**: table, row, column

**Grammar** (7 verbs, 4 nouns, 5 adjectives):

| POS | Cores | Hex |
|---|---|---|
| Verbs | query, measure, plot, retrieve, insert, update, delete | 1, 2, 3, 4, 5, 6, 7 |
| Nouns | chat, table, row, column | 0, A, B, C |
| Adjectives | user, agent, multiple, confirm, deny | 8, 9, D, E, F |

**Core → intent mapping:**

| Intent | Core Dacts |
|---|---|
| Clean | retrieve, table, row, column |
| Transform | insert, update, delete |
| Analyze | query, measure |
| Report | plot, multiple |
| Converse | chat, user, agent, confirm, deny |
| Plan | composites only |
| Internal | composites only |

**48 flows** (7-9-8-4-7-6-7 by intent):

| Intent | Dact | Flow Name | Dax | Description | Slots | Output |
|---|---|---|---|---|---|---|
| **Clean** | retrieve | retrieve | `{004}` | Fetch a dataset or table into the workspace | dataset (req), source (opt) | table |
| | update | update | `{006}` | Modify cell values or column types in place | dataset (req), column (req), row (opt), value (req) | toast |
| | retrieve + table | schema | `{04A}` | Inspect table structure — column names, types, row count | dataset (req) | card |
| | retrieve + row | sample | `{04B}` | Preview a random or head/tail subset of rows | dataset (req), n (opt) | table |
| | retrieve + column | profile | `{04C}` | Generate summary stats for a single column (min, max, nulls) | dataset (req), column (req) | card |
| | update + confirm | datatype | `{06E}` | Validate and cast column types (string → date, int → float) | dataset (req), column (req), type (elective) | toast |
| | delete + row + multiple | dedupe | `{7BD}` | Remove duplicate rows based on key columns | dataset (req), key_columns (opt) | toast |
| **Transform** | insert | insert | `{005}` | Add a new row or column to the table | dataset (req), column (opt), row (opt) | toast |
| | delete | delete | `{007}` | Remove rows or columns from the table | dataset (req), target (req) | confirmation |
| | insert + table | join | `{05A}` | Combine two tables on a shared key (left, inner, outer) | left (req), right (req), key (req), how (elective) | table |
| | insert + row | append | `{05B}` | Stack rows from one table onto another | source (req), target (req) | toast |
| | update + table | reshape | `{06A}` | Pivot, unpivot, or melt between wide and long format | dataset (req), method (elective) | table |
| | update + column | rename | `{06C}` | Rename one or more columns | dataset (req), column (req), name (req) | toast |
| | insert + update + column | merge | `{56C}` | Combine two columns into one (e.g., first + last → full name) | dataset (req), columns (req), name (req) | toast |
| | insert + column + multiple | split | `{5CD}` | Split one column into multiple (e.g., full name → first, last) | dataset (req), column (req), delimiter (opt) | toast |
| | measure + column + user | define | `{28C}` | Create a named metric formula the user can reuse. ≠ measure (one-time computation) | name (req), formula (req) | toast |
| **Analyze** | query | query | `{001}` | Run a SQL-like query against the data | dataset (req), query (req) | table |
| | measure | measure | `{002}` | Compute a scalar metric (count, sum, average) | dataset (req), column (req), metric (elective) | card |
| | query + table | pivot | `{01A}` | Cross-tabulate rows by two dimensions | dataset (req), row_dim (req), col_dim (req) | table |
| | query + row | filter | `{01B}` | Subset rows matching a condition | dataset (req), condition (req) | table |
| | query + column | aggregate | `{01C}` | Group by a column and compute summary stats per group | dataset (req), group_by (req), metric (elective) | table |
| | measure + table | summarize | `{02A}` | Generate a full statistical summary of a table | dataset (req), depth (opt) | table |
| | query + measure + table | correlate | `{12A}` | Compute correlation or relationship between two columns | dataset (req), column_a (req), column_b (req) | chart |
| | query + retrieve + column | exist | `{14C}` | Check whether data related to a topic exists — scanning table names, column headers, and cell values beyond exact matches | query (req), dataset (opt) | card |
| **Report** | plot | plot | `{003}` | Create a basic chart (bar, line, pie) | dataset (req), chart_type (elective) | chart |
| | measure + plot | trend | `{023}` | Plot values over time and highlight directional patterns | dataset (req), column (req), time_col (req) | chart |
| | plot + table | dashboard | `{03A}` | Compose multiple charts into a saved multi-panel view | dataset (req), charts (req) | chart |
| | measure + plot + multiple | report | `{23D}` | Generate a formatted multi-section document with charts and tables | dataset (req), sections (opt) | list |
| **Converse** | chat | chat | `{000}` | Open-ended conversation not about a specific dataset | topic (opt) | card |
| | query + agent | explain | `{019}` | Agent explains a data concept, metric, or chart. ≠ recommend (suggests action) | topic (req) | card |
| | retrieve + user | preference | `{048}` | Express a personal preference about display or workflow | key (req), value (req) | toast |
| | retrieve + agent | recommend | `{049}` | Agent suggests a next step or analysis. ≠ explain (teaches concepts) | — | card |
| | user + deny | undo | `{08F}` | Reverse the most recent data transformation. ≠ delete (removes data); undo restores previous state | action (opt) | toast |
| | agent + confirm | approve | `{09E}` | Confirm a suggested action before the agent executes it | action (req) | toast |
| | agent + deny | reject | `{09F}` | Decline a suggested action — agent proposes alternatives | action (req), reason (opt) | toast |
| **Plan** | query + retrieve + update | insight | `{146}` | Chain Analyze + Report flows to answer a complex question. ≠ pipeline (chains write flows) | question (req), dataset (req) | list |
| | query + insert + update | pipeline | `{156}` | Chain Transform flows into a reusable ETL sequence. ≠ insight (chains read flows) | steps (req), dataset (req) | list |
| | query + update + column | outlier | `{16C}` | Detect numeric values outside expected ranges. One of 4 diagnosis types | dataset (req), column (req), threshold (opt) | list |
| | query + update + confirm | validate | `{16E}` | Run business rules on a dataset and flag failing rows. ≠ outlier (statistical); validate checks rules | dataset (req), rules (req) | list |
| | retrieve + update + row | blank | `{46B}` | Find and address null or empty cells. One of 4 diagnosis types | dataset (req), column (opt), strategy (elective) | list |
| | retrieve + update + deny | typo | `{46F}` | Detect likely typos or misspellings in text columns. One of 4 diagnosis types | dataset (req), column (opt) | list |
| **Internal** | chat + query + user | recap | `{018}` | Pull a snippet from the current conversation (session scratchpad L1). ≠ peek (checks data state); ≠ recall (retrieves persistent user prefs) | key (opt) | (internal) |
| | user + agent | think | `{089}` | Agent's internal reasoning step | — | (internal) |
| | query + measure + agent | calculate | `{129}` | Perform basic arithmetic or comparison the agent cannot do reliably in its head (e.g., is 9.11 < 9.8) | expression (req) | (internal) |
| | query + retrieve + agent | search | `{149}` | Search across datasets or columns for relevant data | query (req) | (internal) |
| | query + user + agent | peek | `{189}` | Quick internal check of data state before agent responds | dataset (opt) | (internal) |
| | retrieve + user + agent | recall | `{489}` | Retrieve from agent memory (user prefs, L2). ≠ recap (session scratchpad); ≠ context (business docs) | key (opt), scope (opt) | (internal) |
| | retrieve + agent + table | context | `{49A}` | Retrieve from organizational knowledge base (business docs, FAQs, domain rules, L3). ≠ recall (user prefs); ≠ search (scans datasets) | key (opt), source (opt) | (internal) |

**Rejected flows:**

| Flow | Composition | Why rejected | Anti-pattern |
|---|---|---|---|
| scatter | plot + row | Chart type (scatter, bar, histogram) is a slot of `plot` — the user picks a chart type, they don't invoke a different flow | #8 Slot as flow |
| scorecard | measure + plot + table | "Show me a summary view" triggers both scorecard and dashboard — NLU can't distinguish them | #6 Near-synonym |
| context (original) | retrieve + user + agent | "Context" is too broad — what kind? Decomposed into three flows by memory tier: recap (L1 session), recall (L2 user prefs), context (L3 business docs) | #2 Vague umbrella |

## Worked Example: Chef

**Scope**: Recipes, cooking techniques, meal planning, nutrition, food safety. NOT: restaurant management, food photography, catering logistics.

**Intents**: Source → Prep → Cook → Plate

| Domain Intent | Abstract Slot |
|---|---|
| Source | Read |
| Prep | Prepare |
| Cook | Transform |
| Plate | Schedule |

**Key entities**: recipe, ingredient, step

Note: "Cook" is an intent, so no core dact is named "cook". The cooking action decomposes into `heat` and `mix` — two composable primitives that generate specific techniques (grill = heat + hot, steam = heat + wet, bake = heat + mix + ingredient). Similarly, "search" and "lookup" were considered but rejected as near-synonyms; only `search` is kept.

**Grammar** (7 verbs, 4 nouns, 5 adjectives):

| POS | Cores | Hex |
|---|---|---|
| Verbs | heat, search, serve, mix, insert, update, delete | 1, 2, 3, 4, 5, 6, 7 |
| Nouns | chat, recipe, ingredient, step | 0, A, B, C |
| Adjectives | user, agent, wet, hot, cold | 8, 9, D, E, F |

**Core → intent mapping:**

| Intent | Core Dacts |
|---|---|
| Source | search, recipe, ingredient, step |
| Prep | insert, update, delete |
| Cook | heat, mix |
| Plate | serve, wet |
| Converse | chat, user, agent, hot, cold |
| Plan | composites only |
| Internal | composites only |

**48 flows** (7-7-7-7-7-7-6 by intent):

| Intent | Dact | Flow Name | Dax | Description | Slots | Output |
|---|---|---|---|---|---|---|
| **Source** | search | search | `{002}` | Search for a recipe, ingredient, or cooking topic | query (req) | list |
| | search + recipe | browse | `{02A}` | Browse recipes by category, cuisine, or dietary label | category (opt), cuisine (opt) | list |
| | search + ingredient | inventory | `{02B}` | Check what ingredients are currently available | ingredient (opt) | list |
| | search + step | technique | `{02C}` | Look up how to perform a technique (julienne, deglaze, temper) | step (req) | card |
| | heat + search + ingredient | pairing | `{12B}` | Find ingredients that complement each other. ≠ browse (finds recipes, not combos) | ingredient (req) | list |
| | heat + search + step | timing | `{12C}` | Look up cooking times and temperatures for a method | method (req), ingredient (opt) | card |
| | search + user + ingredient | allergen | `{28B}` | Check if ingredients match user's restrictions. ≠ dietary (sets prefs); allergen reads data | ingredient (req), recipe (opt) | card |
| **Prep** | insert | insert | `{005}` | Add a new ingredient or step to a recipe | recipe (req), content (req) | toast |
| | update + recipe | revise | `{06A}` | Edit a recipe's instructions or metadata | recipe (req), field (req) | toast |
| | update + ingredient | substitute | `{06B}` | Swap one ingredient for another (butter → oil) | recipe (req), ingredient (req), replacement (req) | card |
| | update + step | portion | `{06C}` | Scale recipe quantities up or down for a different serving size | recipe (req), servings (req) | card |
| | delete + recipe | discard | `{07A}` | Remove a recipe from the collection | recipe (req) | confirmation |
| | insert + ingredient + step | mise | `{5BC}` | Generate a mise-en-place checklist — all ingredients prepped before cooking | recipe (req), steps (opt) | list |
| | delete + ingredient + step | simplify | `{7BC}` | Remove ingredients and steps to make a recipe easier | recipe (req), target (opt) | list |
| **Cook** | heat + wet | steam | `{01D}` | Cook with moist indirect heat (steamer, covered pot) | ingredient (req), time (opt) | timer |
| | heat + hot | grill | `{01E}` | Cook with direct dry heat (grill, broiler) | ingredient (req), temp (req) | timer |
| | mix + ingredient | blend | `{04B}` | Combine ingredients by mixing (smoothies, batters, sauces) | ingredients (req), method (opt) | timer |
| | heat + mix + ingredient | bake | `{14B}` | Cook in an oven using mixed ingredients (bread, casseroles) | recipe (req), temp (req), time (req) | timer |
| | heat + ingredient + hot | saute | `{1BE}` | Cook quickly in a pan with high heat and fat. ≠ grill (no fat) and boil (liquid) | ingredient (req), temp (req), fat (opt) | timer |
| | heat + step + wet | poach | `{1CD}` | Cook gently submerged in liquid below boiling. ≠ boil (higher temp, vigorous) | ingredient (req), liquid (opt), time (opt) | timer |
| | heat + wet + hot | boil | `{1DE}` | Cook in vigorously bubbling liquid at high heat | ingredient (req), time (opt), temp (opt) | timer |
| **Plate** | serve | serve | `{003}` | Plate and serve a completed dish | dish (req) | card |
| | serve + recipe | present | `{03A}` | Arrange a dish for visual presentation (plating technique) | recipe (req), style (opt) | card |
| | serve + ingredient | garnish | `{03B}` | Add a finishing ingredient for visual or flavor accent | dish (req), ingredient (req) | card |
| | serve + recipe + hot | reheat | `{3AE}` | Warm a previously cooked dish before serving. ≠ grill/saute (cook raw food) | dish (req), method (opt) | timer |
| | serve + recipe + cold | chill | `{3AF}` | Cool a dish to serving temperature (gazpacho, salad) | dish (req), temp (opt) | timer |
| | serve + ingredient + cold | store | `{3BF}` | Package and refrigerate leftovers with storage guidance. ≠ freeze (preserves a component) | dish (req), container (opt) | card |
| | serve + step + cold | freeze | `{3CF}` | Freeze a component for later use (ice cream base, stock) | ingredient (req), method (opt) | card |
| **Converse** | chat | chat | `{000}` | Open-ended food conversation not about a specific recipe | topic (opt) | card |
| | heat + agent | teach | `{019}` | Agent explains a cooking concept or food science principle. ≠ suggest (proposes action) | concept (req) | card |
| | search + user | preference | `{028}` | Express food preferences (spicy, no raw fish, etc.) | key (req), value (req) | toast |
| | search + agent | suggest | `{029}` | Agent recommends a recipe or technique. ≠ teach (explains why) | — | card |
| | user + ingredient | dietary | `{08B}` | Set dietary restrictions or allergies (gluten-free, nut allergy). ≠ allergen (checks data) | restriction (req) | toast |
| | agent + hot | endorse | `{09E}` | Approve the agent's recipe or substitution suggestion | action (req) | toast |
| | agent + cold | decline | `{09F}` | Decline the agent's suggestion — agent proposes alternatives | action (req), reason (opt) | toast |
| **Plan** | search + insert + ingredient | shopping | `{25B}` | Generate a shopping list from selected recipes | recipes (req) | list |
| | search + update + recipe | menu | `{26A}` | Plan meals across multiple days. ≠ feast (single-event multi-course) | days (req), servings (opt) | list |
| | mix + update + recipe | batch | `{46A}` | Plan a batch-cooking session reusing shared ingredients across recipes | recipes (req), schedule (opt) | list |
| | mix + update + step | review | `{46C}` | Walk through recipe steps and flag timing or technique issues | recipe (req), focus (opt) | list |
| | mix + update + cold | troubleshoot | `{46F}` | Diagnose why a dish turned out wrong and suggest corrections | dish (req), symptom (req) | list |
| | mix + user + agent | consider | `{489}` | Weigh multiple options by combining Source and Prep flows before presenting a recommendation | goal (req) | list |
| | insert + update + recipe | feast | `{56A}` | Plan a multi-course meal for one event with prep timing. ≠ menu (multi-day planning) | recipes (req), occasion (opt) | list |
| **Internal** | chat + heat + user | recap | `{018}` | Pull a snippet from the current conversation (session scratchpad L1). ≠ recall (user prefs); ≠ context (cooking knowledge) | key (opt) | (internal) |
| | user + agent | think | `{089}` | Agent's internal reasoning step | — | (internal) |
| | heat + user + agent | safety | `{189}` | Check food safety requirements (internal temps, storage times) | ingredient (req), method (opt), temp (opt) | (internal) |
| | search + user + agent | recall | `{289}` | Retrieve stored user preferences (dietary rules, flavor prefs, L2). ≠ recap (session scratchpad); ≠ context (cooking knowledge) | key (opt), scope (opt) | (internal) |
| | search + agent + recipe | context | `{29A}` | Retrieve from cooking knowledge base (techniques, food science, cultural context, L3). ≠ recall (user prefs); ≠ pantry (ingredient inventory) | key (opt), source (opt) | (internal) |
| | search + recipe + ingredient | pantry | `{2AB}` | Internally check pantry inventory before making suggestions | ingredient (opt), recipe (opt) | (internal) |

**Rejected flows:**

| Flow | Composition | Why rejected | Anti-pattern |
|---|---|---|---|
| dissuade | agent + cold | "Don't eat that" isn't a cooking task — negative feedback flows must tie to a real domain action (cf. `warn` in programming, where the code actually produces a warning) | #5 Domain-irrelevant |
| plan | search + mix + step | Flow named "plan" under the Plan intent — auto-reject. The cooking action decomposes into specific Plan flows like menu, batch, and shopping | #1 Intent collision |
| clarify | chat + heat + user | Users don't request clarification — the agent detects ambiguity and asks. Handled by the Ambiguity Handler component, not a standalone flow | #3 Ambiguity handler |

## Worked Example: Programmer

**Scope**: Full-stack web development + DevOps (Kubernetes, Terraform, Docker). NOT: AI/ML, hardware, Rust, mobile, security.

**Intents** (pipeline order): Trace → Code → Refactor → Deploy

| Domain Intent | Abstract Slot |
|---|---|
| Trace | Read |
| Code | Prepare |
| Refactor | Transform |
| Deploy | Schedule |

**Key entities**: folder, file, function

Note: domain verbs are `read`, `write`, `run`, `ship` — not "trace" or "code", which collide with the Trace and Code intent names.

**Grammar** (7 verbs, 4 nouns, 5 adjectives):

| POS | Cores | Hex |
|---|---|---|
| Verbs | read, write, run, ship, insert, update, delete | 1, 2, 3, 4, 5, 6, 7 |
| Nouns | chat, folder, file, function | 0, A, B, C |
| Adjectives | user, agent, local, approve, decline | 8, 9, D, E, F |

**Core → intent mapping:**

| Intent | Core Dacts |
|---|---|
| Trace | read, folder, file, function |
| Code | write, insert, update, delete |
| Refactor | run |
| Deploy | ship, local |
| Converse | chat, user, agent, approve, decline |
| Plan | composites only |
| Internal | composites only |

**48 flows** (7-7-6-7-7-6-8 by intent):

| Intent | Dact | Flow Name | Dax | Description | Slots | Output |
|---|---|---|---|---|---|---|
| **Trace** | read | read | `{001}` | Read a file or code snippet | file (req) | card |
| | read + file | inspect | `{01B}` | Examine a specific file's contents in detail | file (req), line (opt) | card |
| | read + function | diff | `{01C}` | Show recent changes to a function or file. ≠ inspect (current state) | file (req), range (opt) | diff |
| | read + local | history | `{01D}` | Show version control log for a file or project | file (req), branch (opt) | list |
| | read + folder + function | stacktrace | `{1AC}` | Trace a call stack across folders and functions to find error origin | error (req) | list |
| | read + file + function | deps | `{1BC}` | Map import chains and dependency relationships. ≠ stacktrace (runtime); deps traces static imports | file (req), depth (opt) | list |
| | read + file + local | log | `{1BD}` | Read application or server log files. ≠ history (VCS log); log reads runtime output | file (req), filter (opt) | terminal |
| **Code** | write | write | `{002}` | Write code — a function, class, or module | file (req), content (req) | diff |
| | write + function | mock | `{02C}` | Generate a test double for unit testing — stubs, mocks, or fixtures. ≠ implement (production code) | function (req), signature (opt) | diff |
| | insert + folder | config | `{05A}` | Create or update project configuration files (package.json, tsconfig) | file (req), format (elective) | diff |
| | insert + file | scaffold | `{05B}` | Generate boilerplate project structure from a template | template (req), folder (opt) | list |
| | insert + function | implement | `{05C}` | Write the full implementation of a function from a spec or stub | function (req), spec (opt) | diff |
| | update + file | migrate | `{06B}` | Generate a database or schema migration file | file (req), version (opt) | diff |
| | update + function | patch | `{06C}` | Fix a specific function — targeted code edit. ≠ implement (writes new code) | function (req), fix (req) | diff |
| **Refactor** | run | run | `{003}` | Run a single command or script | command (req) | terminal |
| | run + file | execute | `{03B}` | Run a multi-step sequence or remote procedure. ≠ run (single command) | file (req), args (opt) | terminal |
| | run + function | test | `{03C}` | Run tests for a function or module | target (req), suite (opt) | terminal |
| | write + run + folder | typecheck | `{23A}` | Run type checker across the project. ≠ lint (style rules); typecheck validates types | folder (opt) | terminal |
| | write + run + file | lint | `{23B}` | Run linter to enforce code style and catch common errors | file (opt) | terminal |
| | write + delete + function | prune | `{27C}` | Find and remove dead code, unused imports, or unreachable functions | folder (opt), scope (opt) | diff |
| **Deploy** | ship | ship | `{004}` | Deploy the current build to production | target (req) | toast |
| | ship + file | bundle | `{04B}` | Package files into a deployable artifact (Docker image, zip) | file (req), format (opt) | toast |
| | ship + local | release | `{04D}` | Tag and publish a versioned release locally | version (req), tag (opt) | toast |
| | ship + decline | rollback | `{04F}` | Revert to the previous deployment version. ≠ release (moves forward) | version (req) | confirmation |
| | run + ship + file | pipeline | `{34B}` | Configure or trigger a CI/CD pipeline | config (req), trigger (opt) | card |
| | run + ship + function | monitor | `{34C}` | Set up or check health monitors for a deployed service | service (req), metric (opt) | card |
| | run + ship + local | stage | `{34D}` | Deploy to a staging environment for pre-production testing | target (req), env (opt) | toast |
| **Converse** | chat | chat | `{000}` | Open-ended conversation not about a specific codebase | topic (opt) | card |
| | read + user | preference | `{018}` | Set coding style preferences (indentation, naming, frameworks) | key (req), value (req) | toast |
| | read + agent | explain | `{019}` | Agent explains how code works. ≠ critique (judges quality) | topic (req) | card |
| | write + agent | critique | `{029}` | Agent reviews code quality and suggests improvements. ≠ explain (describes behavior) | file (req), scope (opt) | diff |
| | user + decline | decline | `{08F}` | Decline a proposed code change from the agent | action (req), reason (opt) | toast |
| | agent + approve | endorse | `{09E}` | Approve a proposed code change | action (req) | toast |
| | agent + decline | warn | `{09F}` | Agent flags code that runs but may have issues (no-op, edge case, deprecation) | issue (req) | card |
| **Plan** | read + write + function | feature | `{12C}` | Plan implementation of a new feature across multiple functions | spec (req), scope (opt) | list |
| | read + update + file | debug | `{16B}` | Plan a debugging investigation — which files to examine, what to log | issue (req), file (opt) | list |
| | read + update + function | fix | `{16C}` | Plan a multi-step bug fix spanning several functions. ≠ debug (investigates); fix plans the repair | bug (req), functions (opt) | list |
| | read + update + decline | diagnose | `{16F}` | Narrow down the root cause of a failure. ≠ debug (broad); diagnose reaches a conclusion | error (req), context (opt) | list |
| | write + update + file | debt | `{26B}` | Identify and prioritize technical debt items for resolution | area (req), priority (opt) | list |
| | run + update + function | coverage | `{36C}` | Plan test coverage — which functions need tests, what edge cases. ≠ test (runs tests) | target (req), depth (opt) | list |
| **Internal** | read + folder | browse | `{01A}` | Internally explore source code folder structure before acting. ≠ scan (checks deployment state) | folder (opt), depth (opt) | (internal) |
| | user + agent | think | `{089}` | Agent's internal reasoning step | — | (internal) |
| | read + run + agent | benchmark | `{139}` | Internally measure current code performance to inform recommendations. ≠ evaluate (tests proposed changes); benchmark measures existing state | target (req), metric (opt) | (internal) |
| | read + ship + agent | scan | `{149}` | Scan deployment state (Docker, CI/CD, infra) before recommendations. ≠ browse (explores source code structure) | env (opt) | (internal) |
| | read + user + agent | recall | `{189}` | Retrieve stored user preferences (coding style, frameworks, L2). ≠ preference (user sets prefs); recall retrieves them internally | key (opt), scope (opt) | (internal) |
| | read + user + local | recap | `{18D}` | Pull a snippet from the current conversation (session scratchpad L1). ≠ recall (user prefs); ≠ context (project docs) | key (opt) | (internal) |
| | write + run + agent | evaluate | `{239}` | Internally run the agent's proposed change through tests before suggesting. ≠ test (user runs existing suite); evaluate validates agent-generated code | change (req), tests (opt) | (internal) |
| | ship + agent + folder | context | `{49A}` | Retrieve from project knowledge base (architecture docs, conventions, L3). ≠ recall (user prefs); ≠ browse (explores current structure) | key (opt), source (opt) | (internal) |

**Rejected flows:**

| Flow | Composition | Why rejected | Anti-pattern |
|---|---|---|---|
| refactor_plan | read + write + update | "refactor" collides with the Refactor intent name, and multi-word flow names violate naming convention. The refactoring task is covered by feature and debt | #1 Intent collision |
| analyze | read + write + agent | "Analyze code patterns" is what the agent does within critique and explain — not a distinct task a user requests. No clear output that distinguishes it | #7 Agent behavior |

## Worked Example: Digital Marketer

**Scope**: SEO, paid ads, social media, email marketing, analytics. NOT: blog posts/long-form content (that's the blogger assistant).

**Intents** (pipeline order): Scout → Craft → Launch → Optimize

| Domain Intent | Abstract Slot |
|---|---|
| Scout | Read |
| Craft | Prepare |
| Launch | Transform |
| Optimize | Schedule |

**Key entities**: campaign, ad, channel

**Grammar** (7 verbs, 4 nouns, 5 adjectives):

| POS | Cores | Hex |
|---|---|---|
| Verbs | review, draft, post, tune, insert, update, delete | 1, 2, 3, 4, 5, 6, 7 |
| Nouns | chat, campaign, ad, channel | 0, A, B, C |
| Adjectives | user, agent, paid, boost, cut | 8, 9, D, E, F |

**Core → intent mapping:**

| Intent | Core Dacts |
|---|---|
| Scout | review, campaign, ad, channel |
| Craft | draft, insert, update, delete |
| Launch | post |
| Optimize | tune, paid |
| Converse | chat, user, agent, boost, cut |
| Plan | composites only |
| Internal | composites only |

**48 flows** (6-7-6-6-7-8-8 by intent):

| Intent | Dact | Flow Name | Dax | Description | Slots | Output |
|---|---|---|---|---|---|---|
| **Scout** | review | review | `{001}` | Review overall campaign or marketing performance | campaign (opt) | card |
| | review + campaign | sentiment | `{01A}` | Analyze audience sentiment around a campaign. ≠ benchmark (compares channels) | campaign (req) | chart |
| | review + ad | audit | `{01B}` | Audit a specific ad for compliance, quality, or performance | ad (req) | card |
| | review + channel | benchmark | `{01C}` | Compare performance across channels or against industry standards | channel (req), metric (opt) | table |
| | review + paid | budget | `{01D}` | Review spend and budget utilization across paid channels | campaign (opt), date_range (opt) | table |
| | review + ad + channel | funnel | `{1BC}` | Map the conversion funnel from impression to purchase. ≠ benchmark (compares); funnel traces the journey | campaign (req), channel (opt) | chart |
| **Craft** | draft | draft | `{002}` | Write initial ad copy or marketing content | channel (req), topic (req) | card |
| | draft + campaign | brief | `{02A}` | Create a campaign brief — objectives, audience, messaging strategy | campaign (req), audience (req) | card |
| | draft + ad | copywrite | `{02B}` | Write polished ad copy for a specific ad unit | ad (req), channel (opt) | card |
| | draft + channel | headline | `{02C}` | Write headline variations for a channel's format. ≠ copywrite (full ad copy) | channel (req), topic (opt) | list |
| | insert + ad | creative | `{05B}` | Finalize ad creative for delivery to the ad platform. ≠ copywrite (writes content); creative packages for launch | ad (req), format (elective) | card |
| | draft + insert + campaign | landing | `{25A}` | Create landing page copy and structure tied to a campaign | campaign (req), offer (opt) | card |
| | insert + campaign + paid | sponsor | `{5AD}` | Set up a sponsored/paid placement for a campaign | campaign (req), channel (req), budget (req) | form |
| **Launch** | post + campaign | schedule | `{03A}` | Schedule campaign posts for specific dates and times. ≠ publish (publishes now) | campaign (req), date (req) | toast |
| | post + ad | promote | `{03B}` | Boost or promote a specific ad with paid spend | ad (req), budget (req) | form |
| | post + channel | publish | `{03C}` | Publish content to a specific channel (blog, newsletter, social) | content (req), channel (req) | toast |
| | post + campaign + channel | syndicate | `{3AC}` | Distribute a campaign across multiple channels. ≠ blast (single ad) | campaign (req), channels (req) | toast |
| | post + ad + channel | blast | `{3BC}` | Push a single ad creative identically across all channels. ≠ syndicate (distributes a whole campaign, adapted per channel) | ad (req), channels (req) | toast |
| | post + ad + paid | retarget | `{3BD}` | Launch retargeting ads for users who visited but didn't convert. ≠ promote (new audiences) | ad (req), audience (req) | form |
| **Optimize** | tune | tune | `{004}` | Adjust campaign settings or parameters | campaign (req), parameter (req) | toast |
| | tune + ad | split | `{04B}` | Run an A/B split test on ad variants | ad (req), variants (req) | form |
| | tune + paid | bid | `{04D}` | Adjust bidding strategy for paid placements | channel (req), strategy (elective) | form |
| | tune + cut | cap | `{04F}` | Set frequency caps to limit how often users see an ad | ad (req), frequency (req) | toast |
| | tune + campaign + channel | targeting | `{4AC}` | Refine audience targeting criteria (demographics, interests, behaviors). ≠ allocate (moves money between channels); targeting refines who sees the ads | campaign (req), audience (req), criteria (opt) | form |
| | tune + channel + paid | allocate | `{4CD}` | Distribute budget across channels by performance. ≠ bid (per-placement); allocate moves money between channels | channels (req), budget (req) | table |
| **Converse** | chat | chat | `{000}` | Open-ended marketing conversation | topic (opt) | card |
| | review + user | preference | `{018}` | Set brand voice, tone, and style preferences. ≠ goal (sets metrics) | key (req), value (req) | toast |
| | review + agent | recommend | `{019}` | Agent suggests a strategy or next step. ≠ critique (evaluates existing work) | — | card |
| | draft + user | goal | `{028}` | Define campaign KPIs and success metrics (CTR, ROAS). ≠ preference (sets style/tone) | campaign (req), kpi (req) | toast |
| | draft + agent | critique | `{029}` | Agent evaluates existing ad copy or campaign structure. ≠ recommend (proposes new things) | ad (opt) | card |
| | user + cut | reject | `{08F}` | Decline a proposed change from the agent | action (req), reason (opt) | toast |
| | agent + boost | endorse | `{09E}` | Approve a proposed change from the agent | action (req) | toast |
| **Plan** | review + draft + campaign | roadmap | `{12A}` | Plan a multi-campaign marketing strategy over time | goal (req), timeline (opt) | list |
| | review + insert + paid | forecast | `{15D}` | Forecast future performance and plan budget allocation. ≠ budget (reviews past spend); forecast predicts forward | campaign (opt), budget (opt) | list |
| | review + update + campaign | assess | `{16A}` | Evaluate a campaign's health and recommend adjustments | campaign (req), metrics (opt) | list |
| | review + update + cut | diagnose | `{16F}` | Identify why a campaign is underperforming and pinpoint the cause | campaign (req), issue (req) | list |
| | draft + post + campaign | rollout | `{23A}` | Plan the staged rollout of a campaign launch — timing, channels, creative | campaign (req), phases (req) | list |
| | draft + update + campaign | calendar | `{26A}` | Build a content calendar mapping posts to dates. ≠ roadmap (strategic); calendar is tactical scheduling | channel (opt), date_range (opt) | list |
| | draft + update + ad | experiment | `{26B}` | Design A/B test plan with variants and metrics. ≠ split (runs test); experiment plans the design | ad (req), hypothesis (req) | list |
| | review + post + channel | post | `{13C}` | Review content quality then publish — a composed flow that calls publish after review passes. ≠ publish (single-step); post plans and executes | content (req), channel (opt) | list |
| **Internal** | chat + tune + user | recap | `{048}` | Pull a snippet from the current conversation (session scratchpad L1). ≠ recall (user prefs); ≠ context (business docs) | key (opt) | (internal) |
| | user + agent | think | `{089}` | Agent's internal reasoning step | — | (internal) |
| | agent + cut | caution | `{09F}` | Internally check if a spend amount or action is risky before proceeding | action (req), threshold (opt) | (internal) |
| | review + draft + agent | research | `{129}` | Research market trends, competitor data, or industry benchmarks before suggesting (competitor = slot). ≠ context (retrieves stored knowledge); research gathers ad-hoc market intelligence | query (req), market (opt) | (internal) |
| | review + tune + agent | analyze | `{149}` | Internally analyze optimization data to inform tuning | campaign (req), dimension (opt) | (internal) |
| | review + user + agent | recall | `{189}` | Retrieve stored user preferences (brand voice, KPI targets, L2). ≠ preference (user sets prefs); recall retrieves them internally | key (opt), scope (opt) | (internal) |
| | draft + tune + agent | score | `{249}` | Score draft creative quality before presenting to the user. ≠ audit (user checks live ad); score is agent pre-check on drafts | draft (req), criteria (opt) | (internal) |
| | tune + agent + campaign | context | `{49A}` | Retrieve from business knowledge base (brand guidelines, market research, L3). ≠ recall (user prefs); ≠ research (ad-hoc market trends) | key (opt), source (opt) | (internal) |

**Rejected flows:**

| Flow | Composition | Why rejected | Anti-pattern |
|---|---|---|---|
| daypart | tune + ad + channel | Time-of-day targeting is a parameter you set within `tune`, not a separate task — "optimize delivery for mornings" is just tuning with a time slot filled in | #8 Slot as flow |
| rebalance | tune + channel + paid | Identical slot signature to `allocate` — both need the same inputs (channels + budget amounts) and produce the same output. If slots match, it's the same flow | #4 Same slots |
