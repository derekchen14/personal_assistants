# Phase 6 — Staging

Verify the agent works end-to-end with hard-coded test flows before investing in policies and prompts. This phase catches integration bugs early and proves the full pipeline (NLU → PEX → RES) is functional.

## Context

After Phase 5, the agent has all 7 components and 3 modules implemented, but nothing has been tested as a system. Staging exercises the full turn pipeline with canned responses, confirming that the server boots, WebSocket connects, authentication works, and the agent responds to messages. This is the cheapest point to find and fix integration issues.

**Prerequisites**: Phase 5 complete — all components, modules, and Agent orchestrator are implemented.

**Outputs**: Bootable server, WebSocket smoke tests passing, canned responses for core flows, SQLite dev database working.

**Spec references**: [server_setup.md](../utilities/server_setup.md), [configuration.md](../utilities/configuration.md)

---

## Steps

### Step 1 — Verify Server Boots

Ensure the server starts without errors:

```bash
cd <domain> && ./run.sh
curl localhost:<port>/api/v1/health   # → {"status": "ok"}
```

Fix any import errors, missing `__init__.py` files, or configuration issues that prevent startup.

### Step 2 — Database Portability

For development, use SQLite with portable types:

| PostgreSQL Type | SQLite Replacement |
|---|---|
| `UUID` | `String(36)` with `uuid4()` default |
| `JSONB` | `JSON` |
| `ARRAY(String)` | `JSON` (list stored as JSON) |
| `Enum(...)` | `String(16)` |

Tables should auto-create on startup via `Base.metadata.create_all()`. No Alembic yet.

### Step 3 — Lazy LLM Client

The server must boot even without an API key. Use a lazy property pattern:

```python
@property
def client(self) -> anthropic.Anthropic:
    if self._client is None:
        if not self._api_key:
            raise RuntimeError('ANTHROPIC_API_KEY not set.')
        self._client = anthropic.Anthropic(api_key=self._api_key)
    return self._client
```

The client is only instantiated when an LLM call is actually made.

### Step 4 — Canned Responses

Add hard-coded responses for core Converse flows so the agent responds without needing the LLM:

```python
_CANNED = {
    'chat': "Hi! I'm <name>, your <role>...",
    'next_step': "Here's what we can work on next...",
    'status': "Let me check where we are...",
}
```

The canned check runs BEFORE intent routing in PEX so it works regardless of which intent the flow falls under.

### Step 5 — Environment and Keys

- Shared API keys live in `shared/.keys` (not committed to git)
- `run.sh` sources `shared/.keys` before `.env`
- `.gitignore` includes `.keys`, `.env`, `*.db`
- Each domain runs on its own port (starting at 8000, incrementing by 1)

### Step 6 — WebSocket Smoke Test

Test the full round-trip: signup → login → WebSocket connect → send message → receive response.

```
1. POST /api/v1/user/signup → create test user
2. POST /api/v1/user/login  → get auth cookie
3. WS   /api/v1/ws          → connect with auth cookie
4. Send {"currentMessage": "Hello"}      → receive canned chat response
5. Send {"currentMessage": "status"}     → receive canned status response
6. Send {"currentMessage": "what next?"} → receive canned next_step response
```

All 3 messages must receive non-error responses.

### Step 7 — Config Validation

Verify the config loader successfully:
1. Finds and loads `shared/shared_defaults.yaml`
2. Finds and loads `schemas/<domain>.yaml`
3. Merges with section-level override
4. Validates all required sections present
5. Returns a deeply frozen `MappingProxyType`

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Modify | `<domain>/backend/modules/pex.py` | Add `_CANNED` dict for core flows |
| Modify | `<domain>/backend/components/prompt_engineer.py` | Lazy client property |
| Modify | `<domain>/backend/db.py` | SQLite default, portable types |
| Modify | `<domain>/database/tables.py` | Replace PG-specific types with portable ones |
| Modify | `<domain>/run.sh` | Source `shared/.keys` before `.env` |
| Create | `<domain>/schemas/__init__.py` | Package init (if missing) |
| Create | `<domain>/database/__init__.py` | Package init (if missing) |

---

## Verification

- [ ] Server boots on assigned port without errors
- [ ] `GET /health` returns `{"status": "ok"}`
- [ ] Server boots without `ANTHROPIC_API_KEY` set
- [ ] Config loads and validates successfully
- [ ] User signup creates a user and returns auth cookie
- [ ] User login returns auth cookie
- [ ] WebSocket connects with valid auth cookie
- [ ] WebSocket rejects connection without auth
- [ ] Canned response for `chat` flow works
- [ ] Canned response for `status` flow works
- [ ] Canned response for `next_step` flow works
- [ ] SQLite database file created on first boot
- [ ] `.keys` file is not tracked by git
