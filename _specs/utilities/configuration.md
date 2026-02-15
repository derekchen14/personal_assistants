# Configuration

Engineering utility that provides per-domain configuration with shared defaults to guide the development of the agent. Every module and component that accepts `domain config` as input reads from the frozen object this utility produces.

**Loading lifecycle**: Startup-only, immutable. The config loader reads YAML data and ontology definitions, validates against a schema, and freezes the result into a read-only object. No config is modified after startup. If validation fails, the agent refuses to start.

## File Architecture

Three files per assistant, plus one shared defaults file.

### Config Data (YAML)

- `shared_defaults.yaml` in `shared/` — baseline inherited by every domain
- `<domain>.yaml` in `<domain>/` — domain-specific overrides and additions
- YAML holds system-level and domain-level runtime config: environment, models, persona, guardrails, session, memory, resilience, context_window, logging, display, thresholds, feature flags, template registry path, response_constraints, human_in_the_loop, slot types, key entities
- YAML does **not** hold flow definitions — those live in `ontology.py`

### Config Loader (config.py)

Python module at root of each assistant folder (per style guide). Responsibilities:

- Load `shared_defaults.yaml` and domain YAML
- Load flow definitions from `ontology.py`
- Apply section-level override (YAML sections only)
- Validate the merged result against the schema
- Freeze into a read-only object and expose to each assistant

Contains no config data itself — pure loading, merging, and validation logic.

### Constants & Flows (ontology.py)

Python module at root of each assistant folder (per style guide). Contains enums, constants, and flow definitions:

| Goes in `ontology.py` | Goes in YAML config (§1–§16) |
|---|---|
| Intent enum (Plan, Converse, Internal, Read, Prepare, Transform, Schedule) | §1 Models (provider, parameters, cost budgets) |
| Flow lifecycle states (Pending, Active, Completed, Invalid) | §2 Persona (tone, boundaries, name, response style) |
| **Dact catalog** (name, dax code, intent, edge flows, policy path) | §3 Guardrails (content filter, PII, topic control, injection) |
| Slot category strings (`'required'`, `'elective'`, `'optional'`) | §4 Session (timeouts, turn limits, persistence) |
| Ambiguity levels (General, Partial, Specific, Confirmation) | §5 Memory (scratchpad, summarization, user prefs, RAG) |
| Base slot value types (string, number, boolean, enum) | §6 Resilience (retries, backoff, fallback, recovery) |
| **Type hierarchy** (domain-specific column/entity type tree) | §7 Context window (budget allocation, priority order) |
| — | §7 Context window (budget allocation, priority order) |
| — | §8 Logging (level, trace export, sensitive data) |
| — | §9 Display (types, chart types, page size) |
| — | §10 Thresholds (stream, NLU confidence, ambiguity, promotion) |
| — | §11 Feature flags (boolean toggles) |
| — | §12 Template registry (path to templates) |
| — | §13 Response constraints (length bounds, language, citation) |
| — | §14 Human-in-the-loop (tool approval, escalation) |
| — | §15 Slot types (custom validators per domain) |
| — | §16 Key entities (domain-specific entity names) |

### Boundary: What Goes Where

If a value is a fixed structural category that code switches on → `ontology.py`. If tunable, domain-specific, or could differ between environments → YAML config.

Flow definitions are structural: NLU switches on dact names and dax codes, PEX resolves policy paths from dact names. These are the agent's vocabulary, not runtime tuning — hence ontology.

## Dact Selection Guide

See [Flow Selection](./flow_selection.md) for the compositional dact grammar, builder process, and worked examples. The flows defined there are registered in `ontology.py` and loaded by the config loader.

## Shared Defaults

`shared/shared_defaults.yaml` defines baseline values. Override model: section-level replacement. If a domain YAML defines a `display` section, the entire shared `display` section is discarded and the domain version is used. If a domain YAML omits a section, the shared default is used as-is. In other words, there is full section-level replacement only, rather than partial merge within a section. A domain that wants to change one value in `display` must redefine the entire `display` section.

### Coverage Table

| § | Section | Shared default |
|---|---|---|
| — | `tier` | `basic` — controls auth complexity, database backend, and which checklist phases apply (basic / pro / advanced) |
| 1 | `models` | `provider: anthropic`, `model_id: claude-sonnet-4-5-latest`, `temperature: 0.0`, `top_p: 1.0`, `max_output_tokens: 4096`, `stop_sequences: []`, overrides: `skill: { model_id: claude-opus-4-6 }`, `naturalize: { temperature: 0.5 }`, all cost budgets `null` (unlimited), `warn_threshold: 0.8` |
| 2 | `persona` | `tone: professional`, `expertise_boundaries: []`, `name: "Assistant"`, `response_style: balanced` |
| 3 | `guardrails` | `input_max_tokens: 4096`, content filter enabled at `severity: medium`, PII detection disabled, topic control empty (defers to `persona.expertise_boundaries`), no forbidden patterns, prompt injection enabled at `medium` |
| 4 | `session` | `idle_timeout_ms: 3600000` (60 min), `max_turns: 256`, `max_flow_depth: 8`, persistence backend `postgres`, `ttl_hours: 24` |
| 5 | `memory` | `max_snippets: 64`, `eviction: lru`, `trigger_turn_count: 20`, `trigger_token_count: 32000`, user prefs backend `postgres` with 256 max entries, business context `retrieval_top_k: 128`, `rerank_top_n: 10`, `similarity_threshold: 0.5` |
| 6 | `resilience` | tool retries `max_attempts: 3`, `exponential` backoff 1000/30000ms; LLM retries `max_attempts: 2`, `exponential` 500/10000ms, retriable `[rate_limit, timeout, server_error]`; no fallback model; `max_recovery_attempts: 2` |
| 7 | `context_window` | `max_input_tokens: 128000`, allocation `system_prompt: 0.10, conversation_history: 0.30, memory_context: 0.15, tool_results: 0.35, response_reserve: 0.10`, `history_max_turns: 50`, priority `[memory_context, conversation_history, tool_results]` |
| 8 | `logging` | level `null` (defer to environment: dev→DEBUG, prod→INFO), trace disabled, sensitive data all `false` in prod / all `true` in dev, signal export disabled |
| 9 | `display` | `types: [Default]`, `chart_types: [bar, line]`, `page_size: 512` |
| 10 | `thresholds` | `stream_threshold_tokens: 200`, `nlu_confidence_min: 0.64`, `nlu_vote_agreement_min: 0.67`, `ambiguity_escalation_turns: 3`, `scratchpad_promotion_frequency: 3` |
| 11 | `feature_flags` | `{}` (all flags default to false; auth/OAuth controlled by `tier`, not flags) |
| 12 | `template_registry` | `templates/base/` (templates may include `block_hint` and `skip_naturalize`; see [RES](../modules/res.md)) |
| 13 | `response_constraints` | `min_tokens: 10`, `max_tokens: 2048` for all intents, `language: en`, `supported_languages: [en]`, `confidence_auto_threshold: 0.6`, `citation_mode: footnote` |
| 14 | `human_in_the_loop` | mode `none`, `timeout_ms: 60000`, escalation disabled |
| 15 | `slot_types` | None (base types in ontology.py; custom always domain-specific) |
| 16 | `key_entities` | None (always domain-specific) |

## Domain Config Schema

### Annotated YAML Reference

#### shared_defaults.yaml

```yaml
# shared/shared_defaults.yaml
# Baseline config inherited by all domain agents.
# Each top-level section is fully replaced if the domain defines it.

environment: dev                    # dev | prod — controls logging, guardrails
tier: basic                         # basic | pro | advanced — controls auth and deployment complexity

models:
  default:
    provider: anthropic             # openai | anthropic | google | azure | bedrock
    model_id: claude-sonnet-4-5-latest
    temperature: 0.0                # 0.0–2.0
    top_p: 1.0                      # 0.0–1.0
    max_output_tokens: 4096         # max tokens in LLM response
    stop_sequences: []              # optional custom stop tokens
  overrides:                        # named overrides for specific call sites
    skill:                          # PEX skill invocation uses Opus
      model_id: claude-opus-4-6
    naturalize:                     # RES naturalization benefits from variety
      temperature: 0.5
  cost:
    token_budget_per_session: null   # max total tokens (in+out) per session; null = unlimited
    token_budget_per_turn: null      # max tokens per single turn
    daily_token_budget: null         # max tokens across all sessions per day
    warn_threshold: 0.8             # 0.0–1.0 fraction of budget to emit warning signal
  # Consumed by: Prompt Engineer (all calls, budget enforcement),
  #   Agent (session-level cost tracking),
  #   Evaluation (prompt version attribution, cost signals)

persona:
  tone: professional                # neutral baseline
  expertise_boundaries: []          # empty = no restrictions
  name: "Assistant"                 # agent display name
  response_style: balanced          # concise | balanced | detailed
  # Consumed by: Prompt Engineer (system prompt composition), RES (response formatting)

guardrails:
  input_max_tokens: 4096            # max user input length (reject above)
  content_filter:
    enabled: true
    categories: [violence, sexual, hate_speech, self_harm, dangerous]
    severity: medium                # none | low | medium | high
  pii_detection:
    enabled: false
    action: redact                  # redact | warn | block
    types: [ssn, credit_card, email, phone, address]
  topic_control:
    allowed_topics: []              # empty = no restriction (use expertise_boundaries)
    forbidden_topics: []            # explicit blocklist
  forbidden_patterns: []            # regex patterns to block in input or output
  prompt_injection_detection:
    enabled: true
    sensitivity: medium             # low | medium | high
  # Consumed by: NLU pre-hook (input validation),
  #   RES post-hook (output filtering),
  #   Prompt Engineer (system prompt injection for topic control)

session:
  idle_timeout_ms: 3600000          # 60 min before idle session expires
  max_turns: 256                    # hard cap on turns per session (0 = unlimited)
  max_flow_depth: 8                 # max flows on stack simultaneously
  persistence:
    backend: postgres                # memory | postgres | redis
    ttl_hours: 24                   # how long to keep persisted sessions
    timing: session_end             # session_end | per_turn — when to persist state
                                    # session_end keeps it simple; per_turn adds durability
  # Consumed by: Agent (turn counting, timeout enforcement),
  #   Context Coordinator (persistence backend),
  #   Server Setup (session cleanup)

memory:
  scratchpad:
    max_snippets: 64                # cap on session scratchpad entries
    eviction: lru                   # lru | fifo
  summarization:
    trigger_turn_count: 20          # summarize after N turns
    trigger_token_count: 32000      # or when context exceeds N tokens
  user_preferences:
    backend: postgres               # memory | postgres | redis
    max_entries: 256                # max stored preferences per user
  business_context:
    backend: vector                 # vector store type
    retrieval_top_k: 128            # candidates from vector search
    rerank_top_n: 10                # after reranking
    similarity_threshold: 0.5       # 0.0–1.0, minimum score to include
    embedding_model: null           # embedding model ID; null = provider default
  # Consumed by: Memory Manager (all tiers),
  #   NLU/PEX/RES (indirectly via memory contents),
  #   Prompt Engineer (context budget)

resilience:
  tool_retries:
    max_attempts: 3                 # total attempts (1 = no retry)
    backoff_strategy: exponential   # none | linear | exponential
    backoff_base_ms: 1000           # base delay between retries
    backoff_max_ms: 30000           # ceiling for exponential backoff
  llm_retries:
    max_attempts: 2
    backoff_strategy: exponential
    backoff_base_ms: 500
    retriable_errors: [rate_limit, timeout, server_error]
  fallback_model: null              # model_id to try if primary fails; null = none
  max_recovery_attempts: 2          # max times Agent tries re-route before escalate
                                    # (skip and escalate are the natural fallback chain
                                    # after re-routes are exhausted, not counted as attempts)
  # Consumed by: PEX execute() and recover() (tool retries),
  #   Prompt Engineer (LLM retries),
  #   Agent (recovery attempts)

context_window:
  max_input_tokens: 128000          # total input budget (model-dependent)
  allocation:                       # suggested fraction split — applies primarily to PEX policy calls
    system_prompt: 0.10             # fraction of budget (0.0–1.0)
    conversation_history: 0.30
    memory_context: 0.15            # scratchpad + retrieved business context
    tool_results: 0.35
    response_reserve: 0.10          # reserved for model output
  history_max_turns: 50             # max raw turns before summarization kicks in
  priority_order:                   # when budget is tight, which sections get cut first
    - memory_context
    - conversation_history
    - tool_results
  # Consumed by: Prompt Engineer (budget guidance during composition — advisory, not hard-enforced),
  #   Memory Manager (summarization trigger),
  #   Context Coordinator (history trimming)

logging:
  level: null                       # DEBUG | INFO | WARNING | ERROR; null = defer to environment
                                    # (dev → DEBUG, prod → INFO)
  trace_export:
    enabled: false
    endpoint: console               # OTLP endpoint URL, or "console"
    sampling_rate: 1.0              # 0.0–1.0 (1.0 = trace everything)
  sensitive_data:                   # environment modulates defaults: dev = all true, prod = all false
    log_prompts: false              # whether to log full prompt text
    log_responses: false            # whether to log full LLM responses
    log_tool_args: false            # whether to log tool call arguments
  signal_export:
    enabled: false                  # export evaluation signal envelopes
    endpoint: ""                    # where to send signals
  # Consumed by: All modules/components (logging),
  #   Evaluation (signal export),
  #   Prompt Engineer (prompt/response logging)

display:
  types: [Default]                  # minimal; domains extend
  chart_types: [bar, line]          # common chart types
  page_size: 512                   # rows before pagination
                                    # (ref: display_frame.md § Pagination)

thresholds:
  stream_threshold_tokens: 200      # above this, RES streams response
                                    # (ref: res.md § Step 4)
  nlu_confidence_min: 0.64          # below this, NLU triggers round-2 vote
  nlu_vote_agreement_min: 0.67      # minimum agreement ratio for majority vote
  ambiguity_escalation_turns: 3     # max turns in ambiguity loop before escalating
  scratchpad_promotion_frequency: 3  # recurrence count to trigger promotion
  extended_thinking_budget: 2048    # token budget for extended thinking (NLU round 3)

feature_flags:                      # all flags default false
  proactive_issue_detection: false  # when true, agent proactively checks for issues after N turns (threshold above)

template_registry: templates/base/  # path to base intent templates
                                    # (ref: res.md § Template Registry)

response_constraints:
  length_bounds:
    default:
      min_tokens: 10
      max_tokens: 2048
    per_intent: {}                  # optional overrides, e.g. Converse: { min_tokens: 1, max_tokens: 512 }
  language: en                      # ISO 639-1 code
  supported_languages: [en]         # for multilingual agents
  confidence_auto_threshold: 0.6    # below this, ask clarification instead of auto-responding
  citation_mode: footnote           # none | inline | footnote
  # Consumed by: RES generate() (length enforcement),
  #   Self-check gate (length bounds check),
  #   NLU (confidence threshold),
  #   Prompt Engineer (language instruction)

human_in_the_loop:
  tool_approval:
    mode: none                      # none | non_idempotent | all | explicit_list
    explicit_list: []               # tool_ids requiring approval (when mode=explicit_list)
    timeout_ms: 60000               # how long to wait for approval before failing
  escalation:
    enabled: false
    triggers: [max_recovery_exceeded, low_confidence, user_request]
    channel: webhook                # webhook | queue | email
    endpoint: ""                    # where to send escalation
  # Consumed by: PEX execute() (tool gating),
  #   Agent (escalation routing),
  #   Server Setup (webhook/queue integration)

# No shared defaults for: §15 slot_types, §16 key_entities
# These are inherently domain-specific.
#
# Note: CORS and health endpoint config is server-level, not domain YAML.
# (ref: server_setup.md § CORS, § Health Endpoint)
#
# Note: Rendering hints (viewport adaptation, color scheme) are owned by
# Building Blocks, not by domain config. Domains do not override rendering
# behavior. (ref: blocks.md § Responsive Hints)
```

#### cooking.yaml

```yaml
# cooking/cooking.yaml
# Domain config for the cooking assistant.
# Sections defined here fully replace the shared default for that section.

environment: prod                   # overrides shared 'dev'
tier: pro                           # production agent with JWT auth

models:                             # fully replaces shared models
  default:
    provider: anthropic
    model_id: claude-sonnet-4-5-latest
    temperature: 0.0
    top_p: 1.0
    max_output_tokens: 4096
    stop_sequences: []
  overrides:
    skill:
      model_id: claude-opus-4-6
    naturalize:
      temperature: 0.5
  cost:
    token_budget_per_session: null
    token_budget_per_turn: null
    daily_token_budget: null
    warn_threshold: 0.8

persona:                            # fully replaces shared persona
  tone: warm                        # encouraging, instructional
  expertise_boundaries: [cooking techniques, nutrition, meal planning, food safety]
  name: "Chef Assistant"
  response_style: balanced
  # Consumed by Prompt Engineer (prompt_engineer.md § Prompt Composition)

guardrails:                         # fully replaces shared guardrails
  input_max_tokens: 4096
  content_filter:
    enabled: true
    categories: [violence, sexual, hate_speech, self_harm, dangerous]
    severity: medium
  pii_detection:
    enabled: false
    action: redact
    types: [ssn, credit_card, email, phone, address]
  topic_control:
    allowed_topics: []              # defers to persona.expertise_boundaries
    forbidden_topics: []
  forbidden_patterns: []
  prompt_injection_detection:
    enabled: true
    sensitivity: medium

display:                            # fully replaces shared display
  types: [Default, Dynamic]         # Default for recipes, Dynamic for timers
  chart_types: [bar]                # nutrition breakdowns
  page_size: 512                    # recipes are shorter than data tables

thresholds:                         # fully replaces shared thresholds
  stream_threshold_tokens: 200      # same as shared default here
  nlu_confidence_min: 0.64
  nlu_vote_agreement_min: 0.67
  ambiguity_escalation_turns: 3
  scratchpad_promotion_frequency: 3

slot_types:
  # Custom slot type validators (dialogue_state.md § Slot Value Types)
  ingredient:
    validator: validators.ingredient_validator
  cuisine_type:
    validator: validators.cuisine_type_validator

key_entities: [recipe, ingredient, step]
  # Domain-specific entities for Ambiguity Handler
  # (ambiguity_handler.md § Levels)

feature_flags:                      # fully replaces shared feature_flags
  meal_planning: true
  nutrition_tracking: false         # beta feature

template_registry: templates/cooking/
  # Path to domain template files; RES loads from here
  # (res.md § Template Registry)
```

### Section Details

1. **`models`**: LLM provider and model selection. The `default` block sets the primary model (provider, model_id, temperature, top_p, max_output_tokens, stop_sequences). The `overrides` map allows named call sites (nlu_vote, self_check, naturalize) to use different models or parameters without code changes. The `cost` sub-section co-locates token budgets (per-session, per-turn, daily) with model config because token budgets are directly tied to model usage. Model selection is the single highest-impact tunable; every framework makes this configurable.
2. **`persona`**: Tone, expertise boundaries, display name, and response style consumed by Prompt Engineer for system prompt composition. Shared defaults provide a neutral baseline; domains override to set personality. The `response_style` (concise/balanced/detailed) guides Prompt Engineer verbosity. Other personality details (follow-up behavior, emoji usage) belong in prompt templates, not config.
3. **`guardrails`**: Input/output safety checks, content filtering, PII detection, topic enforcement, forbidden regex patterns, and prompt injection detection. Severity is a single config value; `environment` modulates enforcement behavior (dev: warnings not blocks, prod: strict enforcement). Varies dramatically by domain (healthcare vs. entertainment). Amazon Bedrock, NVIDIA NeMo, and Azure all make this a first-class config surface.
4. **`session`**: Session lifecycle management — idle timeout, turn limits, flow stack depth cap, and persistence backend/TTL. Without session limits, a runaway conversation can consume unbounded resources. The `max_flow_depth` prevents infinite flow-stacking bugs. Every production chatbot platform (Dialogflow, Lex, Rasa) enforces session timeouts.
5. **`memory`**: Limits and backends for the three-tier memory system. Scratchpad has capacity and eviction policy. Summarization triggers replace the previous "TBD" with concrete turn-count and token-count thresholds. User preferences has backend and capacity. Business context configures RAG retrieval (top-k, rerank-top-n, similarity threshold, embedding model). These values are tuned per domain everywhere.
6. **`resilience`**: Retry and recovery behavior for tool calls and LLM invocations. Tool retries (max attempts, backoff strategy/base/max), LLM retries (max attempts, backoff, retriable error types), optional fallback model, and max recovery attempts for the Agent re-route chain. Retry behavior is deployment-dependent (aggressive for batch, conservative for real-time). The `max_recovery_attempts` controls re-route attempts only; skip and escalate are the natural fallback chain after re-routes are exhausted.
7. **`context_window`**: Prompt budget allocation — how the finite context window is divided among system prompt, conversation history, memory context, tool results, and response reserve. Allocation fractions are advisory (primarily relevant for PEX policy calls where tool results dominate), not hard-enforced. Includes `history_max_turns` and `priority_order` for graceful degradation when budget is tight. Context window management is the #1 operational concern for production LLM apps.
8. **`logging`**: Observability configuration — log level (overrides environment default), OpenTelemetry trace export (endpoint, sampling rate), sensitive data toggles (prompts, responses, tool args), and evaluation signal export. Sensitive data toggles are a compliance requirement. You can't debug production issues if you can't turn up logging without redeploying code.
9. **`display`**: Display type list, chart type list, page size, and accepted file formats (with MIME types). Display types govern how RES maps frames to blocks. File formats define what the domain accepts for upload (e.g., `[csv, xlsx, tsv]` for data analysis, `[md, docx]` for blogging). Shared defaults provide minimal baseline.
10. **`thresholds`**: Numeric thresholds controlling runtime behavior. `stream_threshold_tokens` for RES streaming. `nlu_confidence_min` and `nlu_vote_agreement_min` for NLU classification confidence. `ambiguity_escalation_turns` caps the ambiguity loop. `scratchpad_promotion_frequency` controls how many times a snippet must recur to trigger promotion to long-term memory.
11. **`feature_flags`**: Boolean toggles per domain. Shared defaults set all false. Checked at runtime but config itself is still immutable after startup.
12. **`template_registry`**: Path to RES template file directory. Config stores path only; RES owns the files. Shared defaults point to base templates. Domain override templates can include `block_hint` (suggested block type) and `skip_naturalize` (skip LLM naturalization). Reference: [RES — Template Registry](../modules/res.md#template-registry), [Building Blocks — Block-Template Coordination](../utilities/blocks.md#block-template-coordination)
13. **`response_constraints`**: Output boundaries — length bounds (min/max tokens, with per-intent overrides), language (ISO 639-1 code), supported languages list, confidence auto-threshold (below which the agent asks clarification instead of auto-responding), and citation mode. The self-check gate already checks length bounds — this section gives it concrete values to read. Language config is standard for any internationalized deployment.
14. **`human_in_the_loop`**: Approval and escalation configuration. Tool approval mode (none/non_idempotent/all/explicit_list) gates which actions require human approval before execution, with a timeout. Escalation routing (triggers, channel, endpoint) determines when and how to hand off to a human agent. As agents perform consequential actions, the ability to gate specific tools without code changes is essential.
15. **`slot_types`**: Custom slot type validators per domain. Base types (string, number, boolean, enum) in ontology.py. Always domain-specific.
16. **`key_entities`**: Entity names grounding the Ambiguity Handler's Partial level. Always domain-specific.

### Cross-Domain Comparison

Brief diffs showing how the 3 queued agents differ from cooking:

| Section | Cooking | Blogger | Headhunter | Scheduler |
|---|---|---|---|---|
| `persona.tone` | warm | conversational | professional | efficient |
| `persona.name` | Chef Assistant | Writing Coach | Talent Scout | Schedule Pro |
| `persona.expertise_boundaries` | cooking, nutrition, meal planning, food safety | creative writing, SEO, content strategy | recruiting, job market, candidate evaluation | calendar management, time optimization |
| `persona.response_style` | balanced | detailed | concise | concise |
| `guardrails.pii_detection.enabled` | false | false | true | false |
| `session.max_turns` | 256 | 256 | 256 | 256 |
| `display.types` | Default, Dynamic | Default, Derived | Default, Decision | Default, Dynamic |
| `display.chart_types` | bar | bar, line | bar | bar, line |
| `display.page_size` | 512 | 512 | 1024 | 1024 |
| `response_constraints.language` | en | en | en | en |
| `response_constraints.citation_mode` | footnote | inline | footnote | footnote |
| `key_entities` | recipe, ingredient, step | post, section, draft | listing, application, resume | event, calendar, time_block |
| `human_in_the_loop.tool_approval.mode` | none | none | non_idempotent | none |

## Environment Awareness

The `environment` field (dev/prod) controls behavioral differences:

| Behavior | `dev` | `prod` |
|---|---|---|
| Logging level (default) | `DEBUG` | `INFO` |
| Logging sensitive data (default) | All `true` | All `false` |
| Guardrails enforcement | Warnings, not blocks | Strict enforcement |
| Feature flags | May enable untested features | Only stable features |
| Validation strictness | Warnings on schema issues | Hard failure on schema issues |
| Tool timeout | Longer (development convenience) | Configured per-tool `timeout_ms` |

Single config file per domain serves both environments — the environment flag controls behavior, not separate config files. The `logging.level` and `logging.sensitive_data` fields can override these defaults explicitly; `guardrails` severity is set directly in config while `environment` modulates enforcement behavior.

## Tier Awareness

The `tier` field (basic/pro/advanced) controls auth complexity, database backend, and which checklist phases apply:

| Behavior | `basic` | `pro` | `advanced` |
|---|---|---|---|
| Auth | Username prompt only (no login) | JWT + bcrypt passwords | OAuth 2.0 providers |
| Database | SQLite | Postgres | Postgres |
| Persistence backend | memory | postgres | postgres |
| Session store | In-memory | Postgres | Postgres |
| Deployment | Local dev (`init_backend.sh` + `init_frontend.sh`) | Dockerfile + docker-compose | Same + monitoring |
| CORS | Permissive (all origins) | Explicit allowlist | Same |
| Rate limiting | None | Auth endpoints (5/min) | Same |
| Payment | None | None | Stripe (or similar) |
| Checklist phases | 4a, 9a | 4a + 4b, 9a + 9b | 4a + 4b + 4c, 9a + 9b + 9c |

Tiers are incremental — `pro` includes everything in `basic`, and `advanced` includes everything in `pro`. The `tier` value determines which checklist phases are relevant during implementation and which infrastructure components to set up.

## Startup Loading & Validation

### Load Sequence

1. Read shared defaults — parse `shared/shared_defaults.yaml`
2. Read domain config — parse `<domain>/<domain>.yaml`
3. Merge — section-level override (YAML sections only)
4. Load ontology — import flow definitions from `ontology.py`, attach as `config.flows`
5. Validate — run merged config through schema validation
6. Freeze — convert to read-only object, expose to all consumers

If any step fails, the agent does not start.

### Schema Validation Checks

One row per numbered section. Each row lists all checks for that section.

| § | Section | Checks |
|---|---|---|
| 1 | `models` | Provider in `[openai, anthropic, google, azure, bedrock]`; temperature 0.0–2.0; top_p 0.0–1.0; override keys are recognized call sites; cost budgets non-negative (when non-null) |
| 2 | `persona` | Required fields present; `response_style` in `[concise, balanced, detailed]` |
| 3 | `guardrails` | Content filter categories recognized; PII types recognized; forbidden patterns compile as valid regex; `severity` in `[none, low, medium, high]`; injection `sensitivity` in `[low, medium, high]` |
| 4 | `session` | Persistence backend in `[memory, postgres, redis]`; `idle_timeout_ms` > 0; `max_flow_depth` > 0 |
| 5 | `memory` | Backends recognized; `similarity_threshold` 0.0–1.0; `retrieval_top_k` >= `rerank_top_n`; `eviction` in `[lru, fifo]` |
| 6 | `resilience` | Backoff strategy in `[none, linear, exponential]`; `max_attempts` >= 1; `retriable_errors` entries recognized |
| 7 | `context_window` | Allocation fractions sum to 1.0; priority order entries in `[system_prompt, conversation_history, memory_context, tool_results]`; `max_input_tokens` > 0 |
| 8 | `logging` | Level in `[DEBUG, INFO, WARNING, ERROR]` (when non-null); `sampling_rate` 0.0–1.0 |
| 9 | `display` | Display types recognized; chart types in recognized set |
| 10 | `thresholds` | `nlu_confidence_min` 0.0–1.0; `nlu_vote_agreement_min` 0.0–1.0; all numeric values positive |
| 11 | `feature_flags` | All values are boolean |
| 12 | `template_registry` | Directory path exists |
| 13 | `response_constraints` | Length bounds `min_tokens` < `max_tokens`; language codes valid ISO 639-1; `confidence_auto_threshold` 0.0–1.0; `citation_mode` in `[none, inline, footnote]` |
| 14 | `human_in_the_loop` | Mode in `[none, non_idempotent, all, explicit_list]`; `explicit_list` entries are non-empty strings; `timeout_ms` > 0 |
| 15 | `slot_types` | Validator functions exist and are importable |
| 16 | `key_entities` | Entity names are non-empty strings |

Additional cross-cutting checks (not section-specific): `tier` in `[basic, pro, advanced]`; `environment` is `dev` or `prod`; required sections present; flow integrity (no conflicting dax codes, intent references valid); edge flow names match defined flows; policy paths resolve to importable modules. Flow-related checks validate ontology.py data, not YAML data. All checks run during step 5 regardless of data source.

### Frozen Config Object

After validation, config is frozen. All consumers receive a reference to the same read-only object. Attempting to modify raises an error. Aligns with style guide: "Global state is acceptable if read-only."

## Config Interface

### Consumer Access Patterns

| Consumer | What it reads | Config path |
|---|---|---|
| NLU `think()` | Flow definitions, dax codes, edge flows, confidence threshold | `config.flows`, `config.persona`, `config.thresholds.nlu_confidence_min` |
| NLU `contemplate()` | Same, narrowed by ambiguity metadata, vote agreement threshold | `config.flows`, `config.thresholds.nlu_vote_agreement_min` |
| NLU pre-hook | Input validation, guardrails | `config.guardrails` |
| PEX `execute()` | Policy mapping, tool approval, retries | `config.flows[dact].policy`, `config.resilience.tool_retries`, `config.human_in_the_loop.tool_approval` |
| PEX pre-hook | Flow validation | `config.flows` |
| PEX `recover()` | Retry config | `config.resilience` |
| RES `generate()` | Streaming threshold, template registry, length bounds, language | `config.thresholds`, `config.template_registry`, `config.response_constraints` |
| RES `display()` | Display types, chart types, page size | `config.display` |
| RES post-hook | Output filtering, guardrails | `config.guardrails` |
| Display Frame | Page size for pagination | `config.display.page_size` |
| Prompt Engineer | Model config, persona, context window budget, language, LLM retries | `config.models`, `config.persona`, `config.context_window`, `config.response_constraints.language`, `config.resilience.llm_retries` |
| Self-check gate | Length bounds, model config for self-check | `config.response_constraints.length_bounds`, `config.models.overrides.self_check` |
| Agent | Session limits, cost tracking, recovery attempts, escalation | `config.session`, `config.models.cost`, `config.resilience.max_recovery_attempts`, `config.human_in_the_loop.escalation` |
| Memory Manager | Scratchpad limits, summarization triggers, user prefs backend, RAG params, promotion frequency | `config.memory`, `config.thresholds.scratchpad_promotion_frequency` |
| Context Coordinator | Persistence backend, history trimming | `config.session.persistence`, `config.context_window` |
| Ambiguity Handler | Key entity definitions, escalation turn limit | `config.key_entities`, `config.thresholds.ambiguity_escalation_turns` |
| Dialogue State | Custom slot type validators | `config.slot_types` |
| Evaluation | Signal export, model attribution | `config.logging.signal_export`, `config.models` |
| Server Setup | Tier, session cleanup, escalation integration | `config.tier`, `config.session`, `config.human_in_the_loop.escalation` |
| All modules | Log level, trace config | `config.logging` |

Note: `config.flows` originates from ontology.py but is accessed through the same frozen config object as YAML-sourced data. Consumers don't need to know the underlying source.

### Common Patterns

- Dot-path access: `config.persona.tone`
- Section iteration: `for category, entries in config.guardrails.content_filter.items()`
- Flag checks: `config.feature_flags.get('meal_planning', False)`
- Environment branching: `if config.environment == 'prod'`
- Tier branching: `if config.tier in ('pro', 'advanced')`
