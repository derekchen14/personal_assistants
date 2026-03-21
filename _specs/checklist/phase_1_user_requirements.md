# Phase 1 — User Requirements

Define the agent's identity: what it does, what it doesn't do, and the vocabulary it uses to understand user requests.

## Context

Every domain assistant starts with a clear scope. An assistant is a **job role** — a specific professional persona with boundaries. This phase produces the assistant's intent taxonomy, key entities, persona definition, and stub files that all later phases build on.

**Prerequisites**: None — this is the starting phase.

**Outputs**: `ontology.py` (stub with intents and empty flow catalog), `<domain>.yaml` (persona and guardrails), scoping document.

**Spec references**: [architecture.md](../architecture.md), [flow_selection.md § Agent Scoping](../utilities/flow_selection.md), [configuration.md § Domain Config Schema](../utilities/configuration.md)

---

## Steps

### Step 1 — Agent Scoping

Define what the assistant does and doesn't do. Follow the scoping process:

1. Start with a description of what the assistant should do
2. Narrow it to a specific job or task domain
3. Ask: "What does the assistant NOT do?" to enforce boundaries
4. Reject agents whose scope spans more than one domain

**Good scope examples**:
- "Data analyst" — connects to data sources, cleans data, runs analyses, creates visualizations and reports
- "Customer support agent" — ticket triage, FAQ answers, escalation routing
- "Full-stack web developer" — web dev + DevOps, NOT AI/ML or mobile

**Bad scope examples**:
- "General assistant" — no domain boundaries, can't specialize flows
- "Software engineer + data scientist" — two distinct domains
- "Marketing + sales" — overlapping but separate job roles

**Output**: A 2–3 sentence scope statement with explicit inclusions and exclusions.

### Step 2 — Choose Key Entities

Pick 3 grounding objects that make the domain concrete. These are the things you'd ask "which one?" about. They ground the Ambiguity Handler's Partial level and often inspire building block types.

**Guidelines**:
  - Pick entities that are central to the domain and have clear distinctions
  - These are the artifacts displayed in the UI so they should be tangible and relatable things
  - Avoid entities that are too similar to each other (e.g. folder and directory — they're the same thing)

**Examples**:

| Domain | Key Entities |
|---|---|
| Data Analysis | spreadsheet (or dataset), column, chart |
| Programmer | folder, file, function |
| Digital Marketer | campaign, ad, channel |
| Blogger | post, section, note |
| Scheduler | event, calendar, time_block |
| Recruiter | listing, application, resume |

### Step 3 — Define Intents

Choose 7 intents: 3 universal + 4 domain-specific.

**Universal intents** (fixed for all domains):
- **Plan** — decomposes a request into sub-flows
- **Converse** — open-ended conversation, FAQs, chitchat
- **Internal** — system housekeeping (never user-triggered)

**4 domain-specific intents** map to abstract slots describing the semantic role:

| Abstract Slot | If the flow... |
|---|---|
| Read | Retrieves or reads existing entities without modification |
| Prepare | Create new entities, or clean and prepare the entity for downstream consumption |
| Transform | Modifies, connects, or processes the key entities, including removal |
| Share | Publishes or delivers the entity to others, possibly including time-based scheduling |

**Rules**:
- Name intents after domain activities, not generic operations (Good: "Analyze", "Deploy"; Bad: "Read", "Transform")
- The 4 intents often form a natural pipeline representing the typical workflow
  * Read: I want to see the entity. What is the status of the entity?
  * Prepare: I want to create a new entity. How do I prepare the entity for later use?
  * Transform: I want to modify the entity. How do I mix and match these entities to form new ones?
  * Share: I want to share my entity to others. What steps are needed to make the result accessible to others?
- Intent names must not collide with dact names

**Worked examples**:

Domain: Data Analysis
  - Analyze (Read) — understand or query the data, but does not modify it
  - Clean (Prepare) — normalize, impute, deduplicate and prepare the data for analysis
  - Transform (Transform) — changes the tables, can connect (ie. join) multiple entities (tables) together
  - Report (Share) — export to CSV, generate report, publish findings, create dashboard

Domain: Programmer
  - Trace (Read) — understand or query the code, but does not modify it
  - Code (Prepare) — write new code, or clean and prepare the code for execution
  - Refactor (Transform) — changes the code, connect multiple entities (functions) together to form a class
  - Deploy (Share) — deploy the code to a server, publish the code to a repository, build a docker image

Domain: Digital Marketer
  - Scout (Read) — understand or query the campaigns and ads, but does not modify them
  - Craft (Prepare) — write new content, launch new campaigns or ad groups, clean up ad copy
  - Launch (Transform) — adjust campaign settings or bids, connect multiple entities (posts) together to form a series
  - Optimize (Share) — optimize the campaign performance, schedule the campaign to run

Domain: Blogger
  - Outline (Read) — understand or query the posts or drafts, but does not modify it
  - Draft (Prepare) — write new content, clean up post copy, create an outline of bullet points
  - Revise (Transform) — adjust post tone or style, compare different drafts, polish a specific sentence
  - Publish (Share) — publish the post to a channel, schedule the post to run

Domain: Customer Support
  - Triage (Read) — understand or query the tickets, but does not modify them
  - Route (Prepare) — create new tickets, categorize and prioritize tickets, clean up ticket copy
  - Resolve (Transform) — adjust ticket status or priority, connect multiple entities (tickets) together to form a thread
  - Follow-up (Share) — follow up on the ticket, schedule the ticket to be resolved

### Step 4 — Define Persona and Guardrails

Every domain must define both sections in its YAML config. The persona sets the assistant's personality; guardrails enforce safety boundaries.

**Persona fields**:
- `tone` — communication style (warm, professional, conversational, efficient)
- `expertise_boundaries` — list of topics the assistant is qualified for
- `name` — display name for the agent
- `response_style` — concise | balanced | detailed
- `design colors` - color palette for the UI (2 primary colors, 1 accent color)

**Guardrails fields**:
- `content_filter` — categories and severity level
- `pii_detection` — enabled/disabled, action (redact/warn/block), PII types
- `topic_control` — allowed/forbidden topics
- `prompt_injection_detection` — enabled, sensitivity level

**Cross-domain comparison** (for reference):

| Section | Data Analysis | Blogger | Recruiter | Scheduler |
|---|---|---|---|---|
| `persona.tone` | analytical | conversational | professional | efficient |
| `persona.name` | Dana | Writing Coach | Talent Scout | Schedule Pro |
| `persona.response_style` | balanced | detailed | concise | concise |
| `guardrails.pii_detection.enabled` | true | false | true | false |
| `key_entities` | dataset, column, chart | post, section, draft | listing, application, resume | event, calendar, time_block |
| `human_in_the_loop.tool_approval.mode` | none | none | non_idempotent | none |

### Step 5 — Create Ontology Stub

Create `ontology.py` with the intent enum and an empty flow catalog. This file will be fully populated in Phase 2.

```python
from enum import Enum

class Intent(str, Enum):
    """7 intents: 3 universal + 4 domain-specific."""
    PLAN = 'Plan'
    CONVERSE = 'Converse'
    INTERNAL = 'Internal'
    # Domain-specific (rename for your domain):
    READ = 'Read'
    PREPARE = 'Prepare'
    TRANSFORM = 'Transform'
    SCHEDULE = 'Schedule'

class FlowLifecycle(str, Enum):
    PENDING = 'Pending'
    ACTIVE = 'Active'
    COMPLETED = 'Completed'
    INVALID = 'Invalid'

class AmbiguityLevel(str, Enum):
    GENERAL = 'general'
    PARTIAL = 'partial'
    SPECIFIC = 'specific'
    CONFIRMATION = 'confirmation'

# Flow catalog — populated in Phase 2 (Flow Selection)
# Each entry: {dact_name: {dax, intent, description, slots, output, edge_flows, policy_path}}
FLOW_CATALOG = {}

# Key entities for this domain
KEY_ENTITIES = []  # e.g., ['dataset', 'column', 'chart']
```

### Step 6 — Create Domain YAML Stub

Create `<domain>.yaml` with persona and guardrails sections. Other sections (models, session, memory, etc.) inherit from `shared_defaults.yaml`.

```yaml
# <domain>/<domain>.yaml
# Sections defined here fully replace the shared default for that section.

environment: dev

persona:
  tone: professional           # Override for your domain
  expertise_boundaries: []     # List domain expertise areas
  name: "Assistant"            # Agent display name
  response_style: balanced     # concise | balanced | detailed

guardrails:
  input_max_tokens: 4096
  content_filter:
    enabled: true
    categories: [violence, sexual, hate_speech, self_harm, dangerous]
    severity: medium
  pii_detection:
    enabled: false
    action: redact
    types: [ssn, credit_card, email, phone, address]
  topic_control:
    allowed_topics: []
    forbidden_topics: []
  forbidden_patterns: []
  prompt_injection_detection:
    enabled: true
    sensitivity: medium

key_entities: []               # e.g., [dataset, column, chart]

# Tools section populated in Phase 3 (Tool Design)
# Template registry populated in Phase 7 (Prompt Writing)
```

Also verify that `shared/shared_defaults.yaml` exists with baseline config for all 16 sections. If not, create it using the annotated reference in [configuration.md § shared_defaults.yaml](../utilities/configuration.md).

---

## File Changes Summary

| Action | File | Description |
|---|---|---|
| Create | `<domain>/schemas/ontology.py` | Intent enum, lifecycle states, slot categories, empty flow catalog |
| Create | `<domain>/schemas/<domain>.yaml` | Persona, guardrails, key_entities |
| Create | `shared/shared_defaults.yaml` | Baseline config (if not already present) |

---

## Verification

- [ ] Assistant scope is defined with explicit inclusions and exclusions
- [ ] 7 intents defined: 3 universal + 4 domain-specific with meaningful names
- [ ] 3 key entities chosen that ground the domain
- [ ] Persona section has tone, expertise_boundaries, name, response_style
- [ ] Guardrails section has content_filter, pii_detection, topic_control, prompt_injection
- [ ] `ontology.py` has Intent enum with all 7 intents
- [ ] `ontology.py` has FlowLifecycle and AmbiguityLevel enums
- [ ] `<domain>.yaml` loads without syntax errors
- [ ] `shared_defaults.yaml` exists with all 16 sections
- [ ] Intent names do not collide with any planned dact names
