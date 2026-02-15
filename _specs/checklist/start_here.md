# Build Checklist

Phased implementation plan for building a domain agent from scratch. Each phase is a self-contained document with context, steps, files, and verification criteria.

---

## Phases

| # | Phase | What It Produces |
|---|---|---|
| 1 | [User Requirements](./phase_1_user_requirements.md) | Agent scope, intents, key entities, persona, ontology stub, YAML stub |
| 2 | [Flow Selection](./phase_2_flow_selection.md) | 48 flows with dact codes, slots, outputs — fully populated ontology |
| 3 | [Tool Design](./phase_3_tool_design.md) | Tool manifest, JSON schemas, error contracts, service classes |
| 4a | [Basic Foundation](./phase_4a_basic_foundation.md) | Server, config, SQLite, module shells — no auth |
| 4b | [Pro Foundation](./phase_4b_pro_foundation.md) | Postgres, JWT auth, auth routes, rate limiting |
| 4c | [Advanced Foundation](./phase_4c_advanced_foundation.md) | OAuth 2.0, credential storage, token refresh |
| 5 | [Core Agent](./phase_5_core_agent.md) | 7 components, NLU/PEX/RES modules, Agent orchestrator |
| 6 | [Staging](./phase_6_staging.md) | Basic agent working end-to-end with hard-coded test flows |
| 7 | [Policies](./phase_7_policies.md) | 32 working flows, 16 stubbed, skill templates, tests |
| 8 | [Prompt Writing](./phase_8_prompt_writing.md) | Full prompt suite, template registry, prompt versioning |
| 9a | [Basic Deployment](./phase_9a_basic_deployment.md) | SvelteKit frontend, local dev, username prompt |
| 9b | [Pro Deployment](./phase_9b_pro_deployment.md) | Login pages, Docker, production config |
| 9c | [Advanced Deployment](./phase_9c_advanced_deployment.md) | OAuth login, payment, monitoring |
| 10 | [Expansion](./phase_10_expansion.md) | Filling out all 32 flows, prompt tuning, iterate based on evaluation |

---

## Folder Structure

Full directory tree for a domain agent. `shared/` is set up once during Phase 4a and used by all domains. Files annotated with `[Phase 4b]` or `[Phase 4c]` are only created for `pro` or `advanced` tiers respectively.

### `shared/` — Cross-Domain Config

```
shared/
├── shared_defaults.yaml            # Baseline config for all domains         [Phase 1]
├── arguments.py                    # CLI arg definitions (port, env, debug)  [Phase 4a]
└── schemas/                        # Canonical tool schemas                  [Phase 3]
    └── components/                 # Non-manifest component tools
```

### Domain Agent Template

```
<domain>/
├── config.py                       # Config loader — merges shared + domain YAML          [Phase 4a]
├── requirements.txt                # Python dependencies                                  [Phase 4a]
├── run.sh                          # Start backend + frontend                             [Phase 4a]
├── .env.example                    # DATABASE_URL, PORT, ENV, API keys                    [Phase 3]
├── .gitignore                      # __pycache__, node_modules, .env, *.db, dist/, .svelte-kit/
├── Dockerfile                      # Multi-stage build (backend + frontend)               [Phase 9b]
├── docker-compose.yml              # App + Postgres                                       [Phase 9b]
│
├── backend/
│   ├── __init__.py
│   ├── webserver.py                # FastAPI entry point (health, CORS, routers)           [Phase 4a]
│   ├── agent.py                    # Main Agent class (turn pipeline lives here)           [Phase 5]
│   ├── manager.py                  # Agent instance lifecycle (caching, cleanup)           [Phase 5]
│   ├── db.py                       # SQLAlchemy engine + session (reads DATABASE_URL)      [Phase 4a]
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
│   │   ├── chat_service.py         # WebSocket /ws endpoint                               [Phase 4a]
│   │   ├── auth_service.py         # Login, signup, token endpoints                       [Phase 4b]
│   │   ├── oauth_service.py        # OAuth start + callback routes                        [Phase 4c]
│   │   ├── billing_service.py      # Stripe checkout, webhook, status                     [Phase 9c]
│   │   ├── conversation_service.py # Conversation CRUD                                    [Phase 4a]
│   │   └── health_service.py       # GET /health                                          [Phase 4a]
│   │
│   ├── middleware/                  #                                                      [Phase 4b]
│   │   ├── auth_middleware.py      # JWT validation + token refresh                       [Phase 4b]
│   │   └── activity_middleware.py  # User activity tracking                               [Phase 4b]
│   │
│   ├── auth/                       #                                                      [Phase 4b]
│   │   ├── jwt_helpers.py          # JWT sign, decode, cookie management                  [Phase 4b]
│   │   ├── user_fields.py          # Pydantic models for signup/login                     [Phase 4b]
│   │   └── oauth_helpers.py        # PKCE, token exchange, token refresh                  [Phase 4c]
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
│   ├── tables.py                   # SQLAlchemy ORM models (Conversation, etc.)            [Phase 4a]
│   └── seed_data.json              # Initial data (intents, flows)                        [Phase 2]
│
├── monitoring/                     #                                                      [Phase 9c]
│   └── prometheus.yml              # Prometheus scrape config                             [Phase 9c]
│
├── frontend/                       # SvelteKit 2 (Svelte 5) + Tailwind CSS               [Phase 9a]
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
│   │       ├── +page.svelte        # Main app shell (username prompt in basic)            [Phase 9a]
│   │       ├── login/              # Email + password login                               [Phase 9b]
│   │       ├── signup/             # Email + password signup                              [Phase 9b]
│   │       ├── logout/             # Clear cookie, redirect                               [Phase 9b]
│   │       └── billing/            # Subscription management                              [Phase 9c]
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

- **Tier-conditional files**: Files annotated `[Phase 4b]` or `[Phase 9b]` are only created for `pro`/`advanced` tiers. Files annotated `[Phase 4c]` or `[Phase 9c]` are only created for `advanced` tier. All phases are incremental — `pro` builds on `basic`, `advanced` builds on `pro`.
- **`run.sh`** starts both the FastAPI backend and SvelteKit dev server. Each domain runs on its own port.
- **`.env.example`** documents required environment variables. Copy to `.env` and fill in. For `basic` tier, `DATABASE_URL` is SQLite (e.g., `sqlite:///data.db`). For `pro`/`advanced`, it points to Postgres (e.g., `postgresql://localhost/cooking`).
- **`.gitignore`** covers `__pycache__/`, `node_modules/`, `.env`, `dist/`, `.svelte-kit/`, `*.db`.
- **No Alembic** — uses `Base.metadata.create_all()` on startup. Add migrations when schema stabilizes.
- **No shared base classes** — each domain is fully self-contained. `shared/` is config-only.
