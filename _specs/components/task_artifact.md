# Task Artifact

The `TaskArtifact` is the policy's output for one turn — the structured payload PEX hands to RES. The name and shape align with the [A2A protocol](https://a2a-protocol.org/latest/specification/)'s notion of an *Artifact*: an agent's output for a task, composed of one or more *Parts*.

In A2A terms: our `flow` is A2A's `task`; our `TaskArtifact` is A2A's `artifact`; our `parts: list[Part]` is A2A's `parts` array (each element obeys the A2A v1.0 Part oneof contract). The visual building blocks we attach (cards, lists, selections, confirmations) keep their established name `BuildingBlock` rather than A2A's *Part* — A2A's *Part* is a content container (text, raw, url, data), conceptually closer to our `parts` field than to our visual blocks.

## The Attribute Lock

Every `TaskArtifact` has **3 stored attributes** plus **3 helper properties** that unpack the parts list. **Never add a new TaskArtifact attribute without explicit user approval.** Domain-specific data lives inside `blocks[].data` or inside a Part.

| Attribute | Type | Stored / derived | Purpose |
|---|---|---|---|
| `origin` | `str` | stored | Flow name that produced the artifact (e.g. `compose`, `audit`, `release`). Empty for system-emitted artifacts. RES uses this to pick the response template. |
| `parts` | `list[Part]` | stored | A2A v1.0 parts array. Each element is a `Part(text=…)` \| `Part(raw=…)` \| `Part(url=…)` \| `Part(data=…)` with optional `metadata` for tagging. The classification dict (violation / missing / entity / etc.) lives inside the first `data` Part. The agent's reasoning lives inside a `text` Part tagged `metadata={'kind':'thoughts'}`. Generated code lives inside a `text` Part tagged `metadata={'kind':'code'}`. |
| `blocks` | `list[BuildingBlock]` | stored | Visual building blocks targeting display panels. Each block self-describes its `type`, `data`, `panel`, and optional `expand` flag. May be empty. Distinct from `parts`: blocks are *visual UI units*; parts are *content* (text / image / data / url). |
| `data` | `dict` | property | First data Part's dict — the classification dict. Read as `artifact.data['violation']`. Empty dict when no data Part is present. |
| `thoughts` | `str` | property + setter | Agent's user-facing reasoning prose. Backed by a text Part tagged `metadata.kind='thoughts'`. Empty string when absent. |
| `code` | `str \| None` | property + setter | Generated code or raw payload. Backed by a text Part tagged `metadata.kind='code'`. `None` when absent. |

Artifact invariants: `origin`, `parts`, `blocks` always exist (parts/blocks may be empty lists). The helper properties never raise — `artifact.data` returns `{}`, `artifact.thoughts` returns `''`, `artifact.code` returns `None` when their backing Part is absent.

## The Part Oneof Contract

A `Part` is an A2A v1.0 content container. Each Part has **exactly one** of `text`, `raw`, `url`, `data` set, plus an optional `metadata` dict for tagging.

| Field | Shape | Typical use |
|---|---|---|
| `text` | `str` | Agent's textual output. Used internally for `thoughts` (`metadata.kind='thoughts'`) and `code` (`metadata.kind='code'`). Future: auxiliary text blocks, disclaimers. |
| `raw` | `bytes` | Inline binary payload — e.g. an image the agent generated. Serializes as base64-encoded string. |
| `url` | `str` | URI to external file content — e.g. a hosted image or document. |
| `data` | `dict` | Structured JSON. The first data Part carries the classification dict (`violation`, `missing`, `entity`, `metrics`, `findings`, `failed_tool`, `candidate`, `question`, …). |
| `metadata` | `dict` (optional) | A2A v1.0 extension. Used here for kind tagging on text Parts. Callers may add other keys (e.g., `mime` on raw/url Parts). |

Constructing a Part with zero or multiple oneof fields raises `ValueError` — the contract is enforced at construction.

## Artifact Lifecycle

- **Created** by the policy during PEX execution. The policy decides which blocks to attach, what to put in the classification dict, and what reasoning to expose via `thoughts`.
- **Scope**: One artifact per turn. Multi-turn flows produce a new artifact each turn; if a turn carries no new visual, the previous artifact stays on screen by default.
- **Discarded** when superseded by a newer artifact from the same flow, or when the flow completes.
- **Consumed** by RES after PEX execution. RES reads the artifact, picks a template via `origin`, and routes blocks to panels. RES never modifies the artifact's structural attributes.
- The artifact is not part of the dialogue state. Dialogue state tracks beliefs and intent; the artifact tracks what to display.

## Blocks

Artifacts carry a list of pre-built building blocks. Each block is self-describing — type, panel, data, optional expand flag.

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

An artifact may carry multiple blocks targeting different panels at the same time (e.g. a `selection` on top + a `card` on bottom). Chat-only flows attach no block — whatever was on screen stays.

### Panel Attribute

The `panel` attribute lives on **each block**, not on the artifact. Values: `'top'` or `'bottom'` (default: derived from block type — `BuildingBlock.__init__` auto-derives when not explicitly set).

- `'bottom'` — the grounding artifact (post draft, data table, outline) the user keeps attention on
- `'top'` — feedback, navigation, interaction (selections, lists, grids, confirmations, checklists, status)

The frontend derives `displayLayout` from which panel stores are populated:
- Both top + bottom → `'split'`
- Top only → `'top'`
- Bottom only (or neither) → `'bottom'` (default)

`toast` blocks bypass the persistent panels entirely and render in a transient drawer overlay above the display container — this lets the underlying card/list survive the notification.

### Pagination

When underlying data is too large for a single block, the block's `data` holds only the first page (default 512 rows). A reference ID points to the full source. Additional pages are fetched via paginated calls, not stored in the block. Artifacts always transmit full state — no diffing or incremental updates.

## Artifact Construction Patterns

The constructor accepts the **legacy ergonomic shape**: `parts=dict` is wrapped as the artifact's data Part; `thoughts` and `code` are each wrapped as a tagged text Part. This keeps callers concise — they don't need to instantiate `Part(...)` directly for the common case.

```python
TaskArtifact(origin=flow.name())                                                  # empty guard
artifact = TaskArtifact(flow.name(), thoughts='No outline yet, outlining first.') # stack-on
artifact = TaskArtifact(flow.name(), parts={'violation': 'failed_to_save'},       # error
                        thoughts='Outline shrunk from 5 bullets to 3 without an explicit removal directive.')
artifact = TaskArtifact(flow.name(), thoughts=text)                               # success
artifact.add_block({'type': 'card', 'data': {...}})                               # attach a visual block
artifact.add_part(raw=image_bytes, metadata={'mime': 'image/png'})                # attach an image Part
artifact.add_part(url='https://...', metadata={'mime': 'image/png'})              # attach a URL Part
```

`origin` is **always** the flow name. Error-ness lives in the classification dict (`'violation' in artifact.data`), not in `origin`. The only exception is artifacts built outside the policy layer — e.g., `Agent.take_turn`'s outer try/catch may use `origin='system'`.

Readers consume via the helper properties — never iterate `parts` directly for thoughts/code/classification:

```python
violation = artifact.data['violation']    # classification dict
reasoning = artifact.thoughts              # agent's user-facing prose
snippet   = artifact.code                  # generated code, or None
```

## Rendering Pipeline

- After PEX populates the artifact, RES picks an intent / domain template by `origin`, fills it with data from the completed flow + artifact, and routes each block to its declared panel.
- Artifact declares *what* to show; RES and the frontend Blocks decide *how*.
- Each block routes to its declared panel (`top` or `bottom`); transient block types (currently `toast`) divert to a drawer overlay instead of a persistent panel slot.
- Reference: [Building Blocks — Rendering Model](../utilities/blocks.md#rendering-model)
