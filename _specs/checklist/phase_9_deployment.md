# Phase 9 — Deployment

Build the frontend, set up evaluation, and prepare for production. This phase produces a production-ready agent with a web interface and comprehensive testing.

## Context

The final phase connects the agent to a real frontend, instruments evaluation for ongoing quality assurance, and configures production settings. By the end, the agent is deployable with a complete UI, regression thresholds, user feedback collection, and production hardening.

**Prerequisites**: Phase 8 complete — full prompt suite, template registry, 16 working flows.

**Outputs**: SvelteKit frontend with building blocks, full evaluation pipeline (online + offline), production configuration, containerization.

**Spec references**: [blocks.md](../utilities/blocks.md), [evaluation.md](../utilities/evaluation.md), [server_setup.md](../utilities/server_setup.md), [style_guide.md](../style_guide.md)

---

## Steps

### Step 1 — Frontend Setup

**Tech stack**: SvelteKit 2, Svelte 5, TypeScript, Tailwind, Node 24.

Create the frontend directory:

```
frontend/
├── package.json
├── svelte.config.js
├── tailwind.config.js
├── tsconfig.json
├── vite.config.ts
└── src/
    ├── app.html
    ├── app.css
    ├── lib/
    │   ├── stores/
    │   │   ├── conversation.ts    # WebSocket, message history, typing state
    │   │   ├── data.ts            # Active data context, pagination
    │   │   ├── ui.ts              # Layout mode, alerts, loading states
    │   │   └── display.ts         # Active block, frame data, chart config
    │   ├── components/
    │   │   ├── blocks/            # Building block components
    │   │   └── shared/            # Common UI components
    │   └── utils/
    │       ├── websocket.ts       # WebSocket connection manager
    │       └── telemetry.ts       # Frontend logging
    └── routes/
        ├── +layout.svelte
        ├── +page.svelte           # Main application shell
        ├── login/+page.svelte
        ├── signup/+page.svelte
        └── logout/+page.svelte
```

### Step 2 — Building Blocks

Implement the atomic UI components that render Display Frames.

**Block categories**:

| Category | Components | Inline? |
|---|---|---|
| Data display | Table, Chart, Card, List | No (right panel) |
| Input collection | Form, Selector, DatePicker, Confirmation | Confirmation: yes |
| Navigation | Tabs, Breadcrumbs, Pagination | No |
| Feedback | Toast, Progress, Loading | Yes (inline) |

**Key rules**:
- Each block type has a baked-in `inline` attribute — inline blocks render in the conversation stream, others on the right panel
- Display types map directly to atomic blocks (no intermediate composite layer)
- One frame = one block per turn

**Rendering model**:

| Location | Behavior |
|---|---|
| Right panel | Default. Persistent panel alongside conversation (like Claude's artifacts) |
| Inline | Within conversation stream, interspersed with text |

**Layout modes** (user-controlled):

| Mode | Description |
|---|---|
| `split` | Both panels visible (default) |
| `top` | Dialogue panel only |
| `bottom` | Right panel only |

### Step 3 — Responsive Hints

Blocks carry rendering hints consumed by the frontend (agent-unaware).

**v1 dimensions**:

| Dimension | Values | Example |
|---|---|---|
| Viewport | `mobile`, `desktop` | Table → scrollable card list on mobile |
| Color scheme | `dark`, `light` | Chart palette adjusted for contrast |

**Resolution order**: per-block hints → global defaults → apply based on current viewport/color.

### Step 4 — Frontend State Management

Organize state into 4 store categories:

| Category | Scope | Examples |
|---|---|---|
| Conversation | Current session | WebSocket, messages, conversation ID, typing |
| Data | Active data context | Tab data, pagination, columns |
| UI | Layout and chrome | Layout mode, alerts, loading, sidebar |
| Display | Block rendering | Active block, frame data, chart config |

**Auto-save**: User interactions between turns buffered in `interactionHistory` with 60s debounce. Flushed before new messages. Feeds into NLU `react()`.

**Client-side guards**:
- Message length: truncate to max before sending
- Prompt injection: basic client-side detection
- Spinner timeout: configurable delay

### Step 5 — WebSocket Integration

Connect frontend to the backend WebSocket. Handle all server → client message types:

| Type | Content | Rendering |
|---|---|---|
| `text` | `{message, raw_utterance, code_snippet}` | Chat bubble in dialogue panel |
| `options` | `{actions, interaction}` | Reply pills, confirmation modals |
| `block` | `{frame, properties}` | Building block (panel or inline) |
| `error` | `{message, code}` | Error toast (inline) |

### Step 6 — Panel Interactions

User actions on panel-rendered blocks (clicking table rows, submitting forms, selecting chart points) enter the pipeline as user actions via NLU `react()`.

**Deliverable persistence**: Published outputs (blog posts, scheduled events, submitted applications) are stored in domain-specific external systems — not in blocks or Memory Manager. Blocks are transient views.

### Step 7 — Evaluation Infrastructure

Set up the full evaluation pipeline.

#### Signal Collection

Every module and component emits structured signals via signal envelopes:

```python
{
    'signal_id': str,
    'source': str,              # component name
    'signal_type': str,
    'timestamp': float,
    'session_id': str,
    'turn_id': str | None,
    'flow_id': str | None,
    'prompt_version_id': str | None,
    'environment': str,         # dev | prod
    'payload': dict
}
```

**Key signals**: NLU predictions + confidence, flow prediction + votes, tool execution results, ambiguity declarations, RES template fill coverage, self-check results, prompt version IDs.

#### Online Evaluation (Per-Session Metrics)

Session record schema:

| Group | Fields |
|---|---|
| Timing | Turn latencies per component, total session duration |
| Routing | Flows attempted/completed/invalid, re-route count |
| Tool Execution | Calls, successes, failures, retries by tool_id |
| Ambiguity | Declarations by level, resolution outcomes |
| Prediction Quality | Vote rounds, confidence scores, agreement ratios |
| Self-Check | Rule-based results (4), LLM-based (if enabled) |
| Prompt Versions | `{template_id.version: call_count}` map |

### Step 8 — Offline Evaluation (Three Pillars)

#### Pillar 1: Workflow Prediction (NLU)

Did the agent predict the correct flow?
- Metric: Accuracy (0–100%)
- Granularity: flow level (~64 options)

#### Pillar 2: Trajectory Optimization (PEX)

Did the agent choose the correct tool calls?
- 4 scoring modes: partial path, full path, path nodes, full workflow
- Default: full workflow (strictest)

#### Pillar 3: Final Output (RES)

Did the agent produce the correct response?
- 5-level rubric: Perfect, Great, Good, Adequate, Poor
- Simple cases: rule-based value matching
- Complex cases: LLM-as-judge (Haiku)

#### Test Case Format

JSON conversation format with multi-turn scenarios:

```json
[{
   "convo_id": 2001,
   "domain": "<domain>",
   "available_data": [...],
   "turns": [
      {"turn_count": 1, "role": "user", "utterance": "..."},
      {"turn_count": 2, "role": "agent", "context": {...}, "actions": [...], "utterance": "..."}
   ]
}]
```

### Step 9 — Regression Testing

**Triggers**: Prompt version change, `ontology.py` change, domain YAML change, policy code change, manual run.

**Thresholds**:

| Metric | Regression Threshold |
|---|---|
| Workflow prediction accuracy | > 2% drop |
| Trajectory (full workflow) | > 3% drop |
| Final output (mean rubric) | > 0.5 level drop |
| Tool success rate | > 1% drop |
| Mean latency | > 20% increase |
| Self-check failure rate | Any increase |

### Step 10 — Building Block Components

Implement the block types from [blocks.md](../utilities/blocks.md):

| Block | Description | Inline? |
|---|---|---|
| `table` | Data tables with sorting, filtering | No (right panel) |
| `card` | Summary cards for entities | No (right panel) |
| `list` | Ordered/unordered lists | No (right panel) |
| `form` | Input forms for slot collection | No (right panel) |
| `toast` | Ephemeral notifications | Yes (inline) |
| `confirmation` | Yes/no prompts | Yes (inline) |

Each block component:
- Accepts frame data as props
- Handles its own responsive hints (viewport, color scheme)
- Emits user interactions as messages back to the WebSocket

### Step 11 — Production Configuration

**Environment-specific settings**:

| Setting | Dev | Prod |
|---|---|---|
| CORS | Allow all origins | Explicit allowlist |
| Self-check LLM | Enabled | Advisory only (emit signal, don't gate) |
| Logging level | DEBUG | INFO |
| Rate limiting | Relaxed | Enforced (5/min login, 5/min signup) |

**OAuth pattern** (per domain):
- Standard OAuth 2.0 authorization code flow
- PKCE support for providers requiring it
- Token storage in Credential table with expiry tracking
- Lazy token refresh: check before PEX tool calls, refresh if expired

**Production hardening**:
- JWT secret from environment variable (never hardcoded)
- Database connection pooling
- Structured logging (JSON format)
- Health endpoint for container orchestration

### Step 12 — Containerization

**Docker setup**:
- Backend: Python 3.14 image, install from requirements.txt
- Frontend: Node 24 image, SvelteKit build
- Database: Postgres container
- Compose file: orchestrate all services

**Environment management**:
- `.env` for secrets (never committed)
- `docker-compose.yml` with service definitions
- Domain isolation: one database per domain

### Step 13 — Telemetry Endpoint

Frontend logging to `/api/v1/telemetry`:
- Request/session/conversation IDs
- Log levels: DEBUG through FATAL
- Error stack traces
- Structured JSON format

### Step 14 — Update `run.sh`

Update to start both backend and frontend:

```bash
#!/bin/bash
# Start backend
uvicorn backend.webserver:app --host 0.0.0.0 --port ${PORT:-8000} --reload &

# Start frontend
cd frontend && npm run dev -- --port ${FRONTEND_PORT:-5173} &

wait
```

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Create | `<domain>/frontend/package.json` | SvelteKit project config |
| Create | `<domain>/frontend/svelte.config.js` | SvelteKit config |
| Create | `<domain>/frontend/tailwind.config.js` | Tailwind config |
| Create | `<domain>/frontend/src/lib/stores/*.ts` | 4 store categories |
| Create | `<domain>/frontend/src/lib/components/blocks/*.svelte` | Building block components |
| Create | `<domain>/frontend/src/lib/utils/websocket.ts` | WebSocket manager |
| Create | `<domain>/frontend/src/lib/utils/telemetry.ts` | Frontend logging |
| Create | `<domain>/frontend/src/routes/*.svelte` | Pages: main, login, signup, logout |
| Create | `<domain>/tests/test_eval.py` | Evaluation pipeline tests |
| Create | `<domain>/tests/eval_data/*.json` | Test case data (three pillars) |
| Create | `Dockerfile` | Backend container |
| Create | `Dockerfile.frontend` | Frontend container |
| Create | `docker-compose.yml` | Service orchestration |
| Modify | `<domain>/run.sh` | Start both backend and frontend |
| Modify | `<domain>/backend/routers/health_service.py` | Add telemetry endpoint |

---

## Verification

- [ ] Frontend builds without errors (`npm run build`)
- [ ] Frontend dev server starts and loads
- [ ] WebSocket connects from frontend to backend
- [ ] All server → client message types render correctly (text, options, block, error)
- [ ] Building blocks render in correct locations (panel vs. inline)
- [ ] Layout modes work (split, top, bottom)
- [ ] Responsive hints apply correctly (mobile/desktop, dark/light)
- [ ] User interactions on blocks route to NLU `react()`
- [ ] Signal envelopes emitted from all modules and components
- [ ] Session records accumulate per-session metrics correctly-
- [ ] Three-pillar E2E evals produce scores
- [ ] Regression thresholds defined and enforceable
- [ ] Per-flow tests: unit, integration, edge flow confusion all passing
- [ ] Production config: CORS restricted, rate limiting active, JWT from env
- [ ] Docker containers build and run
- [ ] `docker-compose up` starts all services
- [ ] Health endpoint returns OK in containerized environment
- [ ] End-to-end: user can login, send a message, see a response with a visual block
