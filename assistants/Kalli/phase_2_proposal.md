# Phase 2 Proposal — Kalli Flow Catalog

Draft for review. Once approved, this populates `ontology.py` and `seed_data.json`.

---

## Core Dacts (16)

| POS | Cores | Hex | Notes |
|---|---|---|---|
| **Verbs** | browse | 1 | User explores/reads information |
| | describe | 2 | User provides/defines information |
| | iterate | 3 | User reviews/refines a design proposal |
| | export | 4 | User triggers output generation |
| | insert | 5 | CRUD: create new entry |
| | update | 6 | CRUD: modify existing |
| | delete | 7 | CRUD: remove |
| **Nouns** | chat | 0 | Non-domain conversation |
| | config | A | The assistant config being built |
| | lesson | B | Learnings and patterns |
| | spec | C | Spec files from `_specs/` |
| **Adjectives** | user | 8 | User perspective/preferences |
| | agent | 9 | Agent perspective/actions |
| | draft | D | Partial/in-progress state |
| | accept | E | Positive feedback |
| | reject | F | Negative feedback |

**Positive/negative naming**: accept/reject (approve/decline a proposal — fits Kalli's collaborative design workflow).

---

## Block Palette

Kalli's display types (what RES renders):

| Block | Use case | Inline? |
|---|---|---|
| card | Explanations, config sections, spec excerpts, previews | No (panel) |
| list | Multiple items: flows, intents, entities, plans, validation results | No (panel) |
| form | Collecting user input: scope, persona, intent definitions | No (panel) |
| toast | Small confirmations: logged lesson, approved flow | Yes (inline) |
| confirmation | Before destructive/irreversible actions: delete, export | Yes (inline) |

---

## Flow Catalog (48 flows)

### Explore — 8 flows

User browses specs, checks progress, asks architecture questions.

| # | Composition | Flow | Dax | Description | Slots | Output | Edge Flows |
|---|---|---|---|---|---|---|---|
| 1 | browse + config | status | {01A} | View current state of the config being built | section (opt) | card | summarize, inspect |
| 2 | browse + lesson | review_lessons | {01B} | Browse stored lessons and patterns | topic (opt), count (opt) | list | recall, lookup |
| 3 | browse + spec | lookup | {01C} | Look up a specific spec file or section | spec_name (req), section (opt) | card | explain, read_spec |
| 4 | browse + user + spec | recommend | {18C} | Find specs relevant to the user's target domain | domain (req) | list | lookup, research |
| 5 | browse + agent + config | summarize | {19A} | Agent summarizes overall build progress | — | card | status, inspect |
| 6 | browse + agent + spec | explain | {19C} | Agent explains an architecture concept | concept (req) | card | lookup, chat |
| 7 | browse + config + draft | inspect | {1AD} | Inspect a draft config section in detail | section (req), detail_level (elective: summary\|full) | card | status, compare |
| 8 | browse + spec + draft | compare | {1CD} | Compare draft config section against spec requirements | section (req) | card | validate, inspect |

### Provide — 8 flows

User gives project information: scope, intents, entities, persona.

| # | Composition | Flow | Dax | Description | Slots | Output | Edge Flows |
|---|---|---|---|---|---|---|---|
| 9 | describe + config | scope | {02A} | Define assistant scope — name, task, boundaries | name (req), task (req), boundaries (opt) | form | persona, entity |
| 10 | describe + lesson | teach | {02B} | Share a learning or pattern for Kalli to remember | pattern (req), context (opt) | toast | log, feedback |
| 11 | insert + config | intent | {05A} | Provide a domain intent definition | intent_name (req), description (req), abstract_slot (elective: Read\|Prepare\|Transform\|Schedule) | form | entity, revise |
| 12 | insert + lesson | log | {05B} | Log a new lesson or convention | content (req), category (elective: bug\|pattern\|decision\|convention) | toast | teach, style |
| 13 | update + config | revise | {06A} | Update a previously defined config section | section (req), field (req), value (req) | toast | remove, refine |
| 14 | delete + config | remove | {07A} | Remove a config section or entry | section (req) | confirmation | revise, decline |
| 15 | describe + config + user | persona | {28A} | Define persona preferences — tone, name, response style, colors | tone (elective), name (req), response_style (elective), colors (opt) | form | scope, entity |
| 16 | describe + config + spec | entity | {2AC} | Define key entities grounded in domain concepts | entities (req) | form | intent, scope |

### Design — 8 flows

User iterates on the dact grammar and flow catalog with Kalli.

| # | Composition | Flow | Dax | Description | Slots | Output | Edge Flows |
|---|---|---|---|---|---|---|---|
| 17 | iterate + config | propose | {03A} | Review proposed core dacts for the domain | — | list | compose, suggest_flow |
| 18 | iterate + spec | compose | {03C} | Review composed flows generated from dact grammar | intent_filter (opt) | list | propose, validate |
| 19 | iterate + draft | revise_flow | {03D} | Revise an in-progress flow design | flow_name (req), field (req) | card | refine, compose |
| 20 | config + accept | approve | {0AE} | Approve a proposed flow or dact | flow_name (req) | toast | endorse, decline |
| 21 | config + reject | decline | {0AF} | Reject a proposed flow or dact with reason | flow_name (req), reason (opt) | toast | dismiss, approve |
| 22 | iterate + agent + config | suggest_flow | {39A} | Agent suggests new flows; user reviews | intent_hint (opt) | card | propose, compose |
| 23 | iterate + config + draft | refine | {3AD} | Refine a flow's slot signature or output type | flow_name (req), slot_name (opt), change (opt) | card | revise_flow, validate |
| 24 | iterate + config + spec | validate | {3AC} | Validate current flow catalog against spec rules | — | list | compose, compare |

### Deliver — 6 flows

User reviews and exports the completed domain config.

| # | Composition | Flow | Dax | Description | Slots | Output | Edge Flows |
|---|---|---|---|---|---|---|---|
| 25 | export + config | generate | {04A} | Generate the final domain config files | format (elective: python\|yaml\|json) | list | ontology, preview |
| 26 | export + accept | confirm_export | {04E} | Confirm and execute the file export | — | confirmation | generate, package |
| 27 | export + config + draft | preview | {4AD} | Preview generated output before committing | file_type (elective: ontology\|yaml\|seed_data) | card | generate, inspect |
| 28 | export + config + spec | ontology | {4AC} | Generate ontology.py specifically | — | card | generate, preview |
| 29 | export + config + lesson | report | {4AB} | Generate a build report with lessons learned | — | card | review_lessons, summarize |
| 30 | export + config + user | package | {48A} | Package the full domain for the user's environment | target_dir (opt) | list | generate, confirm_export |

### Converse — 7 flows

Open-ended conversation, preferences, agent interaction.

| # | Composition | Flow | Dax | Description | Slots | Output | Edge Flows |
|---|---|---|---|---|---|---|---|
| 31 | chat | chat | {000} | Open-ended conversation about building assistants | topic (opt) | card | explain, feedback |
| 32 | browse + agent | next_step | {019} | Ask Kalli what to do next | — | card | summarize, suggest_flow |
| 33 | describe + agent | feedback | {029} | Give feedback on the build process or Kalli's behavior | — | toast | chat, style |
| 34 | user + config | preference | {08A} | Set a user preference for the build process | key (req), value (req) | toast | style, persona |
| 35 | user + lesson | style | {08B} | Tell Kalli about preferred working style | preference (req) | toast | preference, feedback |
| 36 | agent + accept | endorse | {09E} | Approve Kalli's unsolicited suggestion | action (req) | toast | approve, next_step |
| 37 | agent + reject | dismiss | {09F} | Dismiss Kalli's unsolicited suggestion | — | toast | decline, feedback |

### Plan — 5 flows

Multi-step plans that decompose into sub-flows.

| # | Composition | Flow | Dax | Description | Slots | Output | Edge Flows |
|---|---|---|---|---|---|---|---|
| 38 | browse + iterate + spec | research | {13C} | Plan to research specs before making design decisions | topic (req) | list | lookup, explain |
| 39 | export + describe + config | finalize | {24A} | Plan the final export sequence — generate, preview, confirm | — | list | generate, package |
| 40 | describe + insert + config | onboard | {25A} | Full onboarding plan: scope → intents → entities → persona | domain (opt) | list | scope, intent |
| 41 | iterate + insert + config | expand | {35A} | Plan to add a batch of new flows at once | intent_filter (opt), count (opt) | list | compose, suggest_flow |
| 42 | iterate + update + config | redesign | {36A} | Plan to redesign a section of the config | section (req) | list | revise, refine |

### Internal — 6 flows

Background tasks, never user-triggered.

| # | Composition | Flow | Dax | Description | Slots | Output | Edge Flows |
|---|---|---|---|---|---|---|---|
| 43 | chat + browse + user | recap | {018} | Pull a snippet from current conversation (scratchpad L1) | key (opt) | (internal) | recall, remember |
| 44 | browse + agent + lesson | remember | {19B} | Retrieve relevant lessons from memory (L2/L3) | key (opt), scope (opt) | (internal) | recall, recap |
| 45 | describe + user + agent | recall | {289} | Retrieve stored user preferences | key (opt) | (internal) | recap, remember |
| 46 | describe + agent + spec | read_spec | {29C} | Internally read a spec file to answer a question | spec_name (req), section (opt) | (internal) | lookup, explain |
| 47 | iterate + agent + draft | auto_validate | {39D} | Internally validate config consistency | — | (internal) | validate, compare |
| 48 | export + agent + config | auto_generate | {49A} | Internally trigger file generation after approval | file_type (req) | (internal) | generate, ontology |

---

## Distribution Check

| Intent | Count | Flows |
|---|---|---|
| Explore | 8 | status, review_lessons, lookup, recommend, summarize, explain, inspect, compare |
| Provide | 8 | scope, teach, intent, log, revise, remove, persona, entity |
| Design | 8 | propose, compose, revise_flow, approve, decline, suggest_flow, refine, validate |
| Deliver | 6 | generate, confirm_export, preview, ontology, report, package |
| Converse | 7 | chat, next_step, feedback, preference, style, endorse, dismiss |
| Plan | 5 | research, finalize, onboard, expand, redesign |
| Internal | 6 | recap, remember, recall, read_spec, auto_validate, auto_generate |
| **Total** | **48** | |

---

## Slot Type Hierarchy (16 types)

12 universal + 4 domain-specific:

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
| `SectionSlot` | Config section reference (domain-specific) |
| `SpecSlot` | Spec file reference (domain-specific) |
| `FlowSlot` | Flow name reference (domain-specific) |
| `IntentSlot` | Intent name reference (domain-specific) |

---

## Verification Checklist

- [ ] 16 core dacts defined with hex assignments (E=accept, F=reject)
- [ ] 48 flows with unique dax codes (no duplicates)
- [ ] No flow name collides with an intent name
- [ ] Each intent has 5–8 flows (balanced)
- [ ] All flows have 0–3 slots (max 5)
- [ ] No two flows share the same slot signature
- [ ] All flows have output block type from palette
- [ ] Internal flows use `(internal)` output
- [ ] Plan flows use `list` output
- [ ] Delete flows use `confirmation` output
- [ ] 1–3 edge flows per flow
