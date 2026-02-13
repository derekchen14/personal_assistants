# Tool Smith

Design-time utility for building the tool manifest. Sits between [Flow Selection](./flow_selection.md) (which produces flows + slots) and [PEX](../modules/pex.md) (which executes tools at runtime). Output: a complete tool manifest + JSON Schema files for each tool.

**Relationship chain**: Flow Selection → **Tool Smith** → [PEX](../modules/pex.md)

Flow Selection defines *what* the agent can do (48 flows). Tool Smith defines *how* — the tools that flows invoke. Tools are modular units: cheap to add, easy to swap, safe to remove. A domain has at least as many tools as flows — each flow needs at least one tool, and some flows need several.

Some tools are shared across flows (e.g., `recipe_search` serves `browse`, `find`, and `match`). Others are 1:1 with a flow (e.g., `timer_set` exists only for the `timer` flow). Both patterns are normal. The design goal is modularity, not consolidation.

## Flow-to-Tool Mapping

Each flow declares its tool bindings in the policy config. Flow slots become tool parameters — the policy in PEX assembles slot values into tool calls.

### Shared Tool Example

| Flow | Slots | Tool | Parameters passed |
|---|---|---|---|
| browse | category (opt), cuisine (opt) | recipe_search | query=category, filter=cuisine |
| find | recipe (req) | recipe_search | query=recipe, exact=true |
| match | ingredient (req), method (opt) | recipe_search | query=ingredient, filter=method |

Three flows share one tool. The policy for each flow assembles different slot values into the tool's input schema.

### Dedicated Tool Example

| Flow | Slots | Tool | Parameters passed |
|---|---|---|---|
| substitute | ingredient (req) | substitution_find | query=ingredient |
| nutrition | recipe (req) | nutrition_lookup | recipe_id=recipe |
| timer | duration (req), label (opt) | timer_set | duration_sec=duration, label=label |

Each flow has its own tool. This is fine — the tool wraps a distinct service or operation that no other flow needs.

### Policy Tool Config

Each policy declares its tool bindings in a config block. This config feeds into the [skill template](#skill-templates) as strongly-worded guidance for slot-to-parameter mapping. Swapping a tool means changing one config entry — the policy logic stays the same.

```yaml
# Policy config for the "browse" flow
flow: browse
intent: Read
skill_template: skills/browse.md
tools:
  - tool_id: recipe_search
    slot_mapping:
      query: category       # flow slot → tool parameter
      filter: cuisine
    mapping_guidance: >
      Use these mappings as your default. Try them first.
      If a tool call fails, you may adjust parameters based on error context.
```

The `slot_mapping` defines the default mapping from flow slots to tool parameters. At runtime, this config is injected into the skill template (see [Skill Templates](#skill-templates) § Slot Mapping Is Guidance, Not Deterministic). The LLM receives it as guidance — not as a deterministic pre-step — so it can adapt when initial attempts fail.

Adding a new tool to a flow means adding an entry to the config and referencing it in the skill template. Removing a tool means deleting both. The policy logic (skill assembly, error handling, result routing) stays the same.

## Tool Discovery Process

Step-by-step process to derive tools from flows. Run this after Flow Selection produces the 48-flow catalog with slots.

### Step 1: Group Flows by External System

Which API, database, or service does each flow talk to? Flows hitting the same system likely share a tool.

- All recipe-related flows → recipe database
- All nutrition flows → USDA FoodData Central API
- All timer flows → IoT timer service

### Step 2: Identify CRUD Patterns

For each system, what operations exist? Each distinct operation = one tool.

- Recipe database: search, get, create, update → 4 tools
- Nutrition API: lookup → 1 tool
- Timer service: set, cancel → 2 tools

### Step 3: Map Slots to Parameters

For each tool, list all the slots (from all flows that use it) as potential input parameters. Union of slots = tool's input schema.

- `recipe_search` is used by `browse`, `find`, `match` → union of their slots: query (req), filter (opt), exact (opt)
- Required in tool schema = required in *every* flow that uses the tool
- Optional in tool schema = required in *some* flows but not all

### Step 4: Separate Read from Write

Read tools are idempotent; write tools are not. This drives retry policy in [PEX § Idempotency Annotations](../modules/pex.md).

- `recipe_search` (read) → idempotent, auto-retry safe
- `recipe_create` (write) → not idempotent, confirmation before retry

### Step 5: Verify Coverage

Every flow must have at least one tool binding. Walk through the 48 flows and confirm each one maps to a tool. It's fine for a flow to have a dedicated tool that nothing else uses — tools are cheap to add and remove. If a tool serves 10+ flows, consider whether it's doing too much (hard to test, hard to evolve).

## Tool Categories

Three categories based on what the tool talks to.

| Category | What it does | Idempotent | Example |
|---|---|---|---|
| **Code execution** | Runs code the agent writes (SQL, Python, shell) | depends | sql_execute, python_execute, shell_run |
| **External API** | Calls a third-party platform (real integrations) | depends | google_ads_api, github_api, amplitude_get |
| **Internal service** | Calls domain-internal logic (search, validate, compute) | usually yes | recipe_search, chart_render, lint_check |

Code execution tools are *canonical* — they appear across many domains with domain-specific permissions and schemas. External API tools name the real platform they integrate with. Internal service tools wrap domain-specific logic.

### Operation Types

Within each category, tools follow CRUD-style operation types:

| Operation | Idempotent | Typical timeout |
|---|---|---|
| search / get / read | yes | 5–15s |
| create / post | no | 10s |
| update / patch | no | 10s |
| delete | no | 5s |
| analyze / compute | yes | 15–30s |
| execute / run | no | varies |
| validate / check | yes | 5s |

## Tool Implementation

Tools are class methods on Python service classes. One service class per external system or internal service — the class holds connection state, credentials, and shared config so individual methods stay focused on a single operation.

### Service Class Pattern

```python
class RecipeService:
    """Wraps the recipe database. One instance per domain startup."""

    def __init__(self, db_conn, config):
        self.db = db_conn
        self.config = config

    def search(self, query: str, filter: str | None = None,
               exact: bool = False) -> dict:
        """tool_id: recipe_search"""
        rows = self.db.execute(...)
        return {"status": "success", "result": rows,
                "metadata": {"total_count": len(rows), "source": "recipe_db"}}

    def get(self, recipe_id: str) -> dict:
        """tool_id: recipe_get"""
        row = self.db.get(recipe_id)
        if not row:
            return {"status": "error", "error_category": "not_found",
                    "message": f"Recipe '{recipe_id}' not found",
                    "retryable": False}
        return {"status": "success", "result": row}

    def create(self, name: str, ingredients: list[str],
               instructions: str) -> dict:
        """tool_id: recipe_create"""
        ...
```

### Rules

- **One class per system**: `RecipeService`, `GitHubService`, `SQLService`, `NutritionService`, etc.
- **Methods follow naming**: `service.verb(params)` — mirrors the `entity_verb` tool naming convention. `recipe_service.search(query, filter)` corresponds to tool_id `recipe_search`.
- **All methods return envelopes**: Success envelope (`status`, `result`, `metadata`) or error envelope (see [Error Contract](#error-contract)). No raw returns.
- **Instantiated at startup**: Service classes are created once during domain initialization. Policies receive them via dependency injection — they never construct services themselves.
- **Connection state lives on the class**: Database connections, API clients, auth tokens — all held as instance attributes. Methods are stateless beyond `self`.

## Skill Templates

Each flow has a corresponding skill template — a Markdown file that gets assembled into the LLM prompt when the policy invokes the skill. Templates live in `<domain>/skills/<dact>.md`, one file per flow.

When assembled into the final prompt, skill templates follow the [standard 8-slot prompt format](../style_guide.md#standard-prompt-format) from the Style Guide. The skill template provides slots 2-6 (persona/task, detailed instructions, keywords/options, output shape, exemplars). The Prompt Engineer injects slot 1 (grounding data) and slot 8 (final request) at assembly time, and appends slot 7 (closing reminder) after the template's exemplars.

### Template Contents

1. **Flow description** — What this flow accomplishes, one paragraph
2. **Slot-to-parameter mapping guidance** — Strongly-worded default mapping from flow slots to tool parameters. The LLM tries this mapping first but can adjust if a tool call fails
3. **Expected tool call sequence** — Ordered list of tools the skill should call, with conditions for branching
4. **Output format instructions** — What shape the result should take for the Display Frame

### Slot Mapping Is Guidance, Not Deterministic

The skill template includes the slot-to-parameter mapping as strongly-worded guidance, not as a deterministic pre-step. The LLM should:

1. **Try the predicted mapping first** — use the slot values exactly as the template specifies
2. **Adjust on failure** — if a tool call returns an error, the LLM can remap parameters based on the error context (e.g., a `validation_error` might indicate the wrong parameter format)
3. **Stay within the tool's schema** — any adjustment must still conform to the tool's JSON Schema

This approach gives the LLM flexibility to recover from edge cases without requiring the policy to pre-compute every possible mapping.

### Worked Example: `browse` Skill Template

```markdown
# browse

Help the user explore recipes by category or cuisine. This is a discovery flow —
the user is browsing, not searching for something specific.

## Slot-to-Parameter Mapping

Use these mappings as your default. Try them first. If a tool call fails, you may
adjust parameters based on error context.

| Slot | Tool | Parameter | Notes |
|---|---|---|---|
| category | recipe_search | query | Pass the category as the search query |
| cuisine | recipe_search | filter | Pass cuisine as the filter value |

If both slots are empty, call recipe_search with no query to return featured recipes.

## Tool Sequence

1. Call `recipe_search` with the mapped parameters
2. If results are empty and a filter was applied, retry without the filter
3. Return the result array for display

## Output Format

Return results as an array of recipe summary objects. The Display Frame will
render these as a card list. Include recipe_id, name, cuisine, and prep_time_min
for each result.
```

### Assembly

The policy class method assembles the skill prompt by:

1. Reading the skill template from `<domain>/skills/<dact>.md`
2. Injecting the current slot values from the flow stack
3. Appending tool schemas for the tools referenced in the template
4. Appending component tool schemas (context_coordinator, memory_manager, flow_stack) — provided by PEX, not from the manifest

The assembled prompt is passed to the LLM for skill invocation.

## Schema Design

### Input Schema

JSON Schema derived from the flow slots that use this tool. For shared tools, take the union of all flows' slots. For dedicated tools, the schema mirrors the flow's slots directly. Design rules:

- Flat structure (no nesting beyond one level)
- Required fields = slots marked `(req)` in *every* flow that uses this tool
- Optional fields = slots that only some flows pass, or optional within the flow
- Use `enum` for `(choice)` slots
- snake_case field names
- Include `description` on every field (helps NLU slot-filling)

### Output Schema

JSON Schema matching what the [Display Frame](../components/display_frame.md) needs. Design rules:

- Always include a top-level `status` field (success/error)
- Data goes in a `result` field (object or array)
- Include `metadata` for pagination, timestamps, source attribution
- Output shape should match the block type (table data → array of rows, card data → single object)

### Worked Schema Example

**Tool**: `recipe_search`

**Input** (`schemas/recipe_search_input.json`):

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "Search term: recipe name, category, or ingredient"
    },
    "filter": {
      "type": "string",
      "description": "Narrow results by cuisine type or cooking method"
    },
    "exact": {
      "type": "boolean",
      "default": false,
      "description": "If true, match query exactly instead of fuzzy search"
    }
  },
  "required": ["query"],
  "additionalProperties": false
}
```

**Output** (`schemas/recipe_search_output.json`):

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "status": {
      "type": "string",
      "enum": ["success", "error"]
    },
    "result": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "recipe_id": { "type": "string" },
          "name": { "type": "string" },
          "cuisine": { "type": "string" },
          "prep_time_min": { "type": "integer" },
          "ingredients": {
            "type": "array",
            "items": { "type": "string" }
          }
        }
      }
    },
    "metadata": {
      "type": "object",
      "properties": {
        "total_count": { "type": "integer" },
        "page": { "type": "integer" },
        "source": { "type": "string" }
      }
    }
  },
  "required": ["status", "result"]
}
```

## Schema Organization

### Directory Layout

```
shared/
  schemas/
    sql_execute.json          # canonical tool schemas
    python_execute.json
    shell_run.json
    http_request.json
    components/
      context_coordinator.json  # component tool schemas (NOT in manifest)
      memory_manager.json
      flow_stack.json

<domain>/
  schemas/
    recipe_search.json        # domain-specific tool schemas
    recipe_get.json
    nutrition_lookup.json
    ...
```

### Rules

- **`shared/schemas/`** — Canonical tool schemas that appear across many domains (sql_execute, python_execute, shell_run, http_request). These define the baseline shape; domains register them with domain-specific permissions and config.
- **`<domain>/schemas/`** — Domain-specific tool schemas. One file per tool, named `<tool_id>.json`.
- **Domain overrides shared** — A domain can override a shared schema by placing a file with the same tool_id in `<domain>/schemas/`. The domain version wins. This lets a domain tighten permissions, add fields, or restrict enums on a canonical tool.
- **`shared/schemas/components/`** — Component tool schemas for context_coordinator, memory_manager, and flow_stack. These are NOT in the tool manifest. PEX provides them directly to skills alongside flow-specific tools (see [Skill Templates](#skill-templates) § Assembly).

## Naming Conventions

- **Pattern**: `entity_verb` — `recipe_search`, `calendar_create`, `campaign_update`
- **Case**: snake_case, max 30 characters
- **Verb** from a small set: search, get, create, update, delete, analyze, check, set, run
- **Entity** = the key entity from Step B of [Flow Selection](./flow_selection.md)
- When a tool serves multiple entities, use the primary entity

## Tool Manifest Entry

Each tool in the manifest declares these properties. PEX loads the manifest at startup and uses it to validate, gate, and execute tool calls.

### Core Fields

| Field | Type | Description |
|---|---|---|
| `tool_id` | string | Unique identifier, `entity_verb` pattern |
| `name` | string | Human-readable display name |
| `description` | string | What the tool does — for logging/debugging and skill prompt context |
| `input_schema` | string | Path to input JSON Schema file |
| `output_schema` | string | Path to output JSON Schema file |
| `idempotent` | bool | Safe to auto-retry without side effects (drives PEX retry policy) |
| `timeout_ms` | int | Max execution time in milliseconds |

### Capability Tags

Three boolean tags that classify a tool's security profile. Used by [PEX § Pre-Hook](../modules/pex.md) to enforce the Lethal Trifecta threat model — when all three tags are true on a single tool, that tool requires mandatory human approval regardless of other settings.

| Field | Type | Default | Description |
|---|---|---|---|
| `accesses_private_data` | bool | false | Tool reads or writes user/tenant PII, credentials, or sensitive business data |
| `receives_untrusted_input` | bool | false | Tool processes input originating from outside the system (user uploads, external APIs, scraped content) |
| `communicates_externally` | bool | false | Tool sends data to external systems (email, Slack, webhooks, third-party APIs) |

Any two tags together are safe with standard controls. All three together create an exfiltration path (untrusted input → access private data → send externally). PEX pre-hook check #7 enforces this.

### Operational Fields

Per-tool overrides for global [Configuration](./configuration.md) settings. These let a tool tighten or relax behavior set at the system level.

| Field | Type | Default | Description |
|---|---|---|---|
| `max_retries` | int \| null | null (use §6 `resilience` default) | Per-tool retry cap; overrides `resilience.tool_retries.max_attempts` |
| `requires_approval` | bool | false | Require human approval before execution; overrides §14 `human_in_the_loop.tool_approval` |
| `rate_limit_rpm` | int \| null | null (no limit) | Requests per minute — for tools calling rate-limited external APIs |
| `cache_ttl_ms` | int \| null | null (no cache) | Cache identical calls for this duration; 0 or null disables caching |

### Worked Manifest Entry

```yaml
recipe_search:
  tool_id: recipe_search
  name: "Search recipes"
  description: "Search recipe database by ingredients, cuisine, or dietary restriction"
  input_schema: schemas/recipe_search_input.json
  output_schema: schemas/recipe_search_output.json
  idempotent: true
  timeout_ms: 10000
  accesses_private_data: false
  receives_untrusted_input: false
  communicates_externally: false
  max_retries: null              # use global resilience default
  requires_approval: false
  rate_limit_rpm: null
  cache_ttl_ms: 60000            # cache search results for 1 min

timer_set:
  tool_id: timer_set
  name: "Set cooking timer"
  description: "Set a countdown timer for a cooking step"
  input_schema: schemas/timer_set_input.json
  output_schema: schemas/timer_set_output.json
  idempotent: false
  timeout_ms: 5000
  accesses_private_data: false
  receives_untrusted_input: false
  communicates_externally: true   # sends command to IoT device
  max_retries: 1                 # no retry for side-effecting timer
  requires_approval: false
  rate_limit_rpm: null
  cache_ttl_ms: 0                # never cache side effects

nutrition_lookup:
  tool_id: nutrition_lookup
  name: "Look up nutrition info"
  description: "Retrieve nutritional data for an ingredient or recipe"
  input_schema: schemas/nutrition_lookup_input.json
  output_schema: schemas/nutrition_lookup_output.json
  idempotent: true
  timeout_ms: 15000
  accesses_private_data: false
  receives_untrusted_input: false
  communicates_externally: true   # calls external USDA API
  max_retries: null
  requires_approval: false
  rate_limit_rpm: 30             # external API rate limit
  cache_ttl_ms: 300000           # cache nutrition data for 5 min
```

## Error Contract

Structured error responses that [PEX `recover()`](../modules/pex.md) can act on. Every tool failure returns a structured envelope with `error_category` so the policy can branch to the appropriate recovery strategy.

| Error category | HTTP analog | Retryable | PEX recovery strategy |
|---|---|---|---|
| validation_error | 400 | no | Slot correction |
| auth_error | 401/403 | no | Credential refresh → retry |
| not_found | 404 | no | Slot correction (entity doesn't exist) |
| rate_limit | 429 | yes | Retry with backoff |
| timeout | 408 | depends on idempotency | Retry if idempotent |
| server_error | 500 | yes | Retry, then graceful degradation |

Error envelope structure (returned by all tools on failure):

```json
{
  "status": "error",
  "error_category": "not_found",
  "message": "Recipe 'chicken marsala' not found in database",
  "retryable": false,
  "metadata": {
    "tool_id": "recipe_search",
    "attempt": 1
  }
}
```

## Canonical vs Domain-Specific Tools

### Canonical Tools

Patterns that appear across many domains. Still registered per-domain (different schemas and permissions), but the tool shape is reusable:

- `sql_execute` — run SQL queries (Data Analysis, Digital Marketer for analytics)
- `python_execute` — run Python scripts (Data Analysis for transforms, Programmer for scripting)
- `shell_run` — run shell commands (Programmer)
- `http_request` — generic API call (all domains, as a fallback)

### Domain-Specific Tools

Unique to one domain, wrapping a specific platform API:

- `google_ads_api` — Digital Marketer only
- `github_api` — Programmer only
- `timer_set` — Chef only (robot/IoT)

### Component Tools (Skill Access)

Some components are exposed as tools to skills during [PEX § Skill Invocation](../modules/pex.md). These are NOT registered in the tool manifest — PEX provides them directly to the skill alongside flow-specific tools.

| Component tool | Operations | In manifest? |
|---|---|---|
| context_coordinator | Read conversation history | No — provided by PEX |
| memory_manager | Read/write scratchpad, read preferences | No — provided by PEX |
| flow_stack | Read slot values, read flow metadata | No — provided by PEX |

These component tools + 1–3 flow-specific tools = 5–7 total tools per skill invocation.

### Not Tools

Handled by components and never exposed to skills or the manifest:

- Dialogue State → relevant info accessible through flow_stack
- LLM calls → the skill IS the LLM; [Prompt Engineer](../components/prompt_engineer.md) is not needed as a tool
- Ambiguity declaration → policy responsibility, not skill; skill returns `uncertain` outcome instead
- Display Frame → policy responsibility; skill returns data, policy creates the Frame
- Conversation management → NLU/RES

## Worked Examples

Representative tools for each domain. These are the shared and canonical tools — the backbone that most flows use. In practice, each domain will also have dedicated tools for flows with unique requirements. The tables show tool_id, category, real platform or service, idempotent flag, timeout, and which flows use each tool.

### Data Analysis

| tool_id | Category | Platform / Service | Idempotent | Timeout | Flows |
|---|---|---|---|---|---|
| sql_execute | Code execution | Postgres, BigQuery | depends | 15000 | query, filter, aggregate, join, compare |
| python_execute | Code execution | pandas, numpy | depends | 30000 | transform, compute, clean, reshape |
| dataset_load | Internal | CSV/Excel/Parquet ingestion | yes | 10000 | import, upload, connect |
| column_analyze | Internal | Profiling engine | yes | 10000 | profile, inspect, summarize |
| chart_render | Internal | matplotlib, plotly | yes | 15000 | visualize, plot, chart |
| formula_apply | Internal | Computation engine | yes | 5000 | calculate, derive |
| merge_run | Internal | Join engine | yes | 10000 | merge, combine, union |
| validate_check | Internal | Data validation | yes | 5000 | validate, audit, check |
| pivot_run | Internal | Reshape engine | yes | 10000 | pivot, crosstab |
| stat_compute | Internal | Statistical library | yes | 15000 | correlate, regress, test |
| export_run | External API | Google Sheets, S3 | no | 10000 | export, save, publish |
| report_schedule | External API | Email, Slack | no | 10000 | schedule, automate |

### Chef

| tool_id | Category | Platform / Service | Idempotent | Timeout | Flows |
|---|---|---|---|---|---|
| recipe_search | Internal | Recipe database | yes | 10000 | browse, find, match |
| recipe_get | Internal | Recipe database | yes | 5000 | detail, review |
| recipe_create | Internal | Recipe database | no | 10000 | create, draft |
| recipe_update | Internal | Recipe database | no | 10000 | modify, adjust, scale |
| substitution_find | Internal | Ingredient knowledge base | yes | 5000 | substitute, swap |
| safety_check | Internal | Food safety rules | yes | 5000 | check, validate, allergen |
| meal_plan | Internal | Planning engine | yes | 10000 | plan, schedule, prep |
| nutrition_lookup | External API | USDA FoodData Central, Nutritionix | yes | 15000 | nutrition, analyze |
| conversion_calc | Internal | Unit converter | yes | 5000 | convert, measure |
| timer_set | Execute | IoT/robot timer (theoretical) | no | 5000 | timer, alert |

### Programmer

| tool_id | Category | Platform / Service | Idempotent | Timeout | Flows |
|---|---|---|---|---|---|
| shell_run | Code execution | Terminal | no | 30000 | run, execute, build |
| python_execute | Code execution | Python runtime | no | 30000 | script, automate |
| github_api | External API | GitHub (PRs, issues, branches) | depends | 10000 | pr, issue, branch, commit |
| ci_trigger | External API | GitHub Actions, Jenkins | no | 10000 | test, build, pipeline |
| deploy_trigger | External API | Vercel, AWS, Railway | no | 15000 | deploy, release, rollback |
| package_manage | External API | npm, pip, cargo registries | depends | 10000 | install, update, audit |
| file_read | Internal | Filesystem | yes | 5000 | read, inspect, search |
| file_write | Internal | Filesystem | no | 5000 | write, create, edit |
| code_search | Internal | AST/grep engine | yes | 10000 | find, locate, reference |
| lint_run | Internal | ESLint, ruff | yes | 10000 | lint, format, check |
| test_run | Internal | pytest, vitest | yes | 30000 | test, verify, validate |
| mock_generate | Internal | Mock/fixture generator | yes | 5000 | mock, stub, fixture |

### Digital Marketer

| tool_id | Category | Platform / Service | Idempotent | Timeout | Flows |
|---|---|---|---|---|---|
| sql_execute | Code execution | Data warehouse (analytics) | depends | 15000 | query, report, segment |
| google_ads_api | External API | Google Ads | depends | 10000 | campaign, ad_group, keyword, bid |
| meta_ads_api | External API | Meta Ads Manager | depends | 10000 | campaign, audience, creative |
| analytics_get | External API | Amplitude, Segment, GA4 | yes | 10000 | analyze, track, funnel |
| cms_publish | External API | Substack, Medium, WordPress | no | 10000 | publish, draft, schedule |
| social_post | External API | LinkedIn, X, Instagram | no | 10000 | post, share, engage |
| crm_sync | External API | HubSpot, Salesforce | no | 10000 | sync, update, enrich |
| email_campaign | External API | Mailchimp, SendGrid | no | 10000 | send, sequence, template |
| seo_analyze | External API | Semrush, Ahrefs | yes | 15000 | audit, research, rank |
| audience_build | Internal | Segmentation engine | yes | 10000 | segment, target, cohort |
| ab_test_run | Internal | Optimizely, VWO | no | 10000 | test, experiment, variant |
| compliance_check | Internal | Policy rules engine | yes | 5000 | review, approve, flag |
| budget_allocate | Internal | Budget optimizer | yes | 10000 | allocate, forecast, optimize |

## Tool Count Guideline

A domain has at least as many tools as it has flows. The shared tools in the tables above form the backbone — the remaining flows each get a dedicated tool.

| Domain | Flows | Shared tools | Dedicated tools | Total |
|---|---|---|---|---|
| Data Analysis | 48 | 12 | 36+ | 48+ |
| Chef | 48 | 10 | 38+ | 48+ |
| Programmer | 48 | 12 | 36+ | 48+ |
| Digital Marketer | 48 | 13 | 35+ | 48+ |

Tools are modular. Adding a tool means writing a schema and a manifest entry. Removing a tool means deleting both. The policy tool config (see [Policy Tool Config](#policy-tool-config)) makes swapping tools a one-line change. If a tool serves 10+ flows, it might be doing too much — consider splitting by operation type.
