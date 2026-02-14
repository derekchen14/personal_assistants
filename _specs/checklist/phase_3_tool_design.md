# Phase 3 — Tool Design

Derive the tool manifest from the flow catalog. Each flow needs tools — this phase designs the schemas, error contracts, and external service connections that make flows executable.

## Context

Tools are the bridge between flows and external systems. Flow Selection (Phase 2) defines *what* the agent can do; Tool Design defines *how*. Every flow needs at least one tool, and some flows share tools. Tools are modular: cheap to add, easy to swap, safe to remove.

**Prerequisites**: Phase 2 complete — 48 flows defined with slots and outputs in `ontology.py`.

**Outputs**: Tool manifest entries in `<domain>.yaml`, JSON Schema files in `schemas/`, verified external API connections.

**Spec references**: [tool_smith.md](../utilities/tool_smith.md), [pex.md § Policies and Tools](../modules/pex.md)

---

## Steps

### Step 1 — Group Flows by External System

Walk through all 48 flows and answer: "Which API, database, or service does each flow talk to?" Flows hitting the same system likely share a tool.

**Example grouping** (Chef domain):
- Recipe-related flows → recipe database → `recipe_search`, `recipe_get`, `recipe_create`, `recipe_update`
- Nutrition flows → USDA FoodData Central API → `nutrition_lookup`
- Timer flows → IoT timer service → `timer_set`, `timer_cancel`
- Safety flows → food safety rules → `safety_check`

### Step 2 — Identify Operations per System

For each system, determine what operations exist. Each distinct operation = one tool.

**Tool categories**:

| Category | What it does | Example |
|---|---|---|
| Code execution | Runs agent-generated code | sql_execute, python_execute, shell_run |
| External API | Calls a third-party platform | google_ads_api, github_api, nutrition_lookup |
| Internal service | Calls domain-internal logic | recipe_search, chart_render, lint_check |

**Operation types**:

| Operation | Idempotent | Typical timeout |
|---|---|---|
| search / get / read | yes | 5–15s |
| create / post | no | 10s |
| update / patch | no | 10s |
| delete | no | 5s |
| analyze / compute | yes | 15–30s |
| execute / run | no | varies |
| validate / check | yes | 5s |

### Step 3 — Map Slots to Tool Parameters

For each tool, list all the slots (from all flows that use it) as potential input parameters.

- **Required in schema** = required in *every* flow that uses the tool
- **Optional in schema** = required in *some* flows but not all
- Union of all flows' slots = tool's input schema

**Example** — `recipe_search` used by browse, find, match:
- browse slots: category (opt), cuisine (opt)
- find slots: recipe (req)
- match slots: ingredient (req), method (opt)
- Tool schema: query (req), filter (opt), exact (opt)

### Step 4 — Design JSON Schemas

Create input and output schemas for each tool. Follow these rules:

**Input schema**:
- Flat structure (no nesting beyond one level)
- Required fields = slots marked `(req)` in every using flow
- Use `enum` for `(elective)` slots
- snake_case field names
- `description` on every field
- `additionalProperties: false`

**Output schema**:
- Always include `status` field (success/error)
- Data in a `result` field (object or array)
- Include `metadata` for pagination, timestamps, source attribution
- Shape matches the block type (table data → array, card → object)

**Example input schema** (`schemas/recipe_search.json`):

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

### Step 5 — Define Error Contracts

Every tool failure returns a structured envelope with `error_category`:

| Error category | HTTP analog | Retryable | PEX recovery strategy |
|---|---|---|---|
| validation_error | 400 | no | Slot correction |
| auth_error | 401/403 | no | Credential refresh → retry |
| not_found | 404 | no | Slot correction (entity doesn't exist) |
| rate_limit | 429 | yes | Retry with backoff |
| timeout | 408 | depends on idempotency | Retry if idempotent |
| server_error | 500 | yes | Retry, then graceful degradation |

Error envelope structure:

```json
{
  "status": "error",
  "error_category": "not_found",
  "message": "Recipe 'chicken marsala' not found in database",
  "retryable": false,
  "metadata": { "tool_id": "recipe_search", "attempt": 1 }
}
```

### Step 6 — Set Capability Tags (Lethal Trifecta)

Three boolean tags classify each tool's security profile:

| Tag | Description |
|---|---|
| `accesses_private_data` | Reads/writes PII, credentials, or sensitive business data |
| `receives_untrusted_input` | Processes input from outside the system (uploads, external APIs) |
| `communicates_externally` | Sends data to external systems (email, Slack, webhooks) |

**Critical rule**: When all three tags are true on a single tool, that tool requires mandatory human approval (enforced by PEX pre-hook check #7). Any two together are safe with standard controls.

### Step 7 — Write Tool Manifest Entries

Add manifest entries to `<domain>.yaml` under a `tools` section. Each entry:

```yaml
recipe_search:
  tool_id: recipe_search
  name: "Search recipes"
  description: "Search recipe database by ingredients, cuisine, or dietary restriction"
  input_schema: schemas/recipe_search.json
  output_schema: schemas/recipe_search_output.json
  idempotent: true
  timeout_ms: 10000
  accesses_private_data: false
  receives_untrusted_input: false
  communicates_externally: false
  max_retries: null            # use global resilience default
  requires_approval: false
  rate_limit_rpm: null
  cache_ttl_ms: 60000          # cache search results for 1 min
```

**Naming convention**: `entity_verb` — snake_case, max 30 characters. Verb from: search, get, create, update, delete, analyze, check, set, run.

### Step 8 — Implement Service Classes

Tools are class methods on Python service classes. One class per external system.

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
        return {'status': 'success', 'result': rows,
                'metadata': {'total_count': len(rows), 'source': 'recipe_db'}}
```

**Rules**:
- One class per system: `RecipeService`, `GitHubService`, `NutritionService`
- Methods mirror tool naming: `service.verb(params)`
- All methods return envelopes (success or error, never raw returns)
- Instantiated at startup, injected into policies
- Connection state on the class, methods are stateless beyond `self`

### Step 9 — Component Tools (Not in Manifest)

Some components are exposed as tools to skills during PEX execution. These are NOT registered in the tool manifest — PEX provides them directly.

| Component tool | Operations |
|---|---|
| context_coordinator | Read conversation history |
| memory_manager | Read/write scratchpad, read preferences |
| flow_stack | Read slot values, read flow metadata |

These + 1–3 flow-specific tools = 5–7 total tools per skill invocation.

### Step 10 — External Service Connections

For domains integrating with external services, gather credentials and verify connectivity.

**Per-service setup**:

| Service | Auth Method | Env Vars | Setup Effort |
|---|---|---|---|
| GitHub | Fine-grained PAT | `GITHUB_TOKEN` | 5 min |
| Slack | Bot OAuth Token | `SLACK_BOT_TOKEN` | 10 min |
| LinkedIn | OAuth 2.0 | `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET` | 20 min |
| Substack | Browser cookies | `SUBSTACK_SID`, `SUBSTACK_LLI` | 5 min |

Store credentials in `.env` (never commit). Verify with a connectivity check script.

---

## Files to Modify/Create

| Action | File | Description |
|---|---|---|
| Modify | `<domain>/schemas/<domain>.yaml` | Add tools section with manifest entries |
| Create | `<domain>/schemas/<tool_id>.json` | JSON Schema file per tool (input + output) |
| Create | `shared/schemas/sql_execute.json` | Canonical tool schemas (shared across domains) |
| Create | `shared/schemas/python_execute.json` | Canonical tool schemas |
| Create | `shared/schemas/components/context_coordinator.json` | Component tool schemas (not in manifest) |
| Create | `shared/schemas/components/memory_manager.json` | Component tool schemas |
| Create | `shared/schemas/components/flow_stack.json` | Component tool schemas |
| Create | `<domain>/.env.example` | Document required API keys and credentials |

---

## Verification

- [ ] Every flow has at least one tool binding
- [ ] Tool count ≥ flow count (each flow has at least one tool)
- [ ] All JSON Schemas are valid and well-formed
- [ ] Input schemas have `description` on every field
- [ ] Output schemas include `status` and `result` fields
- [ ] All tools have `idempotent` annotation (true or false)
- [ ] All tools have `timeout_ms` configured
- [ ] Lethal Trifecta: no tool has all 3 capability tags true without `requires_approval: true`
- [ ] Error contract: all 6 error categories are documented
- [ ] Tool naming follows `entity_verb` pattern, snake_case, max 30 chars
- [ ] Service classes return structured envelopes (never raw returns)
- [ ] External API connections verified (if applicable)
- [ ] Component tool schemas exist in `shared/schemas/components/`
- [ ] `.env.example` documents all required environment variables
