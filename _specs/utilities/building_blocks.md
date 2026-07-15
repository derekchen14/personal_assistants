# Building Blocks

Engineering utility providing building blocks for creating a web app. Lives outside the agent.

Tech stack: Svelte 5, SvelteKit 2, TypeScript, Tailwind.

## Purpose

Standardized UI components that any domain agent can use to render its Task Artifacts. These are the atomic visual elements that PEX composes into full responses (and the main Agent delivers).

## Block Categories

- **Data display**: Tables, charts, cards, lists
- **Input collection**: Forms, selectors, date pickers, confirmation dialogs
- **Navigation**: Tabs, breadcrumbs, pagination
- **Feedback**: Toasts, progress indicators, loading states

Each block carries a **`panel` attribute** — `top`, `bottom`, or `left` — set per block by PEX. `left` is the dialogue/chat container (the conversation stream); `top` and `bottom` are the two zones of the display panel (see [Rendering Model](#rendering-model) below).

Display types map directly to atomic blocks. There is no intermediate composite layer — everything is flat. Domain-specific display types (defined in [Configuration](configuration.md)) resolve to the same atomic block set.

---

## Rendering Model

Every block sets a **`panel`** attribute — one of three placements:

| `panel` | Location | Typical blocks |
|---|---|---|
| `left` | The dialogue/chat container (conversation stream) | Ephemeral in-stream signals — toasts, progress, short confirmations |
| `top` | Display panel, top zone (feedback / interaction) | Forms, confirmations, status summaries |
| `bottom` | Display panel, bottom zone (grounding entity / artifact) — **default** | Cards, lists, tables, draft previews |

PEX sets `panel` when it composes the block onto the Task Artifact; the frontend places it accordingly. There is **no separate `inline` attribute** — an in-stream block is simply `panel: 'left'`. The display panel's visible zones (`top`/`bottom`/`split`) are derived from which zones are populated (see [Panel Zones](#panel-zones)).

### One Block Per Flow

Each flow **proposes** at most one block; PEX curates the active flows' proposed blocks onto the single turn [Task Artifact](../components/task_artifact.md) — by default passing them through, optionally rewriting for a clearer, more concise summary. If a turn requires two visuals, split across multiple flows — each flow contributes its own block, and PEX aggregates them.

### Panel Interactions

User actions on panel-rendered blocks (clicking a table row, submitting a form, selecting a chart data point) enter the pipeline as user actions — processed by NLU like any other user input. The frontend may also collect interaction analytics (GA4, etc.) separately, but that is outside the agent pipeline.

### Deliverable Persistence

Deliverables (published blog posts, scheduled events, submitted applications) are stored in domain-specific external systems (CMS, calendar, ATS) — not in the blocks layer or MEM. Blocks are transient views; persistence is the domain tool's responsibility.

### Referencing the Panel

When a block renders on the right panel alongside text, the text response can reference the visual. There are no response templates — PEX composes the text directly and may point at the on-screen block, e.g. "Here's your draft — preview it on the right." Reference: [PEX](../modules/pex.md)

---

## Panel Naming

- **dialogue_panel** (left): Conversation stream with user/agent messages
- **display_panel** (right): Visual blocks and artifacts

Follows Soleda convention. Layout ratio: dialogue_panel ~1/3 width, display_panel ~2/3 (`flex-1`). Thin `gap-3` between panels, no border divider.

## Panel Zones

The display_panel contains two zones: **top_container** (feedback/interaction) and **bottom_container** (grounding entity).

| Zone | Purpose | Block types |
|---|---|---|
| `top_container` | Feedback, interaction | Forms, confirmations, toasts, status summaries |
| `bottom_container` | Grounding entity, artifact | Cards, lists, tables, draft previews |

Controlled by a `displayLayout` store with three modes:

| Mode | Visible zones | When |
|---|---|---|
| `bottom` | bottom_container only | Default — artifact/entity blocks |
| `top` | top_container only | Form or confirmation without artifact |
| `split` | Both | Form + artifact simultaneously |

Each block's `panel` property (`'top'`, `'bottom'`, or `'left'`, default `'bottom'`) determines placement: `top`/`bottom` pick a display_panel zone, `left` renders in the dialogue panel. `displayLayout` (display-panel zones) is derived from which display zones are populated: both → `split`, top only → `top`, bottom only or neither → `bottom`.

## Light Theme

Off-white base with per-assistant brand colors:

| Variable | Value |
|---|---|
| `--color-bg` | `#f5f5f4` (stone-100) |
| `--color-surface` | `#ffffff` |
| `--color-border` | `#e7e5e4` (stone-200) |
| `--color-text` | `#1c1917` (stone-900) |
| `--color-text-muted` | `#78716c` (stone-500) |

## Brand Colors

Each assistant defines its own accent palette in `app.css`:

- `--color-accent` — primary brand color (buttons, links)
- `--color-accent-hover` — hover state
- `--color-accent-light` — tinted background (user bubble, subtle highlights)
- `--color-user-bubble` — user message background (= accent-light)
- `--color-agent-bubble` — agent message background (`#ffffff`)

A 2px accent-colored top border on the header bar provides immediate brand identification.

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

## Block Selection

There are no response templates. PEX picks the block type directly from the artifact's data shape — a given flow/artifact maps to a block type, and PEX chooses it based on what the data looks like (e.g., a single grounding entity → `card`, a set of candidates → `selection`). The mapping is a guideline; PEX makes the final call from the data on hand.

---

## Frontend State Management

The frontend organizes state into four store categories. Framework-agnostic — the categories matter, not the implementation.

| Category | Scope | Examples |
|---|---|---|
| **Conversation** | Current session | WebSocket connection, message history, conversation ID, typing state |
| **Data** | Active data context | Tab data (rows, pagination cursor, visibility), active table, column properties |
| **UI** | Layout and chrome | Layout mode (top/split/bottom), alerts, loading states, sidebar |
| **Display** | Block rendering | Active block, artifact data, chart config, interaction panels |

### Auto-Save and Interaction History

User interactions between turns (cell edits, column reorders, selections) are buffered in an `interactionHistory` array with a debounced timer (default 60 seconds). The buffer is flushed before sending new messages, giving the agent context about what the user did in the UI — not just what they said.

This feeds into NLU `react()` as user actions.

### Telemetry

Brief: structured frontend logging to a telemetry endpoint (`/api/v1/telemetry`) with request/session/conversation IDs, log levels (DEBUG through FATAL), and error stack traces. Implementation details follow the scaffold.
