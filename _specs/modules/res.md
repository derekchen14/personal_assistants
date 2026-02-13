# RES — Response Generator

The final stage of the agent pipeline. Consumes execution results and renders user-facing output — text responses, data visualizations, or both. Flow-agnostic: RES does not know which policy produced the result. It only needs the intent (from dialogue state) and the display frame.

**Module principle**: RES is read-only on the data layer. Its only state mutation is flow lifecycle cleanup — popping completed flows from the stack.

- **Respond function**: top-level entry point that routes to the appropriate sub-function
- **Generate function**: composes text responses via template-fill → naturalize pipeline
- **Clarify function**: generates clarification questions when ambiguity is present
- **Display function**: renders display frames into building blocks

Called in pipeline by the Agent: `respond()` is the entry point on every turn. It acts as a mini-agent within RES — it reads the intent, frame, dialogue state, Context Coordinator, and ambiguity handler, then uses a lightweight LLM call (Haiku) to decide which sub-functions to invoke: `generate()` for text, `clarify()` for clarification, `display()` for visuals. A single turn may invoke multiple sub-functions (e.g., both `generate()` and `display()`), so `respond()` may loop. `display()` is a no-op if no display frame exists. `display()` receives `generate()`'s output so it can coordinate layout and avoid duplicating information already in the text.

**Response pipeline**: Every text response follows the same two-phase pattern:
1. **Template fill** — load intent-specific template from the template registry, fill with data from completed flows, dialogue state, frame, and scratchpad
2. **Naturalize** — pass the filled template string through an intent-specific prompt via Prompt Engineer, which smooths it into natural language and fills in any details the template missed

For multi-flow turns (multiple flows completed via `keep_going`), each flow is filled + naturalized individually, then merged into one combined response.

Exceptions: Plan with `keep_going` and Internal produce no user-facing output (lifecycle cleanup still runs).

---

## Template Registry

A separate registry of templates — RES's dedicated resource.

### Base Templates

One base template per intent (Converse, Read, Prepare, Transform, Schedule, Plan, Internal). Each defines the response structure for that intent — what information to include and in what order. Templates are pre-formatted strings with placeholder slots.

### Domain Overrides

Domains can register full-replacement templates for specific flows that need different structure. Override keyed by dact name, completely replaces the base intent template — no patching or extending. If no override exists, the base template is used.

Lookup order: domain override (by dact) → base template (by intent).

Domain overrides can include two additional fields beyond the template string:
- **`block_hint`**: Suggested block type for `display()` to use when this template is active. `display()` may override based on frame attributes.
- **`skip_naturalize`**: When `true`, the filled template skips the naturalization phase (Step 3, Phase 2). Used for structured confirmations where the filled template is already natural enough.
- **Conditional sections**: Templates support simple if/else on slot values or flags, so one template handles multiple cases.

Reference: [Building Blocks — Block-Template Coordination](../utilities/blocks.md#block-template-coordination)

---

## Generate Function

Called by `respond()` after PEX on every turn — including `keep_going` turns (lifecycle cleanup still needed even when no text response is produced).

- **Input**: Dialogue state (intent + completed flow), display frame (if present), session scratchpad, context coordinator, ambiguity handler, prompt engineer, template registry
- **Output**: Text response (may be empty for keep_going / Internal), mutated dialogue state (completed flows popped), CC updated with agent utterance

### Pre-Hook: `start()`

4 checks:

1. **Pop Completed flows**: Remove all flows marked Completed from the stack. Retain the list of popped flows as full flow objects (dact, intent, slots, tool results, metadata) — these represent what just happened and heavily influence response composition.
2. **Snapshot trigger**: If > 1 completed flow popped, trigger dialogue state snapshot via Context Coordinator.
3. **Pop Invalid flows**: Remove all flows marked Invalid from the stack.
4. **Stack integrity**: Validate stack is well-formed. An empty stack is normal — it means the user's task is complete (not session end).

### Step 1 — Ambiguity Check

Before composing any response, check if the ambiguity handler has something to present.

- Call `present()` on the ambiguity handler to see if unresolved ambiguity exists.
- If ambiguity is present: call `ask()` on the handler. `ask()` returns clarification text to RES. RES writes it to CC as an agent utterance with turn type tag `clarification` and delivers to the user. Skip to Step 5.
- If no ambiguity: continue to Step 2.

This check runs before routing because ambiguity takes priority regardless of intent.

### Step 2 — Response Routing

Route by the completed flow's intent:

| Intent | Text response? | Next step |
|---|---|---|
| Converse | Yes | Step 3 |
| Read, Prepare, Transform, Schedule | Yes | Step 3 |
| Plan (with `keep_going`) | No | Skip to post-hook |
| Internal | No | Skip to post-hook |

RES is flow-agnostic at this stage — it only reads the intent from dialogue state, not the specific flow or policy that ran.

### Step 3 — Template Fill + Naturalize

**Single-flow case** (most common):

**Phase 1 — Template fill**:
- Look up template: domain override (by dact) → base template (by intent)
- Fill template slots from: the completed flow object (dact, intent, slot values, tool result), display frame attributes (if present), session scratchpad (metadata gathered by policy, especially for Converse), block metadata (panel_ref — so text can reference the visual, e.g., "preview it on the right")
- Result: a filled template string (structured but not yet natural-sounding)

**Phase 2 — Naturalize** (skipped if template has `skip_naturalize: true`):
- Pass the filled template string into an intent-specific naturalization prompt via Prompt Engineer
- The prompt is **frame-aware**: when a display frame will accompany the text, the prompt knows this and can reference the visual ("as shown below") rather than duplicating data in text
- Conversation history from Context Coordinator (`context.compile_history(turns=5)`) included for grounding
- User preferences from Memory Manager (verbosity, technical depth) included if available
- Result: final naturalized text response

Reference: [Prompt Engineer](../components/prompt_engineer.md), [Memory Manager](../components/memory_manager.md)

**Multi-flow case** (multiple flows completed in one turn, e.g., plan sub-flows):

Each completed flow gets its own fill + naturalize pass (same two phases above). Then a merge step combines the individual naturalized outputs:

| Condition | Merge method |
|---|---|
| ≤ 2 flows, outputs don't overlap | Deterministic: ordered concatenation with transition phrases |
| > 2 flows, or outputs overlap significantly | Prompt Engineer: LLM call to weave outputs into one coherent response |

### Step 4 — Streaming Decision

Applies only when a text response was generated in Step 3.

| Condition | Mode | Rationale |
|---|---|---|
| Long-form response (substantial content) | Stream | Reduces perceived latency |
| Short response | Buffer | Streaming overhead not worthwhile |

- Threshold: configurable in domain config (`stream_threshold_tokens`, default from shared defaults)
- When streaming: Prompt Engineer emits tokens incrementally during the naturalize phase
- When buffered: full response delivered at once after naturalization completes
- Reference: [Prompt Engineer](../components/prompt_engineer.md)

### Step 5 — CC Write

Write the final response to the Context Coordinator as an agent utterance.

- **Turn type tag**: `agent_response` (normal response) or `clarification` (ambiguity question from Step 1)
- **Content**: the text response (naturalized output from Step 3, or clarification text from Step 1)
- System turns are reserved for Internal flow results and error contexts — never for user-facing responses

Reference: [Context Coordinator](../components/context_coordinator.md)

### Post-Hook: `finish()`

4 checks:

1. **Response coherence**: If text response generated, verify it's non-empty and within length limits.
2. **Silent turn valid**: If no text response (keep_going / Internal), verify the flag or intent justifies silence.
3. **Lifecycle complete**: All Completed and Invalid flows were popped from stack.
4. **State consistency**: Dialogue state not corrupted — no orphaned slots, no cleared flags that shouldn't have been cleared.

---

## Display Function

Called by `respond()` after `generate()`. No-op if no display frame exists on the dialogue state.

- **Input**: Display frame, dialogue state, domain config, generate() output (text response — for layout coordination)
- **Output**: Rendered building blocks (tables, charts, pagination controls, etc.)

### Pre-Hook: Frame Validation

4 checks:

1. **Frame exists**: Display frame is present and non-empty.
2. **Required attributes**: `data` and `display_type` are set.
3. **Chart type valid**: If `chart_type` specified, it's a supported type in domain config.
4. **Pagination resolvable**: If `table_id` present, the reference is resolvable.

On failure: set graceful degradation metadata on the frame — generate() already produced a text summary, so the user gets something even if the visual fails.

### Step 1 — Frame-to-Block Mapping

- Map `display_type` directly to an atomic block type (table, chart, card, list, etc.) — no intermediate composite layer
- If the active template includes a `block_hint`, use it as the default mapping; override if frame attributes (data shape, chart type) require a different block
- The selected block type determines placement: panel (default) or inline (based on the type's baked-in `inline` attribute). Reference: [Building Blocks — Rendering Model](../utilities/blocks.md#rendering-model)
- Configure the block with frame attributes: `data`, `display_name`, `source`, `chart_type` (optional)
- Domain-specific display types: each domain defines its own enum of display types; mapping loaded from domain config
- If graceful degradation metadata exists (set by PEX recover()), attach limitation indicator to the block
- Coordinate with generate() output to avoid duplicating information already in the text response
- Reference: [Building Blocks](../utilities/blocks.md), [Display Frame](../components/display_frame.md)

### Step 2 — Data Rendering

- Render the building block with the data payload
- **Tables**: first page (default 512 rows), pagination controls if `table_id` exists
- **Charts**: configure axes, labels, colors from frame metadata
- **Large data**: truncation indicator with "load more" via `table_id` pagination reference
- **Multi-turn flows**: if frame was updated (not created fresh), render the update rather than recreating from scratch

### Post-Hook: Render Validation

3 checks:

1. **Block rendered**: No empty containers — data was actually rendered.
2. **Truncation bounded**: Data not silently truncated beyond configured limits.
3. **Degradation visible**: If graceful degradation metadata was set, limitation indicator is rendered for the user.

---

## Response Output Structure

`respond()` assembles and returns a structured response payload. Blocks within the payload can be streamed to the frontend for faster perceived responses.

| Field | Type | Description |
|---|---|---|
| `message` | `str` | HTML-formatted text response (from `generate()`) |
| `raw_utterance` | `str` | Pre-formatting text (for logging / CC storage) |
| `actions` | `list` | Reply suggestion pills for the user |
| `interaction` | `dict \| null` | Interactive panel JSON (e.g., measure config, column picker) |
| `code_snippet` | `dict` | `{source, snippet}` — generated code to display |
| `frame` | `dict \| null` | Rendered block data (table, chart, etc.) |
| `properties` | `dict` | Schema metadata and display properties (includes tab type if applicable) |
