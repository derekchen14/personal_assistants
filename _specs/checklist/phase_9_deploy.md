# Phase 9 — Deployment

Build the frontend, set up evaluation, and prepare for production. This phase produces a production-ready agent with a web interface and comprehensive testing.

## Context

The final implementation phase connects the agent to a real frontend, instruments evaluation for ongoing quality assurance, and configures production settings. By the end, the agent is deployable with a complete UI, regression thresholds, user feedback collection, and production hardening.

**Prerequisites**: Phase 8 complete — full prompt suite, template registry, prompt versioning.

**Outputs**: SvelteKit frontend with building blocks, full evaluation pipeline (online + offline), production configuration, containerization.

**Spec references**: [blocks.md](../utilities/blocks.md), [evaluation.md](../utilities/evaluation.md), [server_setup.md](../utilities/server_setup.md), [style_guide.md](../style_guide.md)

---

## Steps

### Step 1 — Frontend Project Setup

Initialize a SvelteKit 2 + Svelte 5 + Tailwind CSS project in `frontend/`.

```
frontend/
├── package.json
├── svelte.config.js
├── vite.config.ts
├── tailwind.config.js
├── src/
│   ├── app.html
│   ├── app.css                # Tailwind base + custom styles
│   ├── lib/
│   │   ├── stores/            # 4 state stores
│   │   ├── components/blocks/ # Building block components
│   │   └── utils/             # WebSocket manager, telemetry
│   └── routes/
│       ├── +layout.svelte
│       ├── +page.svelte       # Main chat interface
│       ├── login/
│       ├── signup/
│       └── logout/
└── static/
```

### Step 2 — State Stores

Create four stores matching the block spec's state management model:

| Store | Scope | Contents |
|---|---|---|
| `conversation` | Current session | WebSocket connection, message history, conversation ID, typing state |
| `data` | Active data context | Active display data, pagination, column properties |
| `ui` | Layout and chrome | Layout mode (top/split/bottom), alerts, loading states, sidebar |
| `display` | Block rendering | Active block, frame data, interaction panels |

### Step 3 — WebSocket Integration

Connect the frontend to the backend WebSocket endpoint (`/ws`):

- Establish WebSocket connection after login (attach `auth_token` cookie)
- Send messages as JSON: `{ conversationId, currentMessage, type }`
- Receive agent responses: `{ body, block_type, frame_data, ... }`
- Handle reconnection on disconnect (exponential backoff)
- Show typing indicator while waiting for response

### Step 4 — Auth Pages

Build login, signup, and logout routes:

- **Signup**: POST `/api/v1/signup` with `{ email, password, first, last }`
- **Login**: POST `/api/v1/login` with `{ email, password }` — sets `auth_token` cookie
- **Logout**: Clear cookie, redirect to login
- Protect all routes except login/signup with auth check



### Step 6 — Layout and Rendering Model

Implement the two-location rendering model:

- **Dialogue panel** (left): Conversation messages + inline blocks
- **Right panel**: Non-inline blocks rendered from display frame data
- **Layout modes**: `top` (dialogue only), `split` (both), `bottom` (right panel only)
- User controls layout mode; agent never changes it

One frame per turn → one block. Multi-visual turns use `keep_going` to split across flows.

### Step 7 — Interaction History

Buffer user interactions between turns:

- Cell edits, column reorders, selections → `interactionHistory` array
- Debounced timer (60 seconds)
- Flush buffer before sending new messages
- Feeds into NLU `react()` as user actions

### Step 8 — Evaluation Pipeline

Set up both online and offline evaluation from [evaluation.md](../utilities/evaluation.md).

**Online (every session)**:
- Signal envelopes emitted by NLU, PEX, RES, and components
- Per-session record: timing, routing, tool execution, ambiguity, prediction quality, self-check, prompt versions, user feedback
- Explicit feedback UI: thumbs up/down on agent responses
- Implicit feedback detection: re-asks, abandonment, corrections

**Offline (dev time / deployment)**:
- Three-pillar E2E evals: Workflow Prediction (NLU), Trajectory Optimization (PEX), Final Output (RES)
- Test case format: JSON conversations with expected flows, tools, and responses
- Scoring: accuracy, trajectory modes (partial/full path, path nodes, full workflow), 5-level rubric
- Regression thresholds: workflow accuracy >2% drop, trajectory >3% drop, output >0.5 level drop

**Self-check gate** (rule-based, runs every turn):
1. Intent drift — predicted vs. completed intent mismatch
2. Slot coverage — required values present in response
3. Empty response — non-empty for user-facing intents
4. Length bounds — within min/max for intent type

### Step 9 — Telemetry

Structured frontend logging to `/api/v1/telemetry`:

- Request/session/conversation IDs
- Log levels: DEBUG through FATAL
- Error stack traces
- GA4 or equivalent for interaction analytics (optional)

### Step 10 — Production Configuration

- **CORS**: Explicit allowlist in prod, permissive in dev
- **JWT**: Read secret from environment, cookie settings (httponly, secure, samesite strict)
- **Rate limiting**: 5/minute per IP on signup and login
- **Database**: Production DATABASE_URL from environment
- **Update `run.sh`**: Start both backend (uvicorn) and frontend (vite dev / node build)

### Step 11 — Containerization

- `Dockerfile` for backend (Python + FastAPI)
- `Dockerfile` for frontend (Node + SvelteKit build)
- `docker-compose.yml` orchestrating both services + database
- Environment variable passthrough for secrets

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Create | `<domain>/frontend/package.json` | SvelteKit + Svelte 5 + Tailwind dependencies |
| Create | `<domain>/frontend/svelte.config.js` | SvelteKit configuration |
| Create | `<domain>/frontend/vite.config.ts` | Vite build configuration |
| Create | `<domain>/frontend/tailwind.config.js` | Tailwind configuration |
| Create | `<domain>/frontend/src/app.html` | HTML shell |
| Create | `<domain>/frontend/src/app.css` | Tailwind imports + custom styles |
| Create | `<domain>/frontend/src/lib/stores/conversation.ts` | Conversation state store |
| Create | `<domain>/frontend/src/lib/stores/data.ts` | Data context store |
| Create | `<domain>/frontend/src/lib/stores/ui.ts` | UI state store |
| Create | `<domain>/frontend/src/lib/stores/display.ts` | Display/block state store |
| Create | `<domain>/frontend/src/lib/utils/websocket.ts` | WebSocket manager |
| Create | `<domain>/frontend/src/lib/utils/telemetry.ts` | Frontend telemetry |
| Create | `<domain>/frontend/src/lib/components/blocks/*.svelte` | Block components (Table, Card, List, Form, Toast, Confirmation) |
| Create | `<domain>/frontend/src/routes/+layout.svelte` | App layout with auth guard |
| Create | `<domain>/frontend/src/routes/+page.svelte` | Main chat interface |
| Create | `<domain>/frontend/src/routes/login/+page.svelte` | Login page |
| Create | `<domain>/frontend/src/routes/signup/+page.svelte` | Signup page |
| Create | `<domain>/frontend/src/routes/logout/+page.svelte` | Logout page |
| Create | `<domain>/backend/utilities/evaluation.py` | Evaluation signal collection + session records |
| Modify | `<domain>/backend/modules/res.py` | Add self-check gate before Step 1 |
| Modify | `<domain>/backend/webserver.py` | Add telemetry endpoint |
| Modify | `<domain>/run.sh` | Start frontend alongside backend |
| Create | `<domain>/Dockerfile` | Backend container |
| Create | `<domain>/frontend/Dockerfile` | Frontend container |
| Create | `<domain>/docker-compose.yml` | Service orchestration |

---

## Verification

- [ ] `npm run dev` in `frontend/` starts SvelteKit dev server
- [ ] Frontend connects to backend WebSocket after login
- [ ] Signup → login → send message → receive response with visual block
- [ ] Block components render correctly in right panel and inline
- [ ] Layout modes (top/split/bottom) switch correctly
- [ ] Auth flow works end-to-end (signup, login, token refresh, logout)
- [ ] Thumbs up/down feedback captured and stored
- [ ] Signal envelopes emitted by all modules during a turn
- [ ] Session records populate correctly after a multi-turn conversation
- [ ] Self-check gate catches intent drift and missing slots
- [ ] Offline eval runner executes test cases and produces scores
- [ ] Regression thresholds flag when metrics drop
- [ ] Telemetry endpoint receives frontend logs
- [ ] `run.sh` starts both backend and frontend
- [ ] `docker-compose up` starts the full stack (if containerized)
- [ ] CORS configured correctly for prod vs dev
- [ ] No credentials exposed in logs or frontend
