# Build Checklist

Phased implementation order. Each step lists what to implement, the spec reference, and the output artifact.

---

## Folder Structure

Full directory tree for a domain agent. Phase annotations show when each file/folder is created. `shared/` is set up once during Phase 1 and used by all domains.

### `shared/` — Cross-Domain Config

```
shared/
├── shared_defaults.yaml            # Baseline config for all domains         [Phase 1, step 4]
├── arguments.py                    # CLI arg definitions (port, env, debug)  [Phase 1, step 1]
└── schemas/                        # Canonical tool schemas                  [Phase 1, step 5]
    └── components/                 # Non-manifest component tools
```

### Domain Agent Template

```
<domain>/
├── config.py                       # Config loader — merges shared + domain YAML          [Phase 1, step 2]
├── requirements.txt                # Python dependencies                                  [Phase 1, step 1]
├── run.sh                          # Start backend + frontend                             [Phase 1, step 1]
├── .env.example                    # DATABASE_URL, PORT, ENV, API keys                    [Phase 1, step 1]
├── .gitignore                      # __pycache__, node_modules, .env, *.db, dist/, .svelte-kit/
│
├── backend/
│   ├── __init__.py
│   ├── webserver.py                # FastAPI entry point (health, CORS, routers)           [Phase 1, step 1]
│   ├── agent.py                    # Main Agent class (turn pipeline lives here)            [Phase 4, step 16]
│   ├── manager.py                  # Agent instance lifecycle (JWT, caching, cleanup)     [Phase 4, step 16]
│   ├── db.py                       # SQLAlchemy engine + session (reads DATABASE_URL)     [Phase 1, step 1]
│   │
│   ├── components/
│   │   ├── __init__.py
│   │   ├── dialogue_state.py       # Predicted state, slots, flags, snapshots             [Phase 2, step 6]
│   │   ├── flow_stack.py           # Stack data structure, lifecycle states                [Phase 2, step 7]
│   │   ├── context_coordinator.py  # Turn storage, history retrieval, checkpoints         [Phase 2, step 8]
│   │   ├── prompt_engineer.py      # Model-agnostic LLM interface, guardrails            [Phase 2, step 9]
│   │   ├── display_frame.py        # Data-display decoupling, core entities               [Phase 2, step 10]
│   │   ├── ambiguity_handler.py    # 4-level uncertainty tracking + resolution            [Phase 2, step 11]
│   │   └── memory_manager.py       # 3-tier cache (scratchpad, prefs, business)           [Phase 2, step 12]
│   │
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── nlu.py                  # think(), contemplate(), react()                      [Phase 3, step 13]
│   │   ├── pex.py                  # execute(), recover()                                 [Phase 3, step 14]
│   │   ├── res.py                  # generate(), display()                                [Phase 3, step 15]
│   │   └── policies/               # Per-intent policy methods                            [Phase 3, step 14]
│   │       └── __init__.py
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat_service.py         # WebSocket /ws endpoint                               [Phase 1, step 1]
│   │   ├── auth_service.py         # Login, signup, token endpoints                       [Phase 1, step 1]
│   │   ├── conversation_service.py # Conversation CRUD                                    [Phase 1, step 1]
│   │   └── health_service.py       # GET /health                                          [Phase 1, step 1]
│   │
│   ├── middleware/
│   │   ├── auth_middleware.py      # JWT validation + token refresh                       [Phase 1, step 1]
│   │   └── activity_middleware.py  # User activity tracking                               [Phase 1, step 1]
│   │
│   ├── auth/
│   │   ├── jwt_helpers.py          # JWT sign, decode, cookie management                  [Phase 1, step 1]
│   │   └── user_fields.py          # Pydantic models for signup/login                     [Phase 1, step 1]
│   │
│   ├── prompts/                    # Prompt assembly code (Python)
│   │   ├── for_nlu.py              # NLU prompt strings + assembly                        [Phase 3, step 13]
│   │   ├── for_pex.py              # PEX prompt strings + assembly                        [Phase 3, step 14]
│   │   ├── for_res.py              # RES prompt strings + assembly                        [Phase 3, step 15]
│   │   ├── system.py               # System prompt, persona composition                   [Phase 3, step 13]
│   │   └── skills/                 # Per-flow skill templates (markdown)                  [Phase 6]
│   │       └── <dact>.md           # Slots 2-6 of the 8-slot prompt format
│   │
│   └── utilities/
│       └── __init__.py
│
├── utils/
│   └── helper.py                   # Domain helpers (dax2dact, flow2dax, etc.)            [Phase 1, step 3]
│                                   # Generic utilities every domain should have:
│                                   #   find_nearest_valid_option(target, options)  — entity matching (exact → case-insensitive → alphanumeric)
│                                   #   find_nearest_lexical(candidate, options)    — Levenshtein distance for fuzzy matching
│                                   #   serialize_for_json(value)                  — safe JSON serialization (numpy, pandas, NaN → None)
│                                   #   sanitize_entities(entities, valid_set)     — normalize entity references (strip/lower/upper/title)
│
├── schemas/                        # Domain definitions, tool schemas, response templates
│   ├── ontology.py                 # Intent enum, flow catalog, dact codes, constants     [Phase 1, step 3]
│   ├── <domain>.yaml               # Domain config (persona, guardrails, key_entities)    [Phase 1, step 4]
│   ├── <tool_id>.json              # Tool JSON Schema files                               [Phase 1, step 5]
│   └── templates/                  # RES response templates                               [Phase 3, step 15]
│       └── <domain>/               # Domain-specific output templates
│
├── database/
│   ├── tables.py                   # SQLAlchemy ORM models (User, Conversation, etc.)     [Phase 1, step 1]
│   └── seed_data.json              # Initial data (intents, flows)                        [Phase 1, step 3]
│
├── frontend/                       # SvelteKit 2 (Svelte 5) + Tailwind CSS               [Phase 5, step 17]
│   ├── package.json
│   ├── svelte.config.js            # @sveltejs/adapter-node
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── src/
│   │   ├── app.html
│   │   ├── app.css                 # Tailwind imports
│   │   ├── lib/
│   │   │   ├── api_utils.ts        # HTTP client + WebSocket helpers
│   │   │   └── constants.ts
│   │   └── routes/
│   │       ├── +layout.svelte      # Root layout (nav, global styles)
│   │       ├── +page.svelte        # Landing / home
│   │       ├── login/
│   │       │   └── +page.svelte
│   │       ├── signup/
│   │       │   └── +page.svelte
│   │       ├── logout/
│   │       │   └── +page.svelte
│   │       └── application/
│   │           ├── +page.svelte    # Main app page
│   │           ├── components/
│   │           │   ├── dialogue_panel/
│   │           │   │   ├── input_container/
│   │           │   │   ├── chat_container/
│   │           │   │   └── agent_container/
│   │           │   └── display_panel/
│   │           └── storage/
│   │               └── store.ts    # Svelte stores (state management)
│   └── static/                     # Fonts, images, favicon
│
└── tests/                                                                                 [Phase 6]
    ├── conftest.py                 # pytest fixtures
    └── test_*.py                   # test_<module>.py per style guide
```

### Notes

- **`run.sh`** starts both the FastAPI backend and SvelteKit dev server. Each domain runs on its own port.
- **`.env.example`** documents required environment variables. Copy to `.env` and fill in. `DATABASE_URL` points to a domain-specific database on the local Postgres server (e.g., `postgresql://localhost/cooking`). One Postgres server, one database per domain — schema isolation without operational overhead.
- **`.gitignore`** covers `__pycache__/`, `node_modules/`, `.env`, `dist/`, `.svelte-kit/`.
- **No Alembic** — uses `Base.metadata.create_all()` on startup. Add migrations when schema stabilizes.
- **No shared base classes** — each domain is fully self-contained. `shared/` is config-only.

---

## Phase 1 — Foundation

Before starting, define the agent's scope:

- **Agent = job role** — a specific professional persona (data analyst, chef, programmer, digital marketer)
- User provides a description; help narrow it to a specific job or task domain
- Ask: "What does the agent NOT do?" to enforce boundaries
- Reject agents whose scope spans more than one domain

See [Flow Selection § Agent Scoping](./utilities/flow_selection.md) for details and examples.

### 1. Server Setup

Set up FastAPI app with health endpoint, CORS middleware, and credential management.

- **Spec**: [server_setup.md](./utilities/server_setup.md)
- **Output**: Running server with `/health`, CORS configured, scoped credential store

### 2. Config Loader

Build the config loader: read shared defaults YAML + domain YAML, merge with section-level override, validate against schema, freeze into read-only object.

- **Spec**: [configuration.md § Startup Loading & Validation](./utilities/configuration.md)
- **Output**: `config.py` — loads, merges, validates, freezes config

### 3. Domain Ontology

Define intents (Plan, Converse, Internal + 4 domain-specific), flows with dact names and dax codes, edge flows, slot categories.

- **Spec**: [flow_selection.md](./utilities/flow_selection.md), [dialogue_state.md § Predicted State](./components/dialogue_state.md)
- **Output**: `ontology.py` — intent enum, flow catalog, slot enums, ambiguity levels

### 4. Domain Config YAML

Review the domain YAML for Persona and Guardrails.  Every new domain must define both sections (tone, expertise boundaries, PII policy, topic control). The remaining sections (models, feature flags, context windows, etc.) will use the defaults in the shared YAML config.

- **Spec**: [configuration.md § Domain Config Schema](./utilities/configuration.md)
- **Output**: `<domain>.yaml` and `shared_defaults.yaml` (tools section populated in step 5)

### 5. Tool Design

Derive the tool manifest from the flow catalog. Group flows by external system, identify operations, map slots to tool parameters, design input/output schemas, define error contracts.

- **Spec**: [tool_smith.md](./utilities/tool_smith.md)
- **Output**: Tool manifest entries in `<domain>.yaml` + JSON Schema files in `schemas/`

---

## Phase 1.5 — External Service Connections

**When**: After server setup (Phase 1, step 1) but before building components. Only for domains that integrate with external services (e.g., Blogger → Substack, Recruiter → LinkedIn, Scheduler → Slack).

For each service the domain needs, gather credentials following the steps in [`shared/gather_tokens.md`](../shared/gather_tokens.md), then verify connectivity with `shared/connect_apis.py`. These are development tools, not part of the agent runtime. When building the actual agent, service classes in `backend/` wrap these APIs as tools in the tool manifest.

### Per-Service Setup

| Service | Auth Method | Env Vars | Packages | Setup Effort |
|---|---|---|---|---|
| GitHub | Fine-grained PAT | `GITHUB_TOKEN` | `requests` | 5 min |
| Slack | Bot OAuth Token | `SLACK_BOT_TOKEN` | `slack-sdk` | 10 min |
| LinkedIn | OAuth 2.0 (browser flow) | `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` | `requests` | 20 min |
| Substack | Browser cookies | `SUBSTACK_SID`, `SUBSTACK_LLI` | `python-substack` | 5 min |

### Verification

Run `shared/connect_apis.py` with the service name to confirm connectivity:

```
python shared/connect_apis.py --service github
python shared/connect_apis.py --service slack
python shared/connect_apis.py --service linkedin
python shared/connect_apis.py --service substack
```

Each invocation loads credentials from env vars, makes a simple read request, and prints results. If an env var is missing, the script fails with a clear error pointing to `gather_tokens.md`.

---

## Phase 2 — Core Components

### 6. Dialogue State

Implement predicted state tracking (intent + flow), slot-filling with type validation, flags (`keep_going`, `has_issues`, `has_plan`, `natural_birth`), state history (diffs, snapshots, rollback), and confidence tracking.

- **Spec**: [dialogue_state.md](./components/dialogue_state.md)
- **Output**: Dialogue state class with snapshot/rollback support

### 7. Flow Stack

Implement the stack data structure within dialogue state: push/pop/peek, flow lifecycle states (Pending, Active, Completed, Invalid), deduplication, concurrency model (single-threaded user-facing, parallel Internal), fallback protocol.

- **Spec**: [flow_stack.md](./components/flow_stack.md)
- **Output**: Flow stack with lifecycle management

### 8. Context Coordinator

Implement structured turn storage (role, form, content), retrieval utilities (`compile_history`), and checkpoint support for long-term storage.

- **Spec**: [context_coordinator.md](./components/context_coordinator.md)
- **Output**: Context coordinator with turn storage and checkpoints

### 9. Prompt Engineer

Build model-agnostic LLM interface: streaming vs. regular responses, output parsing, guardrails (JSON, SQL, Python), data preview formatting, prompt versioning.

- **Spec**: [prompt_engineer.md](./components/prompt_engineer.md)
- **Output**: Prompt engineer with multi-model support and guardrails

### 10. Display Frame

Implement the data-display decoupling layer: core entity attributes (`data`, `source`, `display_name`, `display_type`, `chart_type`), pagination via `table_id`, multi-turn frame updates.

- **Spec**: [display_frame.md](./components/display_frame.md)
- **Output**: Display frame class

### 11. Ambiguity Handler

Implement four-level uncertainty tracking (General, Partial, Specific, Confirmation), `declare()` / `ask()` / `generate()` / `resolve()` lifecycle, generation modes (lexicalize, naturalize, compile), metadata storage.

- **Spec**: [ambiguity_handler.md](./components/ambiguity_handler.md)
- **Output**: Ambiguity handler with declaration and resolution

### 12. Memory Manager

Build three-tier cache: Session Scratchpad (L1/L2 in-context), User Preferences (RAM, per-account), Business Context (disk, per-client with vector retrieval). Implement promotion triggers and scratchpad summarization.

- **Spec**: [memory_manager.md](./components/memory_manager.md)
- **Output**: Memory manager with three tiers

---

## Phase 3 — Modules

### 13. NLU

Implement `think()` (pre-hook validation gate, intent prediction, flow prediction with majority vote, slot-filling, post-hook state validation), `contemplate()` (re-routing with narrowed search space), and `react()` (lightweight processing for user actions).

- **Spec**: [nlu.md](./modules/nlu.md)
- **Output**: NLU module with think/contemplate/react

### 14. PEX

Implement `execute()` (pre-hook slot readiness check, policy resolution, tool execution with schema validation, result output by intent, flow completion, post-hook state validation) and `recover()` (slot correction, retry, alternative tool, graceful degradation, ambiguity declaration). Write domain policy files (7 per domain, one per intent).

- **Spec**: [pex.md](./modules/pex.md)
- **Output**: PEX module with execute/recover + domain policy files

### 15. RES

Implement `generate()` (pre-hook lifecycle cleanup, ambiguity check, response routing, template fill + naturalize, streaming decision, CC write, post-hook output validation) and `display()` (pre-hook frame validation, frame-to-block mapping, data rendering, post-hook render validation). Set up the template registry with base and domain override templates.

- **Spec**: [res.md](./modules/res.md)
- **Output**: RES module with generate/display + template registry

---

## Phase 4 — Agent

### 16. Agent

Wire the turn pipeline (NLU `think()`/`react()` → PEX `execute()` → RES `respond()`), implement `keep_going` loop, input validation routing (NLU `prepare()` failures, PEX `has_issues`), two-tier failure handling (PEX repair loop, Agent-level re-route → skip → escalate), Internal flow triggering and parallelization.

- **Spec**: [architecture.md § Agent](./architecture.md)
- **Output**: Agent class coordinating the full turn pipeline

---

## Phase 5 — Utilities

### 17. Building Blocks

Build frontend components: atomic block types (table, chart, card, list), rendering model (panel vs. inline), responsive hints, block-template coordination.

- **Spec**: [blocks.md](./utilities/blocks.md)
- **Output**: Frontend block components

### 18. Evaluation

Implement signal envelope collection from all modules/components, self-check gate (rule-based + optional LLM), per-session metrics and session record, user feedback (explicit + implicit), prompt version attribution. Set up offline evals: three-pillar E2E testing (workflow prediction, trajectory optimization, final output), regression testing, per-flow evaluation.

- **Spec**: [evaluation.md](./utilities/evaluation.md)
- **Output**: Evaluation utility with online + offline modes

---

## Phase 6 — Domain Flow Development

Iterative process for bringing up domain flows. Code flows in batches, test each batch before continuing. Start after all 48 flows are defined in ontology and domain config (Phase 1), core components are built (Phase 2), modules are implemented (Phase 3), Agent is wired (Phase 4), and utilities are in place (Phase 5).

### Per-Flow Checklist

Each flow requires these artifacts:

1. Add the flow to domain config (ontology.py entry + YAML tool bindings)
2. Write 10 utterances per flow — used for guidance, testing, and debugging
3. Update NLU prompts for flow detection (or create a new prompt)
4. Make slot-filling concrete — types, validators, defaults
5. Add a policy class method to PEX (deterministic skeleton: slot review, result processing, flow completion)
6. Write a skill template for the flow's tool execution step (prompt template + tool list)
7. Define the exact Display Frame output for the flow
8. Decide whether this flow benefits from a reflection loop — flows involving creative generation (writing prose, crafting reports), complex code generation (long SQL, multi-step scripts), or multi-source synthesis should enable the optional generate-evaluate-revise cycle in the skill template. See [PEX § Skill Execution](./modules/pex.md).

### 19. First 16 Flows

Code the first 16 flows using the per-flow checklist above. Select flows that cover 5 intents so large parts of the pipeline are exercised early.
Avoid building in Plan and Internal flows for this batch.

Testing:

- Write 3–5 unit tests per flow
- Randomly select 4 utterances per flow → 64 test utterances total
- Run the agent end-to-end; verify all utterances classify correctly
- Iterate on code and NLU prompts until classification works

- **Output**: 16 working flows with unit tests and passing classification

### 20. Next 16 Flows (32 Total)

Code 16 more flows using the per-flow checklist.
This time we can include Plan and Internal flows to exercise the full extent of the assistant's capabilities.

Testing:

- Write 3–5 unit tests per flow
- Randomly select 3 utterances per flow → 96 test utterances total
- Run the agent end-to-end; verify all utterances classify correctly
- Iterate on code and NLU prompts as needed
- If two flows are often confused with each other, consider merging them — this is allowed

- **Output**: 32 working flows with unit tests and passing classification

### 21. Remaining 16 Flows (Stub)

Set a default warning ("X flow is still in development") for the remaining 48 − 32 = 16 flows. Pause development at 32 working flows with 48 total flows of domain coverage. The stubs ensure graceful handling when a user hits an unimplemented flow.

- **Output**: 48 flows registered, 32 fully working, 16 stubbed with development warnings
- The max limit is 64 flows per domain, so this leaves room for future expansion.

---

## Phase 7 — Deployment

### 22. Deployment

Configure production environment: `environment: prod` in domain YAML, strict validation, production timeouts, logging at INFO level. Set up containerization and serving infrastructure.

- **Spec**: [configuration.md § Environment Awareness](./utilities/configuration.md), [server_setup.md](./utilities/server_setup.md)
- **Output**: Production-ready deployment
