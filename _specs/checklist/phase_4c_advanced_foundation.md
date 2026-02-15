# Phase 4c — Advanced Foundation

Add OAuth 2.0 authorization code flow, PKCE support, token lifecycle management, and provider configuration.

## Context

Phase 4b added JWT auth and credential storage. This phase extends credentials to support OAuth 2.0 providers, enabling the agent to access third-party APIs on behalf of users (e.g., Google Calendar, GitHub, Stripe).

**Tier**: `advanced` — OAuth 2.0, credential lifecycle, multi-provider auth.

**Prerequisites**: Phase 4b complete — JWT auth works, Credential table exists.

**Outputs**: OAuth 2.0 authorization code flow, PKCE support, token expiry tracking, lazy token refresh, provider configuration in domain YAML.

**Spec references**: [configuration.md § Tier Awareness](../utilities/configuration.md)

---

## Steps

### Step 1 — Add OAuth 2.0 Authorization Code Flow

Implement the standard OAuth 2.0 authorization code grant.

**New routes** (add to `backend/routers/auth_service.py` or a new `oauth_service.py`):

| Route | Purpose |
|---|---|
| `GET /auth/oauth/{provider}/start` | Redirect user to provider's authorization URL |
| `GET /auth/oauth/{provider}/callback` | Handle provider callback, exchange code for tokens |

**Flow**:
1. Client requests `/auth/oauth/{provider}/start`
2. Server generates `state` parameter (CSRF protection), stores in session
3. Server redirects to provider's authorization URL with `client_id`, `redirect_uri`, `scope`, `state`
4. User authorizes at provider
5. Provider redirects to `/auth/oauth/{provider}/callback` with `code` and `state`
6. Server verifies `state`, exchanges `code` for access + refresh tokens
7. Server stores tokens in Credential table, returns success

### Step 2 — PKCE Support

Add Proof Key for Code Exchange (RFC 7636) to the OAuth flow.

- Generate `code_verifier` (random 43–128 character string)
- Derive `code_challenge` = Base64URL(SHA256(`code_verifier`))
- Send `code_challenge` + `code_challenge_method=S256` in authorization request
- Send `code_verifier` in token exchange request
- Store `code_verifier` in server-side session during the flow

### Step 3 — Token Expiry Tracking and Refresh Tokens

Update the `Credential` table:

| Column | Type | Purpose |
|---|---|---|
| `token_expires_at` | DateTime | When the access token expires |
| `refresh_token` | String | OAuth refresh token (already exists, ensure populated) |
| `last_refreshed_at` | DateTime | When the token was last refreshed |

Add a token refresh helper:
- Accept a Credential record
- Check if `token_expires_at` is within a buffer window (e.g., 5 minutes)
- If expiring, use `refresh_token` to obtain a new access token from the provider
- Update `access_token`, `token_expires_at`, `last_refreshed_at` in the database
- If refresh fails (revoked token), update `status` to `expired` and notify user

### Step 4 — Lazy Token Refresh

Integrate token refresh into the PEX execution path.

- Before any PEX tool call that requires an OAuth credential, check token freshness
- If expired or expiring soon, refresh automatically (lazy refresh)
- If refresh fails, surface error to user via RES rather than failing silently

This keeps the refresh logic out of the tool implementations — they just receive a valid token.

### Step 5 — Provider Configuration in Domain YAML

Add an `oauth_providers` section to the domain YAML schema:

```yaml
oauth_providers:
  google:
    client_id: ${GOOGLE_CLIENT_ID}
    client_secret: ${GOOGLE_CLIENT_SECRET}
    authorization_url: https://accounts.google.com/o/oauth2/v2/auth
    token_url: https://oauth2.googleapis.com/token
    scopes: [openid, email, profile, https://www.googleapis.com/auth/calendar]
    pkce: true
  github:
    client_id: ${GITHUB_CLIENT_ID}
    client_secret: ${GITHUB_CLIENT_SECRET}
    authorization_url: https://github.com/login/oauth/authorize
    token_url: https://github.com/login/oauth/access_token
    scopes: [repo, user]
    pkce: false
```

- Provider config uses environment variable interpolation for secrets
- Each provider specifies whether PKCE is required
- Scopes are provider-specific and defined per domain

Update the config loader to validate `oauth_providers` entries.

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Create | `<domain>/backend/routers/oauth_service.py` | OAuth start + callback routes |
| Modify | `<domain>/backend/auth/jwt_helpers.py` | Add state parameter generation/validation |
| Modify | `<domain>/database/tables.py` | Add token_expires_at, last_refreshed_at to Credential |
| Create | `<domain>/backend/auth/oauth_helpers.py` | PKCE, token exchange, token refresh logic |
| Modify | `<domain>/backend/modules/pex.py` | Add lazy token refresh before tool calls |
| Modify | `<domain>/schemas/<domain>.yaml` | Add oauth_providers section |
| Modify | `<domain>/config.py` | Validate oauth_providers entries |
| Modify | `<domain>/.env.example` | Add provider client ID/secret variables |

---

## Verification

- [ ] OAuth start route redirects to provider authorization URL with correct params
- [ ] OAuth callback exchanges code for tokens and stores in Credential table
- [ ] PKCE code_challenge is sent in authorization request
- [ ] PKCE code_verifier is sent in token exchange request
- [ ] Credential table has token_expires_at and last_refreshed_at columns
- [ ] Token refresh works when access token is near expiry
- [ ] Expired refresh token updates credential status to `expired`
- [ ] Lazy refresh triggers before PEX tool calls requiring OAuth
- [ ] Provider configuration loads from domain YAML with env var interpolation
- [ ] Config validation catches invalid oauth_providers entries
