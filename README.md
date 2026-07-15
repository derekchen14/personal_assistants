# [Assistant Factory](www.assistantfactory.io) 🤖🏭

## Introduction

Assistant Factory is a generator that builds custom AI agents for specific personal and business needs at the click of a button. Our onboarding assistant is called Kalli, who will guide you through the process of building your own agent. She will ask you a few questions about your needs and help you build your agent. Once your agent is built, you can invite your team members to use it by simply sharing the agent's URL. Our agents are powerful and reliable due to three key innovations:
  1. **Explicit Understanding**: Our assistants follow a POMDP-based architecture that models user interaction as a sequence of flows where observations are user utterances and hidden state is the user intent. This neuro-symbolic structure explicitly predicts and tracks user beliefs over time, taking advantage of traditional symbolic AI planning along with modern LLM-based deep learning.
  2. **Ambiguity Handling**: Real-life conversations are often ambiguous due to conflicting information, incomplete specification, or simply the complexity of human language. Our assistants treat ambiguity as a first-class citizen by directly measuring confidence, recognizing levels of uncertainty, and asking for clarifications when needed.
  3. **Synthetic Data Augmentation**: Our assistants are trained using a combination of real and synthetic data to improve their performance in handling rare events and improving generalization. This allows our assistants for customization to any specific user needs without the need for extensive real data.

## Getting Oriented

This README is the starting point for every coding session. The sections down through Folder
Structure are general background that applies to every task. Then find your task — data generation,
backend features, or end-to-end interaction — and focus on the specs and code its section names.

1. Read [architecture.md](./_specs/architecture.md) — the system overview and the canonical vocabulary. Its terms are binding: always use an existing noun, verb, or status over a synonym.
2. Active development happens in `assistants/Hugo/` (blog writing). Read its [AGENTS.md](./assistants/Hugo/AGENTS.md) before coding.
3. Module and component behavior is specified in `_specs/modules/` and `_specs/components/` (map below). The specs are normative — code follows them, not the other way around.

**Terminology**:
An assistant is the overall personalized AI system built for a specific user or team within a domain. The Assistant is deterministic code composed of three modules: NLU, PEX, and MEM. An *agent* is the probabilistic LLM loop inside each module, driving decisions such as which tools to call or which policies to execute. In other words, the assistant is the controlled outer product, while an agent is the inner implementation of each module. The PEX module contains a set of policies, where each policy has a 1-to-1 mapping to a flow. Each flow represents the task and holds the the associated information related to that task. Each policy contains a *sub-agent* which has access to its own scoped set of tools for completing the task. The "module to agent :: policy to sub-agent" relationship are identical as code wrappers around agentic loops.

| Assistant | Domain | Key Entities |
|---|---|---|
| Hugo | Blog writing: drafting, revising, publishing | post, section, snippet, channel |
| Dana | Data analysis: cleaning, transforming, reporting | table, row, column |
| Kalli | Onboarding: guides new users through building their own assistant | assistant, requirement, spec |
| Rowan | Housing or Apartment search | listing, room, broker |

## Spec Map

- [architecture.md](./_specs/architecture.md) — The canonical vocabulary map: modules, components, nouns, verbs, statuses
- [style_guide.md](./_specs/style_guide.md) — Coding conventions and project standards

### Modules

- [modules/nlu.md](./_specs/modules/nlu.md) — Natural Language Understanding: intent/flow prediction, slot-filling, ambiguity
- [modules/pex.md](./_specs/modules/pex.md) — Policy Execution: per-flow policies, tool calling, reply composition
- [modules/mem.md](./_specs/modules/mem.md) — Memory Extension: three levels — context, preferences, business knowledge
- [modules/canonical_turn.md](./_specs/modules/canonical_turn.md) — The full-turn diagram: Assistant wrapper, three module lanes

### Core Components

- [components/dialogue_state.md](./_specs/components/dialogue_state.md) — The single belief object: intent, flows, slots, grounding
- [components/ambiguity_handler.md](./_specs/components/ambiguity_handler.md) — Recognize, recover, and resolve uncertainty at four levels
- [components/workflow_planner.md](./_specs/components/workflow_planner.md) — FlowStack lifecycle, plan decomposition, turn-end invariant
- [components/session_scratchpad.md](./_specs/components/session_scratchpad.md) — Cross-flow working ledger of entries within a session
- [components/task_artifact.md](./_specs/components/task_artifact.md) — The deliverable a policy hands back: parts and blocks
- [components/context_coordinator.md](./_specs/components/context_coordinator.md) — Conversation history, checkpoints, compaction (L1)
- [components/user_preferences.md](./_specs/components/user_preferences.md) — Durable preference records, endorsed or predicted (L2)
- [components/business_context.md](./_specs/components/business_context.md) — Business Knowledge document retrieval (L3)
- [components/prompt_engineer.md](./_specs/components/prompt_engineer.md) — Model-agnostic LLM interface: call, parse, retry

### Utilities

- [utilities/evaluation_suite.md](./_specs/utilities/evaluation_suite.md) — Three tiers: Model Unit Tests, Observability Traces, E2E Agent Evals
- [utilities/server_setup.md](./_specs/utilities/server_setup.md) — FastAPI app, middleware, CORS, credentials
- [utilities/configuration.md](./_specs/utilities/configuration.md) — Per-domain YAML config, shared defaults, schema validation
- [utilities/flow_selection.md](./_specs/utilities/flow_selection.md) — Compositional dact grammar, builder process, domain examples
- [utilities/tool_smith.md](./_specs/utilities/tool_smith.md) — Tool manifest design: flow-to-tool mapping, schemas, error contracts
- [utilities/blocks.md](./_specs/utilities/blocks.md) — Building blocks for frontend rendering

## Folder Structure

Each assistant is a standalone server (FastAPI backend + SvelteKit frontend) with its own config and database. No shared base classes — assistants are fully self-contained.

```
personal_assistants/
├── _specs/                         # Design documents + the canonical vocabulary (architecture.md)
├── shared/                         # Cross-domain config only (shared_defaults.yaml, schemas/)
└── assistants/                     # Hugo, Dana, Kalli, Rowan — each follows the template below
```

**Assistant template**:

```
<Assistant>/
├── backend/                        # FastAPI app
│   ├── assistant.py                #   The turn owner
│   ├── components/                 #   The 9 core components + world.py
│   ├── modules/                    #   NLU, PEX, MEM + policies/
│   ├── prompts/                    #   Prompt assembly per module
│   └── routers/                    #   WebSocket, auth, conversation, health
├── schemas/                        # ontology.py, config.py, tools.yaml
├── database/                       # Content, sessions, memory records
├── utils/                          # Domain helpers + evaluation_suite/
└── frontend/                       # SvelteKit 2, Svelte 5, Tailwind
```

## Task 1: Synthetic Data Generation

If your task is extending the eval corpus, focus on these files in particular:

- `assistants/Hugo/.claude/skills/generating-evals/` — `SKILL.md` is the procedure; `data_aug_guide.md` beside it defines the ten diversity axes, voice rules, and case banks
- `assistants/Hugo/utils/evaluation_suite/datasets/` — the corpus itself: `train/dev/test.jsonl`
- `assistants/Hugo/schemas/ontology.py` — labels must use exact `FLOW_CATALOG` keys and dax codes
- [evaluation_suite.md](./_specs/utilities/evaluation_suite.md) — how the corpus is consumed
- `assistants/Hugo/utils/evaluation_suite/review_app/` — where flagged cases get human review

Each case is one multi-turn conversation; every user turn carries labels (intent, flow stack), expected tools, and an ambiguity tag. Agent turns are the ground-truth reference answers, so keep the assistant voice constant. Sample conversations independently, validate against the skill's rubric, and fix defects in place — never flag-and-defer.

## Task 2: Assistant Features (Backend)

If your task is a round of feature work, focus on these files in particular:

- [master_plan.md](./_specs/_review/master_plan.md) — the roadmap; then the current round's spec under `_specs/_review/rounds/`, which defines the contract you are implementing
- The module and component specs the round names (`_specs/modules/`, `_specs/components/`)
- `assistants/Hugo/backend/modules/` — `nlu.py`, `pex.py`, `mem.py`, and `policies/` (one policy per flow)
- `assistants/Hugo/backend/components/` — the 9 components plus `world.py`, which wires cross-module access
- `assistants/Hugo/backend/prompts/` and `assistants/Hugo/schemas/` — prompt assembly, ontology, config, tool manifest

Verify with the evaluation suite at `assistants/Hugo/utils/evaluation_suite/` ([README](./assistants/Hugo/utils/evaluation_suite/README.md)): Model Unit Tests for component behavior, Observability Traces for module-level calls, E2E Agent Evals for whole conversations.

## Task 3: End-to-End Interaction (Frontend + Infra)

If your task is the user experience from browser to backend and back, focus on these files in particular:

- `assistants/Hugo/frontend/src/` — SvelteKit 2, Svelte 5, Tailwind (use native Tailwind classes, not custom CSS)
- [blocks.md](./_specs/utilities/blocks.md) and architecture.md § User Interface — Building Blocks render into three panels: dialogue on the left, top and bottom display containers
- [task_artifact.md](./_specs/components/task_artifact.md) — the Task Artifact (parts and blocks) is what the frontend renders alongside the spoken reply
- `assistants/Hugo/backend/webserver.py` and `backend/routers/` — the backend boundary: WebSocket, auth, conversation, health
- [server_setup.md](./_specs/utilities/server_setup.md) and [configuration.md](./_specs/utilities/configuration.md) — the FastAPI app, middleware, credentials, and per-domain YAML config

Payloads between our own frontend and backend are an internal contract — no defensive shape-checking on either side; a broken shape should crash loudly so it gets fixed at the source.

## Wrapping Up

Before ending a session:

- Run the evaluation tier that covers your change and report results plainly — a failure or a skip is a failure, even if it looks pre-existing. Run pytest with the working directory set to `assistants/Hugo/` so imports resolve to the right backend.
- Keep specs and code in sync: if behavior changed, update the matching `_specs/` file in the same session, and the round record when the work belongs to a round.
- Vocabulary check the diff: no invented terms, no synonyms for canonical ones. Needing a new word is a signal to stop and find the existing rule that covers the scenario (architecture.md).
- Follow [style_guide.md](./_specs/style_guide.md) and match the surrounding code. Leave the tree clean: no stray temp files, and restore any database seed content the eval suite modified.
