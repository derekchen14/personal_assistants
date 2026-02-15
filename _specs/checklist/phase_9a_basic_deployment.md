# Phase 9a — Basic Deployment

Build the frontend and connect it to the backend end-to-end locally. No login pages — just a username prompt.

## Context

The backend is working with 16+ flows, a full prompt suite, and NLU voting. This phase adds a web frontend so users interact through a browser instead of raw WebSocket messages. This is the **basic** tier deployment: local dev server, no authentication UI.

**Tier**: `basic` — local dev, username prompt, no login/signup pages.

**Prerequisites**: Phase 8 complete — full prompt suite, template registry, working LLM pipeline.

**Outputs**: SvelteKit frontend with building blocks, WebSocket integration, working locally end-to-end.

**Spec references**: [blocks.md](../utilities/blocks.md), [server_setup.md](../utilities/server_setup.md)

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
    │       └── websocket.ts       # WebSocket connection manager
    └── routes/
        ├── +layout.svelte
        └── +page.svelte           # Main application shell
```

No login/signup pages — just a username prompt on the main page.

### Step 2 — Building Blocks

Implement the atomic UI components that render Display Frames.

**Block categories**:

| Category | Components | Inline? |
|---|---|---|
| Data display | Table, Card, List | No (right panel) |
| Input collection | Form, Confirmation | Confirmation: yes |
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

### Step 3 — Frontend State Management

Organize state into 4 store categories:

| Category | Scope | Examples |
|---|---|---|
| Conversation | Current session | WebSocket, messages, typing |
| Data | Active data context | Tab data, pagination, columns |
| UI | Layout and chrome | Layout mode, alerts, loading, sidebar |
| Display | Block rendering | Active block, frame data |

### Step 4 — WebSocket Integration

Connect frontend to the backend WebSocket:

1. User enters username on the main page
2. WebSocket connects to `/api/v1/ws`
3. First message: `{"username": "..."}` → receives greeting
4. Subsequent messages: `{"text": "..."}` → receives response

Handle all server → client message types:

| Type | Content | Rendering |
|---|---|---|
| `text` | `{message, raw_utterance, code_snippet}` | Chat bubble in dialogue panel |
| `options` | `{actions, interaction}` | Reply pills, confirmation modals |
| `block` | `{frame, properties}` | Building block (panel or inline) |
| `error` | `{message, code}` | Error toast (inline) |

### Step 5 — Building Block Components

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
- Emits user interactions as messages back to the WebSocket

### Step 6 — Update `run.sh`

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
| Create | `<domain>/frontend/src/routes/*.svelte` | Main page + layout |
| Modify | `<domain>/run.sh` | Start both backend and frontend |

---

## Verification

- [ ] Frontend builds without errors (`npm run build`)
- [ ] Frontend dev server starts and loads
- [ ] Username prompt appears on load
- [ ] WebSocket connects from frontend to backend
- [ ] Greeting received after entering username
- [ ] Messages send and responses display in chat
- [ ] Building blocks render in correct locations (panel vs. inline)
- [ ] Layout modes work (split, top, bottom)
- [ ] End-to-end: enter username → send message → see response
