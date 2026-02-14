# Build Checklist

Phased implementation plan for building a domain agent from scratch. Each phase is a self-contained document with context, steps, files, and verification criteria.

---

## Phases

| # | Phase | What It Produces |
|---|---|---|
| 1 | [User Requirements](./phase_1_user_requirements.md) | Agent scope, intents, key entities, persona, ontology stub, YAML stub |
| 2 | [Flow Selection](./phase_2_flow_selection.md) | 48 flows with dact codes, slots, outputs — fully populated ontology |
| 3 | [Tool Design](./phase_3_tool_design.md) | Tool manifest, JSON schemas, error contracts, service classes |
| 4 | [Foundation](./phase_4_foundation.md) | Running server, config loader, database, module shells, Agent shell |
| 5 | [Core Agent](./phase_5_core_agent.md) | 7 components, NLU/PEX/RES modules, Agent orchestrator |
| 6 | [Policies](./phase_6_policies.md) | 32 working flows, 16 stubbed, skill templates, tests |
| 7 | [Prompt Writing](./phase_7_prompt_writing.md) | Full prompt suite, template registry, prompt versioning |
| 8 | [Deployment](./phase_8_deployment.md) | Frontend, evaluation pipeline, production config, containerization |

---

## Folder Structure

Full directory tree for a domain agent. `shared/` is set up once during Phase 4 and used by all domains.

### `shared/` — Cross-Domain Config

```
shared/
├── shared_defaults.yaml            # Baseline config for all domains         [Phase 1]
├── arguments.py                    # CLI arg definitions (port, env, debug)  [Phase 4]
└── schemas/                        # Canonical tool schemas                  [Phase 3]
    └── components/                 # Non-manifest component tools
```

### Domain Agent Template

```
<domain>/
├── config.py                       # Config loader — merges shared + domain YAML          [Phase 4]
├── requirements.txt                # Python dependencies                                  [Phase 4]
├── run.sh                          # Start backend + frontend                             [Phase 4]
├── .env.example                    # DATABASE_URL, PORT, ENV, API keys                    [Phase 3]
├── .gitignore                      # __pycache__, node_modules, .env, *.db, dist/, .svelte-kit/
│
├── backend/
│   ├── __init__.py
│   ├── webserver.py                # FastAPI entry point (health, CORS, routers)           [Phase 4]
│   ├── agent.py                    # Main Agent class (turn pipeline lives here)           [Phase 5]
│   ├── manager.py                  # Agent instance lifecycle (JWT, caching, cleanup)      [Phase 5]
│   ├── db.py                       # SQLAlchemy engine + session (reads DATABASE_URL)      [Phase 4]
│   │
│   ├── components/
│   │   ├── __init__.py
│   │   ├── dialogue_state.py       # Predicted state, slots, flags, snapshots             [Phase 5]
│   │   ├── flow_stack.py           # Stack data structure, lifecycle states                [Phase 5]
│   │   ├── context_coordinator.py  # Turn storage, history retrieval, checkpoints         [Phase 5]
│   │   ├── prompt_engineer.py      # Model-agnostic LLM interface, guardrails            [Phase 5]
│   │   ├── display_frame.py        # Data-display decoupling, core entities               [Phase 5]
│   │   ├── ambiguity_handler.py    # 4-level uncertainty tracking + resolution            [Phase 5]
│   │   └── memory_manager.py       # 3-tier cache (scratchpad, prefs, business)           [Phase 5]
│   │
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── nlu.py                  # think(), contemplate(), react()                      [Phase 5]
│   │   ├── pex.py                  # execute(), recover()                                 [Phase 5]
│   │   ├── res.py                  # generate(), display()                                [Phase 5]
│   │   └── policies/               # Per-intent policy methods                            [Phase 6]
│   │       └── __init__.py
│   │
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat_service.py         # WebSocket /ws endpoint                               [Phase 4]
│   │   ├── auth_service.py         # Login, signup, token endpoints                       [Phase 4]
│   │   ├── conversation_service.py # Conversation CRUD                                    [Phase 4]
│   │   └── health_service.py       # GET /health                                          [Phase 4]
│   │
│   ├── middleware/
│   │   ├── auth_middleware.py      # JWT validation + token refresh                       [Phase 4]
│   │   └── activity_middleware.py  # User activity tracking                               [Phase 4]
│   │
│   ├── auth/
│   │   ├── jwt_helpers.py          # JWT sign, decode, cookie management                  [Phase 4]
│   │   └── user_fields.py          # Pydantic models for signup/login                     [Phase 4]
│   │
│   ├── prompts/                    # Prompt assembly code (Python)
│   │   ├── for_experts.py          # NLU intent/flow classification prompts               [Phase 7]
│   │   ├── for_nlu.py              # NLU slot-filling prompts                             [Phase 7]
│   │   ├── for_pex.py              # PEX skill execution prompts                          [Phase 7]
│   │   ├── for_res.py              # RES naturalization prompts                           [Phase 7]
│   │   ├── for_contemplate.py      # NLU re-routing prompts                               [Phase 7]
│   │   ├── for_executors.py        # Domain-specific tool prompts                         [Phase 7]
│   │   ├── for_metadata.py         # Domain-specific metadata prompts                     [Phase 7]
│   │   ├── general.py              # System prompt, persona composition                   [Phase 7]
│   │   └── skills/                 # Per-flow skill templates (markdown)                  [Phase 6]
│   │       └── <dact>.md           # Slots 2-6 of the 8-slot prompt format
│   │
│   └── utilities/
│       └── __init__.py
│
├── utils/
│   └── helper.py                   # Domain helpers (dax2dact, flow2dax, etc.)            [Phase 2]
│
├── schemas/                        # Domain definitions, tool schemas, response templates
│   ├── ontology.py                 # Intent enum, flow catalog, dact codes, constants     [Phase 1–2]
│   ├── <domain>.yaml               # Domain config (persona, guardrails, key_entities)    [Phase 1]
│   ├── <tool_id>.json              # Tool JSON Schema files                               [Phase 3]
│   └── templates/                  # RES response templates                               [Phase 7]
│       └── <domain>/               # Domain-specific output templates
│
├── database/
│   ├── tables.py                   # SQLAlchemy ORM models (User, Conversation, etc.)     [Phase 4]
│   └── seed_data.json              # Initial data (intents, flows)                        [Phase 2]
│
├── frontend/                       # SvelteKit 2 (Svelte 5) + Tailwind CSS               [Phase 8]
│   ├── package.json
│   ├── svelte.config.js
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── src/
│   │   ├── app.html
│   │   ├── app.css
│   │   ├── lib/
│   │   │   ├── stores/             # State: conversation, data, ui, display
│   │   │   ├── components/blocks/  # Building block components
│   │   │   └── utils/              # WebSocket manager, telemetry
│   │   └── routes/
│   │       ├── +layout.svelte
│   │       ├── +page.svelte
│   │       ├── login/
│   │       ├── signup/
│   │       └── logout/
│   └── static/
│
└── tests/                                                                                 [Phase 6]
    ├── conftest.py                 # pytest fixtures
    ├── test_nlu.py                 # NLU classification tests
    ├── test_pex.py                 # Policy execution tests
    ├── test_res.py                 # Response generation tests
    └── test_flows/                 # Per-flow integration tests
        └── {dax}_{flow}.py         # Ordered by dax code
```

### Notes

- **`run.sh`** starts both the FastAPI backend and SvelteKit dev server. Each domain runs on its own port.
- **`.env.example`** documents required environment variables. Copy to `.env` and fill in. `DATABASE_URL` points to a domain-specific database on the local Postgres server (e.g., `postgresql://localhost/cooking`). One Postgres server, one database per domain — schema isolation without operational overhead.
- **`.gitignore`** covers `__pycache__/`, `node_modules/`, `.env`, `dist/`, `.svelte-kit/`.
- **No Alembic** — uses `Base.metadata.create_all()` on startup. Add migrations when schema stabilizes.
- **No shared base classes** — each domain is fully self-contained. `shared/` is config-only.
