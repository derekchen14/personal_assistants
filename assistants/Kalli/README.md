# Kalli — Onboarding Assistant

Kalli is the first domain agent built on the assistants framework. She's a meta-assistant: she guides users through building other AI agents by collecting requirements, answering architecture questions, and generating config files (ontology.py, domain YAML).

Once Kalli is fully working, she'll be used to design the Blogger domain (and subsequent domains) with human-in-the-loop approval.

## Architecture

Kalli follows the POMDP-based agent architecture defined in `_specs/`. Every user message flows through a three-module pipeline:

```
User message → NLU → PEX → RES → Response
```

- **NLU** (Natural Language Understanding) — Two-step classification: predicts intent (Sonnet), then predicts flow with majority vote (Sonnet + Haiku in parallel). Unanimous agreement boosts confidence +0.15.
- **PEX** (Policy Execution) — Routes to the correct policy file, loads skill templates, invokes tools via agentic loop (Opus).
- **RES** (Response Synthesis) — Template fill → naturalization → display frame assembly.

Seven components support the modules:
- **Dialogue State** — Current intent, flow, slots, confidence
- **Flow Stack** — Active/suspended flow tracking
- **Context Coordinator** — Conversation history, checkpoints
- **Prompt Engineer** — LLM calls, model selection, prompt assembly
- **Display Frame** — Visual block data for the frontend
- **Ambiguity Handler** — Confidence-based clarification triggers
- **Memory Manager** — Scratchpad, user preferences

## Domain

**Intents**: Explore, Provide, Design, Deliver, Converse, Plan, Internal

**48 flows** organized into 3 batches:
- Batch 1 (16 flows, working): chat, next_step, feedback, status, lookup, explain, scope, persona, intent, entity, propose, compose, approve, decline, generate, onboard
- Batch 2 (16 flows, templated but stubbed): preference, endorse, review_lessons, summarize, inspect, teach, revise, revise_flow, suggest_flow, refine, confirm_export, preview, ontology, research, expand, read_spec
- Batch 3 (16 flows, unsupported): style, dismiss, recommend, compare, log, remove, validate, report, package, finalize, redesign, recap, remember, recall, auto_validate, auto_generate

**Tools**: spec_read, config_read, config_write, ontology_generate, yaml_generate, python_execute, lesson_store, lesson_search

## Running

```bash
# From assistants/Kalli/
./run.sh
```

This starts the backend (port 8000) and frontend (port 5173). Requires `ANTHROPIC_API_KEY` set in `shared/.keys`.

Backend only:
```bash
source ../../shared/.keys
python -m uvicorn backend.webserver:app --host 0.0.0.0 --port 8000 --reload
```

Health check:
```bash
curl localhost:8000/api/v1/health
```

## WebSocket Protocol

No authentication required. Connect to `ws://localhost:8000/api/v1/ws`:

1. Send `{"username": "..."}` → receive greeting
2. Send `{"text": "..."}` → receive response

Response shape:
```json
{
  "message": "...",
  "raw_utterance": "...",
  "actions": [],
  "interaction": {"type": "...", "show": false, "data": {}},
  "code_snippet": null,
  "frame": null
}
```

## Directory Structure

```
Kalli/
├── run.sh
├── config.py                    # YAML merge + freeze
├── requirements.txt
├── backend/
│   ├── webserver.py             # FastAPI app, CORS, routers
│   ├── agent.py                 # Turn pipeline orchestrator
│   ├── manager.py               # Agent lifecycle (keyed by username)
│   ├── db.py                    # SQLAlchemy engine (SQLite for dev)
│   ├── modules/
│   │   ├── nlu.py               # Two-step + vote classification
│   │   ├── pex.py               # Policy dispatch + agentic tool loop
│   │   ├── res.py               # Template fill + naturalize + display
│   │   └── policies/            # 7 intent-specific policy files
│   ├── components/              # 7 components (dialogue_state, flow_stack, etc.)
│   ├── prompts/                 # 8 prompt modules (general, for_experts, for_nlu, etc.)
│   └── routers/
│       ├── health_service.py
│       └── chat_service.py      # WebSocket endpoint
├── schemas/
│   ├── ontology.py              # Intent enum, FLOW_CATALOG (48 flows)
│   ├── onboarding.yaml          # Domain config (persona, models, tools, guardrails)
│   └── templates/               # Response templates (base/ + onboarding/ overrides)
├── database/
│   ├── tables.py                # Conversation, Utterance, Lesson, etc. (no User table)
│   └── seed_data.json           # Intent/dact/flow seed data
├── frontend/                    # SvelteKit 2 + Svelte 5 + Tailwind
│   └── src/
│       ├── lib/stores/          # conversation, display, ui, data
│       ├── lib/components/blocks/  # Table, Card, List, Form, Toast, Confirmation
│       ├── lib/utils/websocket.ts
│       └── routes/+page.svelte  # Username prompt + split-panel chat UI
└── shared/                      # → ../../shared/ (shared_defaults.yaml, .keys)
```

## Model Configuration

Defined in `schemas/onboarding.yaml`:

| Call Site | Model | Purpose |
|---|---|---|
| default | claude-sonnet-4-5-20250929 | General calls |
| nlu | claude-sonnet-4-5-20250929 | Intent + flow vote 1 |
| nlu_vote | claude-haiku-4-5-20251001 | Flow vote 2 |
| skill | claude-opus-4-6 | PEX agentic tool loop |
| naturalize | claude-sonnet-4-5 (temp 0.5) | Response naturalization |

## Development Status

Following the 10-phase checklist in `_specs/checklist/start_here.md`.

| Phase | Name | Status |
|---|---|---|
| 1 | User Requirements | Done |
| 2 | Flow Selection | Done |
| 3 | Tool Design | Done |
| 4 | Foundation | Done |
| 5 | Core Agent | Done |
| 6 | Staging | Done |
| 7 | Policies | Done |
| 8 | Prompt Writing | Done |
| 9 | Frontend | In progress |
| 10 | Expansion | Not started |

### Phase 9 — What's Done

- SvelteKit project scaffolded with Tailwind v4
- Vite proxy configured (routes `/api/*` including WebSocket to backend:8000)
- 4 Svelte stores (conversation, display, ui, data)
- WebSocket manager with connection queuing and status callbacks
- Main page: username prompt → split-panel chat (left: conversation, right: blocks)
- 6 building block components (Table, Card, List, Form, Toast, Confirmation)
- `npm run build` succeeds
- WebSocket works through proxy from CLI clients

### Phase 9 — What's Left

- Debug frontend WebSocket in browser (works from CLI, fails in browser — likely a small proxy or handshake issue)
- Verify all block types render correctly with real frame data
- Test layout mode cycling (split/top/bottom)

### Phase 10 — What's Planned

- Enable 16 Batch 2 flows (wire policy methods to skill templates)
- Expand NLU exemplars (10 utterances per flow)
- Evaluate Batch 3 flows for promotion

## Key Files for Context

- `_specs/checklist/start_here.md` — Master checklist overview
- `_specs/checklist/phase_9_deployment.md` — Current phase spec
- `schemas/ontology.py` — All 48 flows with slots, outputs, edge flows
- `backend/prompts/for_experts.py` — NLU exemplars (~32 intent, ~32 flow)
- `backend/prompts/general.py` — System prompt template
