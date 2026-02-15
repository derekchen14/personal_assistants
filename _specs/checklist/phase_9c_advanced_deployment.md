# Phase 9c — Advanced Deployment

Add OAuth login buttons, payment integration, monitoring, and production security hardening.

## Context

Phase 9b added login pages and Docker containerization. This phase adds advanced deployment features: OAuth-based login (social login), payment integration, monitoring/observability, and security hardening for production.

**Tier**: `advanced` — OAuth login, payment, monitoring, hardened security.

**Prerequisites**: Phase 9b complete (login pages, Docker work), Phase 4c complete (OAuth flow, provider config exist).

**Outputs**: OAuth login buttons in frontend, Stripe payment integration, monitoring/observability setup, production security hardening.

**Spec references**: [configuration.md § Tier Awareness](../utilities/configuration.md)

---

## Steps

### Step 1 — OAuth Login Buttons

Add provider-specific OAuth login buttons to the login page.

**Frontend changes** (`frontend/src/routes/login/+page.svelte`):
- Add "Sign in with Google", "Sign in with GitHub", etc. buttons
- Each button redirects to `GET /auth/oauth/{provider}/start` (from Phase 4c)
- After OAuth callback, user lands on main page with JWT cookie set

**Dynamic provider list**:
- Frontend fetches available providers from `GET /auth/oauth/providers` (new endpoint)
- Only shows buttons for configured providers
- Provider button styling follows each provider's brand guidelines

**New backend route**:
- `GET /auth/oauth/providers` — returns list of configured provider names from domain YAML `oauth_providers` section

### Step 2 — Payment Integration

Add Stripe (or similar) payment integration for premium features.

**Backend**:

| Route | Purpose |
|---|---|
| `POST /billing/checkout` | Create Stripe checkout session |
| `POST /billing/webhook` | Handle Stripe webhook events |
| `GET /billing/status` | Check user subscription status |

**Database** — add `Subscription` table:

| Table | PK | Key Columns |
|---|---|---|
| `Subscription` | Integer | user_id (FK → User), stripe_customer_id, plan, status, current_period_end |

**Frontend**:
- Billing page or modal showing current plan
- Upgrade button → Stripe checkout
- Plan-gated features check subscription status

**`.env.example`** additions:
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID`

### Step 3 — Monitoring and Observability

Set up production monitoring:

**Application metrics**:
- Request latency (p50, p95, p99)
- WebSocket connection count
- Turn processing time
- LLM call latency and token usage
- Error rates by type

**Infrastructure**:
- Health check endpoint already exists (Phase 4a)
- Add `/metrics` endpoint (Prometheus format) or use OpenTelemetry collector
- Structured JSON logging in production

**Alerting** (documentation only for v1):
- Define alert thresholds: error rate > 5%, p99 latency > 10s, WebSocket drops > 10/min
- Integration points: PagerDuty, Slack, email

**docker-compose.yml** additions (optional):
```yaml
services:
  prometheus:
    image: prom/prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
```

### Step 4 — Production Security Hardening

Additional security measures for advanced deployments:

**HTTP security headers** (add middleware in `webserver.py`):
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy: default-src 'self'`
- `Referrer-Policy: strict-origin-when-cross-origin`

**Input sanitization**:
- Validate and sanitize all user inputs beyond guardrails
- Parameterized queries (already handled by SQLAlchemy ORM)

**Secret management**:
- Document recommended secret management (e.g., Docker secrets, Vault)
- Ensure no secrets in logs (sensitive_data flags already handle this)

**Dependency security**:
- Add `pip-audit` or `safety` to CI pipeline
- Document npm audit for frontend dependencies

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Modify | `<domain>/frontend/src/routes/login/+page.svelte` | Add OAuth login buttons |
| Create | `<domain>/backend/routers/oauth_service.py` | Add providers list endpoint (if not in Phase 4c) |
| Create | `<domain>/backend/routers/billing_service.py` | Stripe checkout, webhook, status |
| Modify | `<domain>/database/tables.py` | Add Subscription table |
| Modify | `<domain>/backend/webserver.py` | Mount billing router, add security headers |
| Create | `<domain>/frontend/src/routes/billing/+page.svelte` | Billing/plan page |
| Create | `<domain>/monitoring/prometheus.yml` | Prometheus config |
| Modify | `<domain>/docker-compose.yml` | Add monitoring services |
| Modify | `<domain>/.env.example` | Add Stripe keys |
| Modify | `<domain>/requirements.txt` | Add stripe, prometheus-client |

---

## Verification

- [ ] OAuth login buttons appear for configured providers
- [ ] OAuth login flow completes end-to-end (redirect → authorize → callback → main page)
- [ ] Provider list endpoint returns only configured providers
- [ ] Stripe checkout session creates successfully
- [ ] Stripe webhook processes subscription events
- [ ] Subscription status reflects in user's billing page
- [ ] Security headers present in all HTTP responses
- [ ] `/metrics` endpoint returns Prometheus-format metrics (if implemented)
- [ ] Structured JSON logs in production mode
- [ ] No secrets appear in application logs
