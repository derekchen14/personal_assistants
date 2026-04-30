# Display Frame

Decouples transforming the data (the policy's job) from displaying the data (RES's job). A frame holds the core entities for the active flow that RES needs to render the correct views.

## Core Concept

The primary goal of the frame is to hold onto all the information that RES needs to display the correct views. The "core entity" depends on the domain:

| Domain | Core Entities |
|---|---|
| Data analysis | Table, row, column |
| Coding | Folder, file, function |
| Blogging | Post, section, draft |
| Job hunting | Listing, application, resume |
| Scheduling | Event, calendar, time block |

## Frame Lifecycle

- **Created** by the policy during PEX execution. Each policy decides which core entities to extract and what attributes to set.
- **Scope**: One frame per flow (not per turn). A flow can span multiple turns, and the frame persists for the duration of that flow. The policy can update the frame on subsequent turns within the same flow (e.g., user says "filter that to Q4" → policy updates the existing frame's data).
- **Discarded** when the flow completes or is popped from the flow stack.
- **Consumed** by RES after each PEX execution. RES reads the current frame state and maps it to Building Blocks. RES never modifies the frame.
- The frame is not part of the dialogue state. Dialogue state tracks beliefs and intent; the frame tracks what to display.

## Common Attributes

These are the base attributes every domain shares.

### Origin
- The flow name that produced the frame (e.g. `compose`, `audit`, `release`). Empty string for system-emitted frames that don't run a flow (sidebar refresh, post view).
- Used by RES to pick the response template and by the frontend to drive flow-specific UI behavior.

### Blocks
- A list of building blocks. Each block carries its own `data` payload, `panel` target, block `type`, and optional `expand` flag.
- Frames may carry multiple blocks targeting different panels (e.g. a selection on top + a card on bottom).
- Block-level `panel` attribute (`'top' | 'bottom'`) — auto-derived from block type when not explicitly set: `confirmation`, `toast`, `list`, `grid`, `selection`, `checklist` default to `top`; `card`, `compare` default to `bottom`.

### Metadata
- Domain- and flow-specific classification keys (violation codes, missing-slot names, finding summaries, etc.). Sparse — flow identity goes in `origin`, not metadata.
- Replaces what earlier drafts called "display name", "display type", and "chart type."

### Code
- The generated code (SQL query, Python script, etc.) that produced the data.
- Top-level attribute so RES can display it to the user alongside the result.

### Thoughts
- User-facing prose attached to the frame. Goes through RES naturalization. No em-dashes (hard to read on small screens).

## Domain Attributes

Each domain extends the common attributes with domain-specific fields. Data analysis is the primary detailed example; other domains will define their own display types and attribute sets when those agents are built.

### Data Analysis

Display types for data analysis frames:

| Type | Description |
|---|---|
| Default | Shows underlying data with pagination beyond 1K lines |
| Derived | A subset of a table, resulting from a SQL query |
| Dynamic | User can dynamically expand/collapse rows, including nested components |
| Decision | Allows user to pick certain columns or cells to indicate a value |
| Pivot | Multiple forms of grouping and breakdowns |

Additional domain-specific attributes for data analysis:

| Attribute | Type | Purpose |
|---|---|---|
| `shadow` | `dict` | Display transformations (formatting, column visibility, sort order) |
| `visual` | chart object | Chart/visualization if applicable (e.g., Plotly figure) |
| `issues_entity` | `dict` | `{tab, col, flow}` — tracks which entity has data quality issues |
| `resolved_rows` | `list` | Row IDs that were corrected during issue resolution |
| `active_conflicts` | `list` | Conflict cards for interactive resolution (e.g., deduplication) |

Other domains define their own extension attributes when built. Display types are also domain-specific — most domains will not need the table-oriented types above.

## Pagination

- Frames always transmit full state — no diffing or incremental updates.
- When underlying data is too large, the `data` attribute holds only the first page (default: 512 rows). A reference ID (`table_id`) points to the full data source. The page size is configurable per domain.
- Additional pages are fetched via paginated calls to the underlying source, not stored in the frame.
- When using a reference, display name is set to `<reference>` to signal it's a pointer, not a literal label.

## Panel Attribute

The `panel` attribute lives on **each block**, not on the frame. A frame can carry blocks targeting different panels at the same time (e.g. a selection on top while a card stays on bottom). Values: `'top'` or `'bottom'` (default: derived from block type).

- `'bottom'` — grounding entity (blog draft, data table, outlines) — the artifact users keep their attention on
- `'top'` — feedback, interaction, navigation (forms, confirmations, lists, grids, selections, checklists, status summaries)

`BuildingBlock.__init__` auto-derives the panel from the block type when not explicitly provided: `confirmation`, `toast`, `list`, `grid`, `selection`, `checklist` → `'top'`; `card`, `compare` → `'bottom'`.

The frontend derives `displayLayout` from which panel stores are populated:
- Both top + bottom → `'split'`
- Top only → `'top'`
- Bottom only (or neither) → `'bottom'` (default)

Toast-type blocks bypass the persistent panels entirely and render in a transient drawer overlay above the display container — a frontend-side render choice that lets the underlying card/list survive the notification.

## Rendering Pipeline

- After PEX populates the frame, RES reads it and maps attributes to [Building Blocks](../utilities/blocks.md).
- Frames carry a list of pre-built blocks; the policy attaches as many as the turn needs (a selection block on top + a card on bottom is a normal pattern). Each block is self-describing: type, panel, data, and optional expand flag.
- Frame declares *what* to show; RES and Blocks decide *how*. Policy stays fully decoupled from rendering.
- Each block routes to its declared panel (`top` or `bottom`); transient block types (currently `toast`) divert to a drawer overlay instead of a persistent panel slot. Reference: [Building Blocks — Rendering Model](../utilities/blocks.md#rendering-model)
