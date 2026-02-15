# Phase 4a — Basic Foundation

Set up the server infrastructure, config loader, database, and module shells for the **basic** tier. No authentication, no Postgres — just a running server that can be smoke-tested locally.

## Context

The basic foundation creates the full directory structure and wires together the server, config, database, and stub modules. By the end, the server boots, `/health` returns OK, WebSocket connects (no auth), and the Agent class exists with stubbed methods.

**Tier**: `basic` — local development, SQLite, no login.

**Prerequisites**: Phases 1–3 complete — ontology, YAML config, and tool schemas exist.

**Outputs**: Running FastAPI server with health endpoint, permissive CORS, WebSocket, config loader, SQLite database, module shells, Agent class shell.

**Spec references**: [architecture.md](../architecture.md), [server_setup.md](../utilities/server_setup.md), [configuration.md § Startup Loading & Validation](../utilities/configuration.md), [style_guide.md](../style_guide.md)

---

## Steps

### Step 1 — Create Directory Structure

Create the full domain folder structure. Every file listed here must exist (may be empty initially with `__init__.py` stubs).

```
<domain>/
├── config.py
├── requirements.txt
├── init_backend.sh
├── init_frontend.sh
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
│   │   ├── conversation_service.py
│   │   └── health_service.py
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
│   └── (created in Phase 9a)
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

Note: no `auth/`, `middleware/auth_middleware.py`, or `routers/auth_service.py` — those are added in Phase 4b.

### Step 2 — FastAPI Server Setup

Implement `backend/webserver.py` — the FastAPI entry point.

**Components**:
- FastAPI app instance
- CORS middleware: permissive (all origins) — basic tier is local-only
- Router mounting: health, conversation, chat (WebSocket)
- Startup event: load config, initialize database, create tables

**Health endpoint** (`routers/health_service.py`):
- `GET /health` — returns `{"status": "ok", "config_loaded": true}`
- No deep dependency checks

**CORS** (`CORSMiddleware`): Allow all origins (basic tier runs locally).

### Step 3 — WebSocket Endpoint

Implement `routers/chat_service.py`.

**Connection lifecycle**:
- No JWT validation — accept all connections
- Generate unique conversation ID on connect
- Close codes: `1000` = normal close

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

### Step 4 — Config Loader

Implement `config.py` at the domain root.

**Load sequence**:
1. Read `shared/shared_defaults.yaml`
2. Read `<domain>/schemas/<domain>.yaml`
3. Merge — section-level override (domain section fully replaces shared section)
4. Load ontology — import flow definitions from `ontology.py`, attach as `config.flows`
5. Validate — run merged config through schema validation (see below)
6. Freeze — convert to read-only object

**Schema validation checks** (by section):
- `tier` in `[basic, pro, advanced]`
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

### Step 5 — Database Setup

Implement `backend/db.py` and `database/tables.py`.

**Database**: SQLite. File-based, no external server. `DATABASE_URL` from `.env` (e.g., `sqlite:///data.db`).

**SQLAlchemy setup** (`db.py`):
- Engine + session factory from `DATABASE_URL`
- `Base.metadata.create_all()` on startup (no Alembic for v1)

**Core tables** (`tables.py`):

| Table | PK | Key Columns |
|---|---|---|
| `Agent` | Integer | name (unique, String 32), use_case |
| `Conversation` | UUID | convo_id (seq), name, description |
| `Utterance` | UUID | speaker (enum), utt_id, text, form (enum), operations, entity (JSON) |
| `Intent` | Integer | level (String 8), intent_name (String 32) |
| `DialogueAct` | Integer | dact (String 64), dax (String 4), description |
| `DialogueState` | UUID | utterance_id (FK), intent, dax, flow_stack (JSON), source (enum) |
| `Frame` | UUID | utterance_id (FK), display_type (enum), columns, status, source, code |
| `UserDataSource` | UUID | user_id (String), source_type (enum), provider, name, content (JSON) |
| `ConversationDataSource` | UUID | conversation_id (FK), data_source_id (FK) |

Note: no `User` table (no passwords in basic tier), no `Credential` table (no API key storage). `UserDataSource.user_id` is a plain string (username) instead of FK. `JSONB` columns use `JSON` for SQLite compatibility.

**Enums**: speaker (User/Agent/System), form (text/speech/image/action), dialogue_state_source (nlu/pex), source_type (upload/api).

### Step 6 — Module Shells

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

### Step 7 — Agent Class Shell

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
- Username-based user lookup (no JWT)
- Cleanup on disconnect

### Step 8 — Run Script and Dependencies

**`init_backend.sh`**: Start FastAPI backend in its own terminal tab.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

KEYS_FILE="../../shared/.keys"
if [ -f "$KEYS_FILE" ]; then set -a; source "$KEYS_FILE"; set +a; fi
if [ -f .env ]; then set -a; source .env; set +a; fi

uvicorn backend.webserver:app --host 0.0.0.0 --port "${PORT:-8000}" --reload
```

**`init_frontend.sh`**: Start SvelteKit frontend in a separate terminal tab (created in Phase 9a).

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/frontend"

npm run dev -- --port "${FRONTEND_PORT:-5173}"
```

**`requirements.txt`**: FastAPI, uvicorn, pydantic, sqlalchemy, pyyaml, anthropic. No bcrypt, no python-jose (added in Phase 4b).

**`.env.example`**: DATABASE_URL, PORT, ENV, ANTHROPIC_API_KEY. No JWT_SECRET (added in Phase 4b).

**`.gitignore`**: `__pycache__/`, `node_modules/`, `.env`, `dist/`, `.svelte-kit/`, `*.db`.

### Step 9 — Shared Utilities

**`shared/arguments.py`**: CLI arg definitions (port, env, debug).

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Create | `<domain>/config.py` | Config loader: merge, validate, freeze |
| Create | `<domain>/requirements.txt` | Python dependencies |
| Create | `<domain>/init_backend.sh` | Start backend (separate tab) |
| Create | `<domain>/init_frontend.sh` | Start frontend (separate tab, wired in Phase 9a) |
| Create | `<domain>/.env.example` | Environment variable documentation |
| Create | `<domain>/.gitignore` | Ignore patterns |
| Create | `<domain>/backend/webserver.py` | FastAPI entry point |
| Create | `<domain>/backend/agent.py` | Agent class (turn pipeline) |
| Create | `<domain>/backend/manager.py` | Agent instance lifecycle |
| Create | `<domain>/backend/db.py` | SQLAlchemy engine + session |
| Create | `<domain>/backend/routers/health_service.py` | GET /health |
| Create | `<domain>/backend/routers/chat_service.py` | WebSocket /ws endpoint |
| Create | `<domain>/backend/routers/conversation_service.py` | Conversation CRUD |
| Create | `<domain>/backend/modules/nlu.py` | NLU shell |
| Create | `<domain>/backend/modules/pex.py` | PEX shell |
| Create | `<domain>/backend/modules/res.py` | RES shell |
| Create | `<domain>/backend/components/*.py` | 7 component shells |
| Create | `<domain>/database/tables.py` | SQLAlchemy ORM models |
| Create | `<domain>/tests/conftest.py` | pytest fixtures |
| Create | `shared/arguments.py` | CLI arg definitions |

---

## Verification

- [ ] `./init_backend.sh` starts the server without errors
- [ ] `GET /health` returns `{"status": "ok", "config_loaded": true}`
- [ ] Config loader reads shared + domain YAML, validates, and freezes
- [ ] Config validation fails on invalid values (test with a bad config)
- [ ] Database tables are created on startup (`create_all()`)
- [ ] WebSocket connection succeeds without authentication
- [ ] All module shells exist with stubbed methods
- [ ] Agent class exists with `process_turn()` method
- [ ] All 7 component shells exist as importable classes
- [ ] `.env.example` documents all required environment variables
- [ ] `requirements.txt` lists all dependencies (no bcrypt or python-jose)
