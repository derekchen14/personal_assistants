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

### Data
- The core payload. Shape varies by domain (dataframe for data analysis, file tree for coding, markdown for blogging, etc.).

### Code
- The generated code (SQL query, Python script, etc.) that produced the data.
- Top-level attribute so RES can display it to the user alongside the result.

### Source
- Where the data came from — the type of code or tool (SQL, Python, API, file system, etc.).
- Metadata about the execution method, not the code itself (code is stored separately above).

### Display Name
- Human-readable label for the entity being displayed.
- Table name for data analysis, file path for coding, post title for blogging.

### Display Type
- Governs how RES renders the frame content.
- Each domain defines its own set of display types. Common Attributes declares that every frame has a display type; the specific values are enumerated in Domain Attributes.

### Chart Type
- Optional. Visualization style: area, bar, stack, scatter, line.
- Cross-domain (schedulers chart time allocation, job hunters chart application funnels).

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

## Rendering Pipeline

- After PEX populates the frame, RES reads it and maps attributes to [Building Blocks](../utilities/blocks.md).
- Display types map directly to atomic blocks — no intermediate composite layer. Mapping is driven by display type and chart type. RES selects the appropriate block category (data display, input collection, navigation, feedback).
- **One frame = one block**: Each frame maps to exactly one block per turn. If a turn needs two visuals, use `keep_going` for multi-flow — each flow gets its own frame and block.
- Frame declares *what* to show; RES and Blocks decide *how*. Policy stays fully decoupled from rendering.
- The selected block type determines where it renders (right panel or inline) based on the type's baked-in `inline` attribute. Reference: [Building Blocks — Rendering Model](../utilities/blocks.md#rendering-model)
