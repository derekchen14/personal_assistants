# Server Setup

Engineering utility for server infrastructure — FastAPI app setup, middleware, and credentials. Lives outside the agent.

Tech stack: FastAPI (async Python) + Pydantic (validation/settings).

## Authentication & Credentials

Keep auth as simple as possible — expected user base is small (2–3 users max).

### JWT Authentication

| Setting | Value |
|---|---|
| Algorithm | HS256 |
| Expiry | 7 days (604800 seconds) |
| Refresh threshold | 1 day before expiry |
| Cookie name | `auth_token` |
| Payload | `{ email, userID, exp }` |

**Cookie strategy**: `httponly`, `secure`, `samesite: strict`, `max_age: 604800`, `path: /`.

**Token extraction priority** (checked in order): Cookie → Bearer header → Query param → Raw Authorization header.

**Token refresh**: Always perform full JWT decode and verification. No unverified decode shortcuts. If refresh fails, the user re-authenticates — do not silently swallow errors.

### Credential Management

- Secure storage and injection of API keys, OAuth tokens, and other secrets
- Never expose credentials in logs, prompts, or agent responses
- v1: plain-string token storage in the `Credential` table (database access controls are the security boundary)

### Scoped Access

- Each domain agent only gets the credentials it needs
- Principle of least privilege: blogger gets CMS tokens, scheduler gets calendar API keys, headhunter gets job board credentials

### OAuth Pattern

Spec the pattern, not specific providers — each domain connects to providers as needed:

- Standard OAuth 2.0 authorization code flow
- PKCE support for providers that require it (e.g., `secrets.token_urlsafe(64)` → SHA-256 → S256 challenge)
- Token storage in `Credential` table with expiry tracking
- Provider configuration lives in domain config (not hardcoded)

### Lazy Token Refresh

For OAuth tokens, check expiry before PEX tool calls. If the token is expired, attempt the OAuth `refresh_token` flow automatically. If the refresh fails, let the tool call fail — PEX `recover()` handles it as a normal tool failure.

API keys have no auto-rotation. If an API key is revoked, the next tool call using it will fail, and PEX `recover()` handles that too.

No background timer, no eager refresh. Fits the turn-based pipeline: credentials are only checked when they're about to be used.

### Rate Limiting

| Endpoint | Limit |
|---|---|
| User signup | 5/minute per IP |
| User login | 5/minute per IP |

## CORS

FastAPI `CORSMiddleware` mounted on the app.

| Environment | Behavior |
|---|---|
| `dev` | Permissive — allow all origins |
| `prod` | Explicit allowlist of permitted origins |

CORS is server-level configuration, not domain-level. It is not set in domain YAML — it's configured alongside other server settings in the FastAPI app initialization.

## Health Endpoint

FastAPI route at `/health`. Returns basic status:

- Server running
- Config loaded

Useful for dev tooling and container orchestration. No deep dependency checks — if something is broken, PEX tool calls will surface it.

## WebSocket Communication

### Connection Lifecycle

- **Auth on connect**: Validate JWT from `auth_token` cookie on WebSocket upgrade
- **Conversation ID**: Generate unique conversation ID on connection open
- **Close codes**: `1008` = auth failure, `1000` = normal close, other = unexpected disconnect
- **Cleanup**: Background task cleanup on disconnect (cancel pending skill executions, flush scratchpad)

### Client → Server Message

```json
{
    "currentMessage": "<user text>",
    "dialogueAct": "<flowDax>",
    "lastAction": "<userAction>",
    "conversation_id": "<conversationId>"
}
```

- `currentMessage` — user text input (routed to NLU `think()`)
- `lastAction` — UI action (routed to NLU `react()`)
- `dialogueAct` — flow context hint from frontend for multi-turn interactions; also used for dev mode (also routed through `react()`)

### Server → Client Messages

Streamed as multiple typed messages per turn. The WebSocket envelope wraps the RES response output structure:

| Type | Source | Content |
|---|---|---|
| `text` | `generate()` | `{message, raw_utterance, code_snippet}` |
| `options` | `generate()` or `clarify()` | `{actions, interaction}` — reply pills, confirmation modals, option selectors |
| `block` | `display()` | `{frame, properties}` — visual building blocks (table, chart, card, etc.) |
| `error` | Any | `{message, code}` — error information |

`text` and `options` have fixed display structure (content changes, structure doesn't). `block` messages are visual building blocks composed by RES `display()`. A single turn may produce multiple messages of different types.

### Client-Side Guard Rails

Defense-in-depth — server-side NLU `prepare()` is authoritative, but the client also validates:

- **Message length**: Truncate to max length before sending (UX feedback)
- **Prompt injection**: Basic client-side detection as a first line of defense
- **Spinner timeout**: Show typing indicator after a configurable delay

## Database Schema

Postgres from day one. One Postgres server, one database per domain (e.g., `createdb cooking`, `createdb recruiting`). Each domain's `.env` sets its own `DATABASE_URL` pointing to its database on the shared server. This gives schema isolation between domains (a bad migration in one domain can't corrupt another) while sharing a single Postgres process for connection pooling, memory, and backups. If cross-domain user accounts are needed, use a small shared `auth` database. ORM models define the persistence layer.

### Core Tables

| Table | PK | Key Columns | Relationships |
|---|---|---|---|
| `User` | Integer (seq) | email (unique), password (bcrypt) | → Credentials, DataSources |
| `Agent` | Integer | name (unique, String 32), use_case | — |
| `Conversation` | UUID | convo_id (seq), name, description | → Utterances, DataSources, Comment |
| `Utterance` | UUID | speaker (enum), utt_id (int), text, form (enum), operations (ARRAY), entity (JSON) | → Conversation, DialogueAct |
| `Intent` | Integer | level (String 8), intent_name (String 32) | → DialogueActs |
| `DialogueAct` | Integer | dact (String 64), dax (String 4), description | → Utterances, Intent |
| `DialogueState` | UUID | utterance_id (FK), intent, dax, flow_stack (JSONB), source (enum nlu/pex) | → Utterance |
| `Frame` | UUID | utterance_id (FK), display_type (enum), columns (ARRAY), status, source (enum), code (Text) | → Utterance |
| `Credential` | Integer | user_id (FK), access_token (unique, indexed), refresh_token, token_expiry, vendor, vendor_id, scope, status | — |
| `UserDataSource` | UUID | user_id (FK, indexed), source_type (enum upload/api), provider, name, size_kb, content (JSONB) | — |
| `ConversationDataSource` | UUID | conversation_id (FK, CASCADE), data_source_id (FK, CASCADE) | → Conversation, UserDataSource |

### Enums

| Enum | Values |
|---|---|
| `speaker` | User, Agent, System |
| `form` | text, speech, image, action |
| `dialogue_state_source` | nlu, pex |
| `display_type` | Domain-specific (e.g., default/derived/dynamic/decision for data analysis) |
| `frame_source` | sql, python, api, interaction, default |
| `source_type` | upload, api |

### Seed Data

Reference seed data for a new domain (update intent names to canonical set):

- Test users for development
- Agent persona with domain-specific name and use_case
- 7 intents: [4 domain-specific] + Converse, Plan, Internal
- Dialogue act entries with hex DAX codes (from flow_selection)
- Flow definitions (32 for v1, up to 48)
