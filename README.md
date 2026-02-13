# Agent Architecture Specs

## What This Is

A POMDP-based agent architecture specification. These are design documents, not runnable code. The architecture models user interaction as a partially observable Markov decision process where observations are user utterances and hidden state is user intent.

## Purpose

Starting point for building AI agents in custom domains. The path:

1. Read [architecture.md](./architecture.md) for the full system overview
2. Define your domain ontology — intents, flows, and dax codes (see [Flow Selection](./utilities/flow_selection.md))
3. Write policies for each flow (see [PEX § Policies and Tools](./modules/pex.md))
4. Configure your domain YAML — tools, persona, display, thresholds (see [Configuration § Domain Config Schema](./utilities/configuration.md))
5. Follow the [build checklist](./build_checklist.md) to implement end-to-end

## Spec Map

### Architecture

- [architecture.md](./architecture.md) — Overall structure: modules, orchestrator, components, utilities

### Modules

- [modules/nlu.md](./modules/nlu.md) — Natural Language Understanding: intent/flow prediction, slot-filling, re-routing
- [modules/pex.md](./modules/pex.md) — Policy Executor: tool execution, recovery, per-flow policies
- [modules/res.md](./modules/res.md) — Response Generator: template-fill, naturalization, display rendering

### Core Components

- [components/dialogue_state.md](./components/dialogue_state.md) — Predicted state, slot-filling, flow stack, flags, snapshots
- [components/flow_stack.md](./components/flow_stack.md) — Stack-based flow management, lifecycle, concurrency, fallback
- [components/context_coordinator.md](./components/context_coordinator.md) — Conversation history, retrieval, checkpoints
- [components/prompt_engineer.md](./components/prompt_engineer.md) — Model-agnostic LLM interface, guardrails, streaming
- [components/display_frame.md](./components/display_frame.md) — Data-display decoupling, core entities for rendering
- [components/ambiguity_handler.md](./components/ambiguity_handler.md) — Uncertainty declaration, tracking, resolution at four levels
- [components/memory_manager.md](./components/memory_manager.md) — Three-tier cache: session scratchpad, user preferences, business context

### Utilities

- [utilities/evaluation.md](./utilities/evaluation.md) — Signals, self-check gate, online/offline evals, feedback
- [utilities/server_setup.md](./utilities/server_setup.md) — FastAPI app, middleware, CORS, credentials
- [utilities/configuration.md](./utilities/configuration.md) — Per-domain YAML config, shared defaults, schema validation
- [utilities/flow_selection.md](./utilities/flow_selection.md) — Compositional dact grammar, builder process, domain examples
- [utilities/tool_smith.md](./utilities/tool_smith.md) — Tool manifest design: flow-to-tool mapping, schemas, error contracts
- [utilities/blocks.md](./utilities/blocks.md) — Building blocks for frontend rendering

### Guides

- [style_guide.md](./style_guide.md) — Coding conventions and project standards
- [build_checklist.md](./build_checklist.md) — Phased implementation checklist

## Open Questions

Unresolved design decisions to address before or during implementation:

- **Memory Manager**: Summarization trigger threshold is TBD. Chunking strategy for business context vector retrieval needs design.
- **Templates**: `{% if %}` syntax used in template examples but the templating engine is never named (Jinja2? custom?).
- **Frontend**: No architecture spec, no state management spec, no backend connection spec. Building blocks define the UI components but not the app shell.
- **Persistence**: No database technology chosen for dialogue state, user preferences, business context, or checkpoints.
- **Deployment**: No containerization, scaling, or multi-tenant spec.
- **NLU `react()`**: Only 4 lines of description. Needs more detail on which user actions it handles and how it maps them to flows.

## Queued Domains

Three domains queued for implementation beyond the cooking example used throughout the specs.

| Domain | Persona | Key Entities |
|---|---|---|
| Blogger | Conversational; creative writing, SEO, content strategy | post, section, draft |
| Scheduler | Efficient; calendar management, time optimization | event, calendar, time_block |
| Recruiter | Professional; recruiting, job market, candidate evaluation | listing, application, resume |

See [Configuration § Cross-Domain Comparison](./utilities/configuration.md) for how domain configs differ across persona, display, tools, and auth scopes.

## Folder Structure

Each domain agent is a standalone server (FastAPI backend + SvelteKit frontend) with its own auth, config, and database. No shared base classes — domains are fully self-contained.

```
assistants/
├── _specs/                         # Design documents
│   └── scaffolding/                # Reference implementation (read-only)
├── shared/                         # Cross-domain config only
│   ├── shared_defaults.yaml        # Baseline config for all domains
│   ├── arguments.py                # CLI arg definitions (port, env, debug)
│   └── schemas/                    # Canonical tool schemas
│
├── blogger/                        # Domain agents (each follows template below)
├── scheduler/
└── recruiter/
```

**Domain agent template** — each domain folder contains:

```
<domain>/
├── config.py                       # Config loader + domain definitions
├── run.sh                          # Start backend + frontend
├── backend/                        # FastAPI app
│   ├── components/                 #   7 core components
│   ├── modules/                    #   NLU, PEX, RES + policies/
│   ├── routers/                    #   WebSocket, auth, conversation, health
│   ├── middleware/                 #   JWT validation, activity tracking
│   ├── auth/                       #   JWT helpers, user models
│   └── prompts/                    #   Prompt assembly (NLU, PEX, RES, system)
│       └── skills/                 #   Per-flow skill templates (markdown)
├── schemas/                        # Domain definitions + tool schemas
│   ├── ontology.py                 #   Intents, flows, dact codes, constants
│   ├── <domain>.yaml               #   Persona, guardrails, key_entities
│   └── templates/<domain>/         #   RES response templates
├── utils/                          # Domain helpers (dax2dact, flow2dax, etc.)
├── database/                       # SQLAlchemy models + seed data
├── frontend/                       # SvelteKit 2, Svelte 5, Tailwind
│   └── src/routes/                 #   login, signup, logout, application shell
└── tests/                          # pytest (test_*.py)
```

See [build_checklist.md § Folder Structure](./build_checklist.md) for the full annotated tree with per-file descriptions and phase annotations.
