# Phase 9b — Pro Deployment

Add login/signup pages, Docker containerization, and production configuration to the frontend and deployment pipeline.

## Context

Phase 9a created a working frontend with a username prompt and local dev server. This phase upgrades to a production-ready deployment: login/signup UI, Docker containers, strict CORS, and HTTPS preparation.

**Tier**: `pro` — login pages, Docker, production config.

**Prerequisites**: Phase 9a complete (frontend works locally), Phase 4b complete (JWT auth, auth routes exist).

**Outputs**: Login/signup/logout pages, Dockerfile, docker-compose.yml, production config, HTTPS setup notes.

**Spec references**: [server_setup.md](../utilities/server_setup.md), [configuration.md § Tier Awareness](../utilities/configuration.md)

---

## Steps

### Step 1 — Add Login/Signup/Logout Pages

Add authentication pages to the SvelteKit frontend:

```
frontend/src/routes/
├── login/
│   └── +page.svelte              # Email + password form → POST /login
├── signup/
│   └── +page.svelte              # Email + password form → POST /signup
└── logout/
    └── +page.svelte              # POST /logout, redirect to login
```

**Login page**:
- Email + password form
- Submit → `POST /login` → receive JWT cookie → redirect to main page
- Error handling: invalid credentials, rate limit exceeded
- Link to signup page

**Signup page**:
- Email + password form (with password confirmation)
- Submit → `POST /signup` → receive JWT cookie → redirect to main page
- Error handling: duplicate email, weak password, rate limit exceeded
- Link to login page

**Logout page**:
- `POST /logout` → clear cookie → redirect to login page

**Auth guard**:
- Main page (`+page.svelte`) checks for valid JWT cookie on load
- If no valid cookie, redirect to login page
- Update WebSocket connection to include JWT cookie

### Step 2 — Create Dockerfile

Multi-stage Dockerfile for the full application:

```dockerfile
# Stage 1: Build frontend
FROM node:24-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Production
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./backend/
COPY config.py ./
COPY schemas/ ./schemas/
COPY database/ ./database/
COPY shared/ /app/shared/
COPY --from=frontend-build /app/frontend/build ./frontend/build
EXPOSE 8000
CMD ["uvicorn", "backend.webserver:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 3 — Create docker-compose.yml

```yaml
services:
  app:
    build: .
    ports:
      - "${PORT:-8000}:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${DB_NAME}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-postgres}"]
      interval: 5s
      timeout: 3s
      retries: 5
volumes:
  pgdata:
```

### Step 4 — Production Configuration

Update domain YAML for production deployment:

```yaml
environment: prod
tier: pro
```

**CORS** (in `backend/webserver.py`):
- When `environment: prod`, switch from permissive to explicit allowlist
- Allowlist configured via environment variable `CORS_ORIGINS` (comma-separated)

**Logging**:
- `level: INFO` in production (not DEBUG)
- `sensitive_data`: all `false`

**`.env.example`** additions:
- `CORS_ORIGINS` — comma-separated allowed origins
- `DB_NAME`, `DB_USER`, `DB_PASSWORD` — for docker-compose

### Step 5 — HTTPS Setup Notes

Document HTTPS setup (not automated in v1):

- Reverse proxy (nginx/Caddy) terminates TLS in front of the app container
- `secure` flag on JWT cookies requires HTTPS
- WebSocket upgrades work through the reverse proxy
- Let's Encrypt for certificate provisioning

### Step 6 — Update `run.sh` for Production Mode

```bash
#!/bin/bash
if [ "$ENV" = "prod" ]; then
    # Production: serve built frontend from backend
    uvicorn backend.webserver:app --host 0.0.0.0 --port ${PORT:-8000}
else
    # Development: hot-reload both
    uvicorn backend.webserver:app --host 0.0.0.0 --port ${PORT:-8000} --reload &
    cd frontend && npm run dev -- --port ${FRONTEND_PORT:-5173} &
    wait
fi
```

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Create | `<domain>/frontend/src/routes/login/+page.svelte` | Login page |
| Create | `<domain>/frontend/src/routes/signup/+page.svelte` | Signup page |
| Create | `<domain>/frontend/src/routes/logout/+page.svelte` | Logout page |
| Modify | `<domain>/frontend/src/routes/+page.svelte` | Add auth guard |
| Create | `<domain>/Dockerfile` | Multi-stage build |
| Create | `<domain>/docker-compose.yml` | App + Postgres |
| Modify | `<domain>/backend/webserver.py` | CORS allowlist for prod |
| Modify | `<domain>/run.sh` | Production mode support |
| Modify | `<domain>/.env.example` | Add CORS_ORIGINS, DB_NAME, DB_USER, DB_PASSWORD |

---

## Verification

- [ ] Login page renders and submits to `POST /login`
- [ ] Signup page renders and submits to `POST /signup`
- [ ] Logout clears cookie and redirects to login
- [ ] Unauthenticated users are redirected to login page
- [ ] `docker-compose up` starts app + Postgres
- [ ] App connects to Postgres in Docker
- [ ] Health endpoint returns OK from Docker container
- [ ] CORS is strict in production mode (rejects disallowed origins)
- [ ] `run.sh` works in both dev and prod modes
- [ ] Frontend build succeeds in Docker multi-stage build
