# Building Blocks

Engineering utility providing building blocks for creating a web app. Lives outside the agent.

Tech stack: Svelte 5, SvelteKit 2, TypeScript, Tailwind.

## Purpose

Standardized UI components that any domain agent can use to render its display frames. These are the atomic visual elements that RES composes into full responses.

## Block Categories

- **Data display**: Tables, charts, cards, lists
- **Input collection**: Forms, selectors, date pickers, confirmation dialogs
- **Navigation**: Tabs, breadcrumbs, pagination
- **Feedback**: Toasts, progress indicators, loading states

Each block type has a baked-in **`inline` attribute** — a property of the type itself, not set per-turn by PEX or RES. Inline blocks render within the conversation stream; all other blocks render on the right panel (see [Rendering Model](#rendering-model) below). RES knows where each block renders based on which block type it selects.

Display types map directly to atomic blocks. There is no intermediate composite layer — everything is flat. Domain-specific display types (defined in [Configuration](configuration.md)) resolve to the same atomic block set.

---

## Rendering Model

Blocks render in one of two locations:

| Location | Behavior |
|---|---|
| **Right panel** | Default. Rendered in a persistent panel alongside the conversation (analogous to Claude's artifacts pane). |
| **Inline** | Rendered within the conversation stream, interspersed with text (the dialogue panel). |

Placement is determined by the block type's `inline` attribute — a fixed property of the type, not a per-turn decision. RES selects a block type via `display()`, and the frontend places it accordingly. The agent never controls placement directly.

### Layout Modes

The right panel can collapse/expand to create three layout modes:

| Mode | Description |
|---|---|
| `split` | Both panels visible — dialogue panel on the left, right panel on the right (default) |
| `top` | Dialogue panel only — right panel collapsed |
| `bottom` | Right panel only — dialogue panel minimized |

Layout mode is controlled by the user, not the agent.

### Inline Blocks

Block types that carry `inline: true`:

- **Feedback**: Toasts, progress indicators, loading states — ephemeral signals that belong in the conversation flow
- **Confirmation dialogs**: Short yes/no prompts that need immediate inline response

All other block types (tables, charts, cards, forms, navigation) render on the right panel by default.

### One Frame, One Block

Each turn produces at most one display frame, which maps to one block. If a turn requires two visuals, use `keep_going` to split across multiple flows — each flow gets its own frame and block. Reference: [Display Frame](../components/display_frame.md)

### Panel Interactions

User actions on panel-rendered blocks (clicking a table row, submitting a form, selecting a chart data point) enter the pipeline as user actions — processed by NLU like any other user input. The frontend may also collect interaction analytics (GA4, etc.) separately, but that is outside the agent pipeline.

### Deliverable Persistence

Deliverables (published blog posts, scheduled events, submitted applications) are stored in domain-specific external systems (CMS, calendar, ATS) — not in the blocks layer or Memory Manager. Blocks are transient views; persistence is the domain tool's responsibility.

### Template Fill Reference

When a block renders on the right panel alongside text, the text response can reference the visual. RES templates support a `panel_ref` metadata field so filled text can include phrases like "Here's your draft — preview it on the right." Reference: [RES](../modules/res.md)

---

## Responsive Hints

Blocks carry rendering hints so the frontend can adapt to different contexts. This is entirely frontend-side — the agent never sees viewport, theme, or device information.

### Design Principles

- **Agent-unaware**: The agent produces the same output regardless of device or display context. Rendering hints are consumed exclusively by the frontend. This maintains the clean separation where blocks "live outside the agent."
- **Blocks-owned**: Rendering defaults are owned by this utility, not by domain configuration. Domains do not override rendering hints — they are universal across all agents.

### Hint Granularity

Per-block with global defaults:

- **Global defaults**: Apply to all block types (e.g., default font scale, default color scheme handling)
- **Per-block overrides**: Individual block types can specify their own rendering behavior (e.g., a table specifies its mobile fallback as a card list; a chart specifies its small-viewport simplification)

### v1 Dimensions

Two dimensions in v1:

| Dimension | Values | Example adaptation |
|---|---|---|
| **Viewport** | `mobile`, `desktop` | Table → scrollable card list on mobile |
| **Color scheme** | `dark`, `light` | Chart palette adjusted for contrast |

Deferred to future versions: accessibility preferences, input modality (touch vs. pointer).

### Hint Resolution

The frontend resolves rendering hints at render time:

1. Read the block type's per-block hints (if defined)
2. Fall back to global defaults for any unspecified dimensions
3. Apply the resolved hints based on the current viewport and color scheme

No domain config involved — resolution is purely within the blocks utility and frontend.

---

## Block-Template Coordination

RES templates (the dact overrides in the [Template Registry](../modules/res.md)) coordinate text responses with building blocks. This is not a separate layer — it extends the existing template system.

### Block Hint

Domain override templates can specify a `block_hint` — a suggested block type for `display()` to use when this template is active. `display()` uses the hint but can override it based on frame attributes (e.g., if data shape doesn't match the hinted type).

```
# Example dact override template entry
draft_preview:
  template: "Here's your draft — {title}. Preview it on the right."
  block_hint: card
  skip_naturalize: false
```

### Naturalization Opt-Out

Templates can flag `skip_naturalize: true` for structured confirmations where the filled template is already natural enough. This skips the LLM naturalization call, saving latency and cost. Best for short, formulaic responses like "Event created: {title} on {date}."

### Conditional Sections

Templates support simple if/else on slot values or flags. One template handles multiple cases rather than requiring separate templates:

```
# Example conditional in a template
event_created:
  template: |
    {title} scheduled for {date}.
    {% if conflict %}Note: this overlaps with {conflict_event}.{% endif %}
    {% if recurring %}Repeats {frequency}.{% endif %}
  block_hint: card
```

### Versioning

Templates follow the same `{template_id, version}` versioning scheme as [Prompt Engineer](../components/prompt_engineer.md). Evaluation tracks template performance uniformly via `prompt_version_id`. Reference: [Evaluation](evaluation.md)

---

## Frontend State Management

The frontend organizes state into four store categories. Framework-agnostic — the categories matter, not the implementation.

| Category | Scope | Examples |
|---|---|---|
| **Conversation** | Current session | WebSocket connection, message history, conversation ID, typing state |
| **Data** | Active data context | Tab data (rows, pagination cursor, visibility), active table, column properties |
| **UI** | Layout and chrome | Layout mode (top/split/bottom), alerts, loading states, sidebar |
| **Display** | Block rendering | Active block, frame data, chart config, interaction panels |

### Auto-Save and Interaction History

User interactions between turns (cell edits, column reorders, selections) are buffered in an `interactionHistory` array with a debounced timer (default 60 seconds). The buffer is flushed before sending new messages, giving the agent context about what the user did in the UI — not just what they said.

This feeds into NLU `react()` as user actions.

### Telemetry

Brief: structured frontend logging to a telemetry endpoint (`/api/v1/telemetry`) with request/session/conversation IDs, log levels (DEBUG through FATAL), and error stack traces. Implementation details follow the scaffold.
