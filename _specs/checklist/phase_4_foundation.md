# Phase 4 — Foundation

Set up the server infrastructure, config loader, database, and module shells. This phase produces a running server that can be smoke-tested.

## Context

The foundation phase creates the full directory structure and wires together the server, config, database, and stub modules. By the end, the server boots, `/health` returns OK, WebSocket connects, and the Agent class exists with stubbed methods.

**Prerequisites**: Phases 1–3 complete — ontology, YAML config, and tool schemas exist.

**Outputs**: Running FastAPI server with health endpoint, CORS, auth, WebSocket, config loader, database tables, module shells, Agent class shell.

**Spec references**: [architecture.md](../architecture.md), [server_setup.md](../utilities/server_setup.md), [configuration.md § Startup Loading & Validation](../utilities/configuration.md), [style_guide.md](../style_guide.md)

---

## Steps

### Step 1 — Create Directory Structure

Create the full domain folder structure. Every file listed here must exist (may be empty initially with `__init__.py` stubs).

```
<domain>/
├── config.py
├── requirements.txt
├── run.sh
├── .env.example
├── .gitignore
├── backend/
│   ├── __init__.py
│   ├── webserver.py
│   ├── agent.py
│   ├── manager.py
│   ├── db.py
│   ├── components/
│   │   ├── __init__.py
│   │   ├── dialogue_state.py
│   │   ├── flow_stack.py
│   │   ├── context_coordinator.py
│   │   ├── prompt_engineer.py
│   │   ├── display_frame.py
│   │   ├── ambiguity_handler.py
│   │   └── memory_manager.py
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── nlu.py
│   │   ├── pex.py
│   │   ├── res.py
│   │   └── policies/
│   │       └── __init__.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── chat_service.py
│   │   ├── auth_service.py
│   │   ├── conversation_service.py
│   │   └── health_service.py
│   ├── middleware/
│   │   ├── auth_middleware.py
│   │   └── activity_middleware.py
│   ├── auth/
│   │   ├── jwt_helpers.py
│   │   └── user_fields.py
│   ├── prompts/
│   │   ├── for_nlu.py
│   │   ├── for_pex.py
│   │   ├── for_res.py
│   │   ├── system.py
│   │   └── skills/
│   └── utilities/
│       └── __init__.py
├── utils/
│   └── helper.py
├── schemas/
│   ├── ontology.py
│   ├── <domain>.yaml
│   ├── <tool_id>.json (per tool)
│   └── templates/
│       └── <domain>/
├── database/
│   ├── tables.py
│   └── seed_data.json
├── frontend/
│   └── (created in Phase 8)
└── tests/
    └── conftest.py
```

Also create `shared/` if it doesn't exist:

```
shared/
├── shared_defaults.yaml
├── arguments.py
└── schemas/
    └── components/
```

### Step 2 — FastAPI Server Setup

Implement `backend/webserver.py` — the FastAPI entry point.

**Components**:
- FastAPI app instance
- CORS middleware: permissive in dev, explicit allowlist in prod
- Router mounting: health, auth, conversation, chat (WebSocket)
- Startup event: load config, initialize database, create tables

**Health endpoint** (`routers/health_service.py`):
- `GET /health` — returns `{"status": "ok", "config_loaded": true}`
- No deep dependency checks

**CORS** (`CORSMiddleware`):

| Environment | Behavior |
|---|---|
| `dev` | Allow all origins |
| `prod` | Explicit allowlist of permitted origins |

### Step 3 — Authentication

Implement JWT authentication in `auth/jwt_helpers.py` and `middleware/auth_middleware.py`.

**JWT settings**:

| Setting | Value |
|---|---|
| Algorithm | HS256 |
| Expiry | 7 days (604800 seconds) |
| Refresh threshold | 1 day before expiry |
| Cookie name | `auth_token` |
| Payload | `{ email, userID, exp }` |

**Cookie strategy**: `httponly`, `secure`, `samesite: strict`, `max_age: 604800`, `path: /`.

**Token extraction priority**: Cookie → Bearer header → Query param → Raw Authorization header.

**Auth routes** (`routers/auth_service.py`):
- `POST /signup` — create user, return JWT cookie (rate limited: 5/min per IP)
- `POST /login` — verify credentials, return JWT cookie (rate limited: 5/min per IP)
- `POST /logout` — clear cookie

**User models** (`auth/user_fields.py`):
- Pydantic models for signup/login request validation

### Step 4 — WebSocket Endpoint

Implement `routers/chat_service.py`.

**Connection lifecycle**:
- Validate JWT from `auth_token` cookie on WebSocket upgrade
- Generate unique conversation ID on connect
- Close codes: `1008` = auth failure, `1000` = normal close

**Client → Server message**:
```json
{
    "currentMessage": "<user text>",
    "dialogueAct": "<flowDax>",
    "lastAction": "<userAction>",
    "conversation_id": "<conversationId>"
}
```

- `currentMessage` → NLU `think()`
- `lastAction` → NLU `react()`
- `dialogueAct` → flow context hint (also `react()`)

**Server → Client messages** (typed envelope):

| Type | Source | Content |
|---|---|---|
| `text` | `generate()` | `{message, raw_utterance, code_snippet}` |
| `options` | `generate()` or `clarify()` | `{actions, interaction}` |
| `block` | `display()` | `{frame, properties}` |
| `error` | Any | `{message, code}` |

### Step 5 — Config Loader

Implement `config.py` at the domain root.

**Load sequence**:
1. Read `shared/shared_defaults.yaml`
2. Read `<domain>/schemas/<domain>.yaml`
3. Merge — section-level override (domain section fully replaces shared section)
4. Load ontology — import flow definitions from `ontology.py`, attach as `config.flows`
5. Validate — run merged config through schema validation (see below)
6. Freeze — convert to read-only object

**Schema validation checks** (by section):
- §1 Models: provider in valid set; temperature 0.0–2.0; top_p 0.0–1.0
- §2 Persona: required fields present; response_style in valid set
- §3 Guardrails: categories recognized; patterns compile as regex
- §4 Session: backend in valid set; timeouts > 0
- §5 Memory: similarity_threshold 0.0–1.0; retrieval_top_k >= rerank_top_n
- §6 Resilience: backoff strategy valid; max_attempts >= 1
- §7 Context window: allocation fractions sum to 1.0
- §8–§16: See [configuration.md § Schema Validation Checks](../utilities/configuration.md)

**Cross-cutting checks**: environment is dev/prod; no conflicting dax codes; intent references valid; edge flow names match defined flows; policy paths importable.

If any validation fails, the agent refuses to start.

### Step 6 — Database Setup

Implement `backend/db.py` and `database/tables.py`.

**Database**: Postgres. One database per domain. `DATABASE_URL` from `.env`.

**SQLAlchemy setup** (`db.py`):
- Engine + session factory from `DATABASE_URL`
- `Base.metadata.create_all()` on startup (no Alembic for v1)

**Core tables** (`tables.py`):

| Table | PK | Key Columns |
|---|---|---|
| `User` | Integer (seq) | email (unique), password (bcrypt) |
| `Agent` | Integer | name (unique, String 32), use_case |
| `Conversation` | UUID | convo_id (seq), name, description |
| `Utterance` | UUID | speaker (enum), utt_id, text, form (enum), operations, entity (JSON) |
| `Intent` | Integer | level (String 8), intent_name (String 32) |
| `DialogueAct` | Integer | dact (String 64), dax (String 4), description |
| `DialogueState` | UUID | utterance_id (FK), intent, dax, flow_stack (JSONB), source (enum) |
| `Frame` | UUID | utterance_id (FK), display_type (enum), columns, status, source, code |
| `Credential` | Integer | user_id (FK), access_token, refresh_token, vendor, scope, status |
| `UserDataSource` | UUID | user_id (FK), source_type (enum), provider, name, content (JSONB) |
| `ConversationDataSource` | UUID | conversation_id (FK), data_source_id (FK) |

**Enums**: speaker (User/Agent/System), form (text/speech/image/action), dialogue_state_source (nlu/pex), source_type (upload/api).

### Step 7 — Module Shells

Create stub modules with all entry points. Each module method should log a message and return a placeholder. All modules have error decorators wrapping entry points.

**NLU** (`modules/nlu.py`):
- `prepare()` — pre-hook (7 checks), return pass/fail
- `think()` — intent prediction, flow prediction, slot-filling
- `contemplate()` — re-routing with narrowed search space
- `react()` — lightweight processing for user actions
- `validate()` — post-hook (5 checks)

**PEX** (`modules/pex.py`):
- `check()` — pre-hook (7 checks)
- `execute()` — slot review, tool invocations, result processing, flow completion
- `recover()` — retry, gather context, re-route, escalate
- `verify()` — post-hook (5 checks)

**RES** (`modules/res.py`):
- `start()` — pre-hook (4 checks)
- `respond()` — route to generate/clarify/display
- `generate()` — template fill + naturalize
- `clarify()` — generate clarification questions
- `display()` — render display frames to blocks
- `finish()` — post-hook (4 checks)

### Step 8 — Agent Class Shell

Implement `backend/agent.py` with the turn pipeline stub.

```python
class Agent:
    def __init__(self, config, nlu, pex, res, ...):
        self.config = config
        self.nlu = nlu
        self.pex = pex
        self.res = res
        # World, components, etc.

    async def process_turn(self, message, conversation_id):
        """Turn pipeline: NLU → PEX → RES with keep_going loop."""
        # Step 1: NLU think() or react()
        # Step 2: PEX execute()
        # Step 3: RES respond()
        # Loop if keep_going
        pass
```

**Agent Manager** (`backend/manager.py`):
- Agent instance lifecycle (one per session)
- JWT-based user lookup
- Cleanup on disconnect

### Step 9 — Run Script and Dependencies

**`run.sh`**: Start both FastAPI backend and SvelteKit dev server. Each domain runs on its own port.

```bash
#!/bin/bash
# Start backend
uvicorn backend.webserver:app --host 0.0.0.0 --port ${PORT:-8000} --reload &

# Start frontend (when ready)
# cd frontend && npm run dev &

wait
```

**`requirements.txt`**: FastAPI, uvicorn, pydantic, sqlalchemy, psycopg2-binary, python-jose, bcrypt, pyyaml, anthropic.

**`.env.example`**: DATABASE_URL, PORT, ENV, JWT_SECRET, ANTHROPIC_API_KEY.

**`.gitignore`**: `__pycache__/`, `node_modules/`, `.env`, `dist/`, `.svelte-kit/`.

### Step 10 — Shared Utilities

**`shared/arguments.py`**: CLI arg definitions (port, env, debug).

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Create | `<domain>/config.py` | Config loader: merge, validate, freeze |
| Create | `<domain>/requirements.txt` | Python dependencies |
| Create | `<domain>/run.sh` | Start script |
| Create | `<domain>/.env.example` | Environment variable documentation |
| Create | `<domain>/.gitignore` | Ignore patterns |
| Create | `<domain>/backend/webserver.py` | FastAPI entry point |
| Create | `<domain>/backend/agent.py` | Agent class (turn pipeline) |
| Create | `<domain>/backend/manager.py` | Agent instance lifecycle |
| Create | `<domain>/backend/db.py` | SQLAlchemy engine + session |
| Create | `<domain>/backend/routers/health_service.py` | GET /health |
| Create | `<domain>/backend/routers/auth_service.py` | Login, signup, token endpoints |
| Create | `<domain>/backend/routers/chat_service.py` | WebSocket /ws endpoint |
| Create | `<domain>/backend/routers/conversation_service.py` | Conversation CRUD |
| Create | `<domain>/backend/middleware/auth_middleware.py` | JWT validation |
| Create | `<domain>/backend/middleware/activity_middleware.py` | Activity tracking |
| Create | `<domain>/backend/auth/jwt_helpers.py` | JWT sign, decode, cookies |
| Create | `<domain>/backend/auth/user_fields.py` | Pydantic models |
| Create | `<domain>/backend/modules/nlu.py` | NLU shell |
| Create | `<domain>/backend/modules/pex.py` | PEX shell |
| Create | `<domain>/backend/modules/res.py` | RES shell |
| Create | `<domain>/backend/components/*.py` | 7 component shells |
| Create | `<domain>/database/tables.py` | SQLAlchemy ORM models |
| Create | `<domain>/tests/conftest.py` | pytest fixtures |
| Create | `shared/arguments.py` | CLI arg definitions |

---

## Verification

- [ ] `run.sh` starts the server without errors
- [ ] `GET /health` returns `{"status": "ok", "config_loaded": true}`
- [ ] Config loader reads shared + domain YAML, validates, and freezes
- [ ] Config validation fails on invalid values (test with a bad config)
- [ ] Database tables are created on startup (`create_all()`)
- [ ] WebSocket connection succeeds with valid JWT
- [ ] WebSocket connection fails with `1008` on invalid JWT
- [ ] Signup creates a user and returns JWT cookie
- [ ] Login returns JWT cookie for existing user
- [ ] All module shells exist with stubbed methods
- [ ] Agent class exists with `process_turn()` method
- [ ] All 7 component shells exist as importable classes
- [ ] `.env.example` documents all required environment variables
- [ ] `requirements.txt` lists all dependencies
