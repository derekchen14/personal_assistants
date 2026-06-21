# Tool Branching Audit

**Purpose.** Every cell in the content-type × CRUD grid should be filled by exactly one canonical tool, so flows never face a "which tool do I call?" decision at runtime. Cells with more than one contender are conflicts we must resolve; empty cells are either genuinely N/A or a gap in the tool surface.

## Layers kept (and dropped)

Of the seven layers we started with, four survive into the grid:

- **Deterministic vs. agentic** — dropped. The tools are the same; the caller differs.
- **Local vs. external** — folded into the entity axis by adding `channel` as a content type.
- **Persistence vs. transient helper** — dropped. Transient helpers (`write_text`, `brainstorm_ideas`, `convert_to_prose`) are free to exist alongside the canonical tool; this audit only worries about persistence / retrieval tools where a single canonical choice matters.
- **Outline vs. prose** — kept, split across the entity axis (`post outline`, `post prose`, `section outline`, `section prose`).
- **CRUD** — kept as the action axis.
- **Post vs. section vs. snippet** — kept as the content axis, extended with `metadata` at the top and `channel` at the bottom.
- **Body vs. metadata** — kept. `metadata` is the top row.

That gives a content axis of **seven**: `metadata`, `post outline`, `post prose`, `section outline`, `section prose`, `snippet`, `channel`. Crossed with **CRUD**, the grid has 28 cells.

## The grid

Each cell names the single tool we believe owns the operation. A `?` flags uncertainty (tool may not exist or we need to confirm). A `N/A` is a deliberately empty cell. A line with two candidates is an unresolved conflict for the questions at the bottom.

| Entity | Create | Read | Update | Delete |
|---|---|---|---|---|
| **metadata** | `create_post` | `read_metadata` | `update_post` | `delete_post` |
| **post outline** | `generate_outline` | `read_metadata(include_outline=True)` | `generate_outline` | N/A (whole-post delete is `delete_post`; emptying just the outline is not a first-class op) |
| **post prose** | N/A (assembled per-section) | N/A (loops `read_section`) | N/A (per-section loop) | N/A |
| **section outline** | `insert_section` (shell) + `revise_content` (body) | `read_section` | `revise_content` (body) / `update_post` with `sections=[…]` (headings, position-by-position) | `remove_content` |
| **section prose** | `insert_section` (shell) + `revise_content` (body) | `read_section` | `revise_content` | `remove_content` |
| **snippet** | `revise_content(snip_id=<int>)` | `read_section(snip_id=..., include_sentence_ids=?)` | `revise_content(snip_id=(start, end))` | `remove_content(snip_id=...)` |
| **channel** | N/A (channels are configured, not created at runtime) | `channel_status` | `release_post` / `promote_post` / `cancel_release` (three distinct verbs) | N/A (channels are not deleted at runtime) |

## Empty cells

Three cells are intentionally N/A and we should confirm we are comfortable leaving them empty:

- **post prose** as a whole is not a first-class target. Prose lives per-section; whole-post prose operations loop over sections rather than using a single tool. Delete-whole-post-prose means deleting the post or clearing every section, neither of which is a post-prose operation per se.
- **channel create** is N/A because channels are configured in app setup, not created by the agent at runtime.
- **channel delete** is N/A for the same reason.

## Transient helpers

Not in the grid per the rules of this audit. Included here for completeness so we do not forget them:

- `write_text(prompt)` \u2014 generate a short text fragment. The skill wraps with `revise_content` or `insert_content` to persist.
- `brainstorm_ideas(topic)` \u2014 generate a list of angles or bullets. Wrapped by `generate_outline` or `insert_content`.
- `convert_to_prose(bullets)` \u2014 bullets to prose. Wrapped by `revise_content`.

## Obvious consolidations (already one tool per cell-cluster)

These groupings are settled; no decision needed.

- **Metadata reads**: `read_metadata(post_id, include_outline=, include_preview=)` covers metadata read and post-outline read via flags.
- **Section-level reads**: `read_section(post_id, sec_id)` returns the section content; the skill reads snippet content by locating the span in what came back, so the same tool covers section outline, section prose, and snippet reads.
- **Post-outline create and update**: `generate_outline(post_id, content)` replaces the full outline, so it owns both create and update.
- **Metadata delete**: `delete_post(post_id)` exists and owns the cell.

## Non-obvious conflicts to review

Each conflict below has a recommendation plus alternatives. Work through them one at a time so the decisions stay informed.

### Conflict 1: section outline delete \u2014 RESOLVED

**Cell**: section outline \u00d7 Delete.

**Decision**: `remove_content(post_id, sec_id)` owns single-section delete for both outline and prose. `generate_outline` is reserved for whole-post rewrites.

### Conflict 2: snippet update \u2014 RESOLVED (updated to `snip_id`)

**Cell**: snippet \u00d7 Update.

**Decision**: extend `revise_content(post_id, sec_id, content, snip_id=None)` with an optional `snip_id` parameter. The signature replaces the earlier `target={start, end}` proposal; `snip_id` models the section content as an ordered list of sentences and supports int or tuple indexing. `find_and_replace` is retired.

### Conflict 3: section outline update vs. section prose update \u2014 REVISED (merged)

**Cells**: section outline \u00d7 Update and section prose \u00d7 Update.

**Original decision (superseded)**: keep two tools \u2014 `generate_section` for outline, `revise_content` for prose.

**Current decision**: merge into `revise_content` for both shapes. `generate_section` was retired because (a) only one flow used it (refine) versus eight using `revise_content`, (b) its silent "first ## heading wins" parsing dropped data when callers passed multi-section content, and (c) the outline-vs-prose validation split moved to `_save_section_content` so every section write enforces structure regardless of caller. Heading rename moved to `update_post(updates={'sections': [<title 0>, <title 1>, \u2026]})` since heading is metadata, not content. The position-based shape avoids forcing the model to learn slug derivation and lets a single call rename multiple headings at once.

### Conflict 4: section create (the two-step pattern) \u2014 RESOLVED

**Cells**: section outline \u00d7 Create and section prose \u00d7 Create.

**Decision**: keep the two-step pattern. `insert_section(post_id, sec_id, section_title)` creates the section shell with explicit ordering after the anchor; the subsequent `revise_content(post_id, sec_id=<new slug>, content)` fills the body. Ordering intent stays legible and signatures stay small. The same pair handles both outline bodies and prose bodies \u2014 the body shape is just markdown.

### Conflict 5: channel update semantics \u2014 RESOLVED

**Cell**: channel \u00d7 Update.

**Decision**: keep three verbs \u2014 `release_post`, `promote_post`, `cancel_release`. They are distinct actions with purpose-fit signatures; CRUD's \"update\" is the wrong frame for channel state transitions.

### Conflict 6: snippet create \u2014 RESOLVED (updated to `snip_id`)

**Cell**: snippet \u00d7 Create.

**Decision**: span-add is `revise_content(post_id, sec_id, content, snip_id=<int>)`. The section is addressed as an ordered list of sentences; an integer `snip_id` points at one slot. `insert_content` is retired.

**Unified `snip_id` semantics** (shared by `read_section`, `revise_content`, `remove_content`):
- `snip_id=None` \u2014 the whole section.
- `snip_id=<int>` \u2014 a single sentence at that index (0-based). `-1` resolves to the last sentence (or the append position, in `revise_content`).
- `snip_id=(start, end)` \u2014 a slice of sentences, Python-style end-exclusive. Both endpoints must be non-negative integers in the range `0 \u2264 start \u2264 end \u2264 sentence_count`. `-1` is never valid as a range endpoint.

## Snippet identification (`snip_id`)

Section content is modelled as an ordered list of sentences. Every snippet-scoped tool accepts the same `snip_id` shape.

- **Source of truth for sentence counts**: `read_metadata(post_id)` returns a `sentence_count` per section so the skill can pick valid `snip_id` values before reading.
- **Previewing sentences with ids**: `read_section(post_id, sec_id, include_sentence_ids=True)` prepends each sentence with its index so the skill can locate spans by id rather than by substring match.
- **Slicing semantics**: int returns one sentence; tuple returns a slice. Index `0` is the first sentence; index `-1` is the last (single-int usage only). Ranges follow Python list-slicing conventions (end-exclusive), so `snip_id=(2, 5)` selects sentences at indices 2, 3, and 4.
- **Range endpoint rule**: both positions of a range must be non-negative integers within `0 \u2264 start \u2264 end \u2264 sentence_count`. `-1` has one meaning and one only \u2014 the last sentence when `snip_id` is a single integer. It is never a valid range endpoint; to reach through the end of a section, pass the concrete `sentence_count` from `read_metadata`.
- **Outline sections**: prose-oriented snippet operations do not apply. Whole-section outline updates go through `revise_content(post_id, sec_id, content)` even when only one bullet changes; the skill rewrites the bullet list wholesale. The validation that used to live in `generate_section` now runs in `_save_section_content`, so every save (outline or prose) is guarded.

### `revise_content` with `snip_id`

- `snip_id=None` \u2014 replace the whole section.
- `snip_id=<int>` \u2014 insert the new content at that index (pushes existing sentences right). `-1` means append to the end.
- `snip_id=(start, end)` \u2014 replace sentences in that range with the new content (find-and-replace semantics).

### `remove_content` with `snip_id`

- `snip_id=None` \u2014 delete the whole section.
- `snip_id=<int>` \u2014 delete that single sentence.
- `snip_id=(start, end)` \u2014 delete the slice of sentences in that range.
- Kept as a distinct tool from `revise_content(content='')` because the semantics (structural removal vs. content edit) and guardrails (only exposed to a few flows) differ.

## Tool Usage

### Metadata

- **Create**: `create_post(title="User Simulators for Training RL Agents", type="draft")`
- **Read**: `read_metadata(post_id="abcd0123")`
- **Update**: `update_post(post_id="abcd0123", updates={"status": "published"})`
- **Delete**: `delete_post(post_id="abcd0123")`

### Post outline

- **Create**: `generate_outline(post_id="abcd0123", content="## The Need for Data\n- why sims beat hand-labeling\n\n## Architectures of the Past\n- seq2seq\n- transformer era")`
- **Read**: `read_metadata(post_id="abcd0123", include_outline=True)`
- **Update**: `generate_outline(post_id="abcd0123", content=<full revised outline>)` \u2014 the tool always replaces the whole outline, so there is no separate update path.
- **Delete**: N/A. Deleting a post's outline is not a first-class operation; whole-post removal goes through `delete_post`.

### Post prose

- **Create**: N/A. Prose is assembled section by section; there is no whole-post prose create.
- **Read**: N/A. A caller loops `read_section` across the post's sections to see all prose.
- **Update**: N/A. Whole-post prose changes are a per-section loop of `revise_content`.
- **Delete**: N/A. There is no whole-post prose concept distinct from the underlying sections.

### Section outline

- **Create**: `insert_section(post_id="abcd0123", sec_id="motivation", section_title="Architectures of the Past")` (returns `sec_id="architectures-of-the-past"`) then `revise_content(post_id="abcd0123", sec_id="architectures-of-the-past", content="- seq2seq era\n- transformer era\n- self-play breakthroughs")`
- **Read**: `read_section(post_id="abcd0123", sec_id="architectures-of-the-past")`
- **Update body**: `revise_content(post_id="abcd0123", sec_id="architectures-of-the-past", content="- seq2seq era\n- transformer era\n- self-play breakthroughs\n- memory-augmented networks")`
- **Update heading (rename)**: `update_post(post_id="abcd0123", updates={"sections": ["The Need for Data", "Architectural Lineage"]})` — pass one heading per existing section, in order. Renames any that differ from the current titles.
- **Delete**: `remove_content(post_id="abcd0123", sec_id="architectures-of-the-past")`

### Section prose

- **Create**: `insert_section(post_id="abcd0123", after_sec="motivation", title="Architectures of the Past")` then `revise_content(post_id="abcd0123", sec_id="architectures-of-the-past", content="Early simulators relied on sequence-to-sequence models trained on scripted conversations. The transformer era shifted the focus from recurrent state to attention-based context windows...")`
- **Read**: `read_section(post_id="abcd0123", sec_id="architectures-of-the-past")`
- **Update**: `revise_content(post_id="abcd0123", sec_id="architectures-of-the-past", content=<full revised prose>)`
- **Delete**: `remove_content(post_id="abcd0123", sec_id="architectures-of-the-past")`

### Snippet

- **Create**: `revise_content(post_id="abcd0123", sec_id="architectures-of-the-past", content="Memory-augmented networks extended the horizon further.", snip_id=-1)` \u2014 append the sentence as the last one. Use any other integer to insert at that index instead.
- **Read**: `read_section(post_id="abcd0123", sec_id="architectures-of-the-past", snip_id=2)` \u2014 returns the third sentence. Pass `snip_id=(1, 4)` for a slice of sentences 1 through 3, or `include_sentence_ids=True` to prepend each sentence with its index.
- **Update**: `revise_content(post_id="abcd0123", sec_id="architectures-of-the-past", content="The transformer era collapsed that recurrent state into attention.", snip_id=(2, 4))` \u2014 replace sentences 2 and 3 with the new content (end-exclusive range).
- **Delete**: `remove_content(post_id="abcd0123", sec_id="architectures-of-the-past", snip_id=(2, 4))` \u2014 delete sentences 2 and 3.

### Channel

- **Create**: N/A. Channels are configured at app setup, not created at runtime.
- **Read**: `channel_status(channel="Substack")`
- **Update**: `release_post(post_id="abcd0123", channel="Substack")` publishes; `promote_post(post_id="abcd0123", channel="Substack")` amplifies; `cancel_release(post_id="abcd0123", channel="Substack")` unwinds.
- **Delete**: N/A. Channels persist across sessions; an operator removes them via app config, not through an agent tool.

## Next step

Land the tool-surface changes before the final Round-2 landings:

1. Extend `read_section` with `snip_id` and `include_sentence_ids` parameters.
2. Extend `read_metadata` to include a `sentence_count` per section in its response.
3. Extend `revise_content` and `remove_content` signatures to accept the optional `snip_id` parameter (int or tuple).
4. Retire `find_and_replace` and `insert_content` from `schemas/tools.yaml` and from every skill file that references them.
5. Update the round-2 drafts for `polish`, `add`, and `rework` so their Tools section reflects the new surface.
