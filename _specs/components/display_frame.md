# Display Frame

Decouples transforming the data (the policy's job) from displaying the data (RES's job). A frame holds the building blocks RES needs to render the active flow's output, plus a small fixed set of metadata attributes for routing and naturalization.

## The Five-Attribute Lock

Every `DisplayFrame` has exactly five attributes — no more. Domain-specific data lives inside `blocks[].data`, never as new top-level fields. **Never add a new DisplayFrame attribute without explicit user approval.**

| Attribute | Type | Purpose |
|---|---|---|
| `origin` | `str` | Flow name that produced the frame (e.g. `compose`, `audit`, `release`). Empty string for system-emitted frames (sidebar refresh, post view). RES uses this to pick the response template. |
| `metadata` | `dict` | Sparse classification keys — `violation`, `missing_slot`, `missing_entity`, `missing_reference`, `failed_tool`, `candidate`. Flow identity goes in `origin`, not metadata. Specifics go in `thoughts`, not nested-underscore tokens. |
| `blocks` | `list` | Building blocks targeting display panels. Each block self-describes its `type`, `data`, `panel`, and optional `expand` flag. May be empty. |
| `code` | `str` | Generated code or raw payload (SQL query, Python script, tool error stack). Machine-consumable, copy-paste shaped. |
| `thoughts` | `str` | User-facing prose attached to the frame. Goes through RES naturalization. No em-dashes (hard to read on small screens). |

Frame invariants: every attribute exists on every frame; values may be empty (`''`, `[]`, `{}`) but never `None`. Check `frame.blocks` (truthy) when you need a non-empty list — never `hasattr` or `is not None`.

## Frame Lifecycle

- **Created** by the policy during PEX execution. The policy decides which blocks to attach, what classification to set in `metadata`, and what prose to place in `thoughts`.
- **Scope**: One frame per turn. Multi-turn flows produce a new frame each turn; if a turn carries no new visual, the previous frame stays on screen by default.
- **Discarded** when superseded by a newer frame from the same flow, or when the flow completes.
- **Consumed** by RES after PEX execution. RES reads the frame, picks a template via `origin`, and routes blocks to panels. RES never modifies the frame's structural attributes.
- The frame is not part of the dialogue state. Dialogue state tracks beliefs and intent; the frame tracks what to display.

## Blocks

Frames carry a list of pre-built building blocks. Each block is self-describing — type, panel, data, optional expand flag.

### Closed Block-Type Vocabulary

Block types are a closed set. Adding a new type requires explicit approval — most "new" rendering needs are met by reusing an existing type with different `data`.

| Type | Used for | Default panel |
|---|---|---|
| `card` | Updates the active grounding entity (post draft, table view, calendar view) | `bottom` |
| `compare` | Side-by-side comparison of two entities or revisions | `bottom` |
| `selection` | Candidate options the user picks from (proposals, audit findings) | `top` |
| `list` | Search results, browse output, multi-entity listings | `top` |
| `grid` | Tabular browsing — rows × columns | `top` |
| `checklist` | Ordered steps to accept / reject | `top` |
| `confirmation` | Single-question accept/decline UI | `top` |
| `toast` | Lightweight notification | overlay (Drawer) |

A frame may carry multiple blocks targeting different panels at the same time (e.g. a `selection` on top + a `card` on bottom). Chat-only flows attach no block — whatever was on screen stays.

### Panel Attribute

The `panel` attribute lives on **each block**, not on the frame. Values: `'top'` or `'bottom'` (default: derived from block type — `BuildingBlock.__init__` auto-derives when not explicitly set).

- `'bottom'` — the grounding artifact (post draft, data table, outline) the user keeps attention on
- `'top'` — feedback, navigation, interaction (selections, lists, grids, confirmations, checklists, status)

The frontend derives `displayLayout` from which panel stores are populated:
- Both top + bottom → `'split'`
- Top only → `'top'`
- Bottom only (or neither) → `'bottom'` (default)

`toast` blocks bypass the persistent panels entirely and render in a transient drawer overlay above the display container — this lets the underlying card/list survive the notification.

### Pagination

When underlying data is too large for a single block, the block's `data` holds only the first page (default 512 rows). A reference ID points to the full source. Additional pages are fetched via paginated calls, not stored in the block. Frames always transmit full state — no diffing or incremental updates.

## Frame Construction Patterns

Build `metadata` and `thoughts` first, then instantiate the frame in a single line. Empty guard frames shorten to `DisplayFrame(origin=flow.name())`.

```python
DisplayFrame(origin=flow.name())                                                # empty guard
frame = DisplayFrame(flow.name(), thoughts='No outline yet, outlining first.')  # stack-on
frame = DisplayFrame(flow.name(), metadata={'violation': 'failed_to_save'},     # error
                     thoughts='Outline shrunk from 5 bullets to 3 without an explicit removal directive.')
frame = DisplayFrame(flow.name(), thoughts=text)                                # success
frame.add_block({'type': 'card', 'data': {...}})                                # attach a block
```

`origin` is **always** the flow name. Error-ness lives in `metadata` (`'violation' in frame.metadata`), not in `origin`. The only exception is frames built outside the policy layer — e.g., `Agent.take_turn`'s outer try/catch may use `origin='system'`.

## Rendering Pipeline

- After PEX populates the frame, RES picks an intent / domain template by `origin`, fills it with data from the completed flow + frame, and routes each block to its declared panel.
- Frame declares *what* to show; RES and the frontend Blocks decide *how*.
- Each block routes to its declared panel (`top` or `bottom`); transient block types (currently `toast`) divert to a drawer overlay instead of a persistent panel slot.
- Reference: [Building Blocks — Rendering Model](../utilities/blocks.md#rendering-model)
