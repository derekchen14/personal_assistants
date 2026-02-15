# Phase 4b — Pro Foundation

Upgrade the basic foundation to production-grade infrastructure: Postgres, JWT authentication, auth routes, rate limiting, and credential storage.

## Context

Phase 4a created a running server with SQLite and no auth. This phase adds the infrastructure needed for a production deployment: a real database, user authentication, and secure credential storage. All changes are incremental on Phase 4a.

**Tier**: `pro` — JWT auth, Postgres, production-ready backend.

**Prerequisites**: Phase 4a complete — server boots, health endpoint works, WebSocket connects.

**Outputs**: Postgres database, User table with bcrypt passwords, JWT auth flow, auth routes (signup/login/logout), rate limiting on auth endpoints, Credential table, JWT-validated WebSocket.

**Spec references**: [server_setup.md](../utilities/server_setup.md), [configuration.md § Tier Awareness](../utilities/configuration.md)

---

## Steps

### Step 1 — Switch to Postgres

Replace SQLite with Postgres.

**`backend/db.py`**:
- Update engine to read `DATABASE_URL` pointing to Postgres (e.g., `postgresql://localhost/<domain>`)
- One Postgres server, one database per domain — schema isolation without operational overhead

**`.env.example`**:
- Update `DATABASE_URL` example to `postgresql://localhost/<domain>`

**`requirements.txt`**:
- Add `psycopg2-binary`

**`database/tables.py`**:
- Replace `JSON` columns with `JSONB` for Postgres-native JSON support

### Step 2 — Add User Table

Add the `User` table to `database/tables.py`.

| Table | PK | Key Columns |
|---|---|---|
| `User` | Integer (seq) | email (unique), password (bcrypt hash) |

- Passwords stored as bcrypt hashes, never plaintext
- `UserDataSource.user_id` changes from plain string to FK → `User.id`

**`requirements.txt`**:
- Add `bcrypt`

### Step 3 — Add JWT Authentication

Implement JWT in `backend/auth/jwt_helpers.py` and `backend/middleware/auth_middleware.py`.

**Create directories**:
```
backend/
├── auth/
│   ├── jwt_helpers.py
│   └── user_fields.py
└── middleware/
    ├── auth_middleware.py
    └── activity_middleware.py
```

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

**User models** (`auth/user_fields.py`):
- Pydantic models for signup/login request validation

**`.env.example`**:
- Add `JWT_SECRET`

**`requirements.txt`**:
- Add `python-jose`

### Step 4 — Add Auth Routes

Implement `backend/routers/auth_service.py`.

- `POST /signup` — create user, hash password with bcrypt, return JWT cookie
- `POST /login` — verify credentials against bcrypt hash, return JWT cookie
- `POST /logout` — clear auth cookie

Mount the auth router in `backend/webserver.py`.

### Step 5 — Add Rate Limiting on Auth Endpoints

Rate-limit auth routes to prevent brute-force attacks.

| Endpoint | Limit |
|---|---|
| `POST /signup` | 5 requests/min per IP |
| `POST /login` | 5 requests/min per IP |

Implementation: in-memory rate limiter (dictionary of IP → timestamps). No external dependency needed for v1.

### Step 6 — Update WebSocket to Validate JWT

Update `backend/routers/chat_service.py`:

- On WebSocket upgrade, extract JWT from `auth_token` cookie
- Validate token signature and expiry
- On failure: close with code `1008` (policy violation)
- On success: extract user ID, proceed with connection

### Step 7 — Add Credential Table

Add the `Credential` table to `database/tables.py` for third-party API key storage.

| Table | PK | Key Columns |
|---|---|---|
| `Credential` | Integer | user_id (FK → User), access_token, refresh_token, vendor, scope, status |

### Step 8 — Update Config

Update domain YAML to reflect pro tier:

- Set `tier: pro`
- Set `session.persistence.backend: postgres`
- Set `memory.user_preferences.backend: postgres`
- Update CORS to explicit allowlist (when `environment: prod`)

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Modify | `<domain>/backend/db.py` | Switch to Postgres engine |
| Modify | `<domain>/database/tables.py` | Add User + Credential tables, JSON → JSONB |
| Create | `<domain>/backend/auth/jwt_helpers.py` | JWT sign, decode, cookie management |
| Create | `<domain>/backend/auth/user_fields.py` | Pydantic models for signup/login |
| Create | `<domain>/backend/middleware/auth_middleware.py` | JWT validation + token refresh |
| Create | `<domain>/backend/middleware/activity_middleware.py` | User activity tracking |
| Create | `<domain>/backend/routers/auth_service.py` | Login, signup, token endpoints |
| Modify | `<domain>/backend/webserver.py` | Mount auth router, add rate limiting |
| Modify | `<domain>/backend/routers/chat_service.py` | Add JWT validation on connect |
| Modify | `<domain>/requirements.txt` | Add psycopg2-binary, bcrypt, python-jose |
| Modify | `<domain>/.env.example` | Add JWT_SECRET, update DATABASE_URL |
| Modify | `<domain>/schemas/<domain>.yaml` | Set tier: pro, persistence backends |

---

## Verification

- [ ] Postgres connection succeeds on startup
- [ ] User table exists with email (unique) and bcrypt password columns
- [ ] `POST /signup` creates user, returns JWT cookie
- [ ] `POST /login` verifies bcrypt password, returns JWT cookie
- [ ] `POST /logout` clears auth cookie
- [ ] Rate limiting blocks 6th auth request within 1 minute
- [ ] WebSocket connection succeeds with valid JWT
- [ ] WebSocket connection fails with `1008` on invalid/missing JWT
- [ ] Credential table exists with user_id FK
- [ ] Domain YAML has `tier: pro`
- [ ] `requirements.txt` includes psycopg2-binary, bcrypt, python-jose
