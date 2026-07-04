# Hugo Flow Reference — domain tables

Hugo-specific lookups for flow authoring. The **cross-assistant** conventions (slot priorities, ambiguity
levels, policy conventions, prompt architecture, verification) live in
`_specs/checklist/flow_authoring.md`; this file holds only what is specific to Hugo's domain — its tools,
content scopes, and identifier formats. Keep it in lockstep with `schemas/tools.yaml` and the flow
classes.

## Identifier formats

- **Post ID** — 8-char lowercase hex (first 8 of a UUID4), e.g. `abcd0123`.
- **Section ID** — slug: lowercase, punctuation-stripped, dash-separated, ≤80 chars, e.g.
  `motivation-and-goals`.
- **Flow name** — bare lowercase string (`outline`, `refine`, `rework`); also the scratchpad key and
  `TaskArtifact.origin`.

## Tool registry — CRUD × entity

One canonical tool per operation per entity. Cite by name; don't extend without approval. (Names verified
against `schemas/tools.yaml` / the PEX tool table.)

| Entity | Create | Read | Update | Delete |
|---|---|---|---|---|
| metadata | `create_post` | `read_metadata` | `update_post` | `delete_post` |
| post outline | `generate_outline` | `read_metadata(include_outline=True)` | `generate_outline` | `delete_post` |
| section | `insert_section` (shell) + `revise_content` (body) | `read_section` | `revise_content` | `remove_content` |
| snippet | `revise_content(snip_id=<int>)` | `read_section(snip_id=…)` | `revise_content(snip_id=(start,end))` | `remove_content(snip_id=…)` |
| channel | N/A (app setup) | `channel_status` / `list_channels` | `release_post` / `cancel_release` | N/A |

**Transient helpers** (wrapped by a canonical tool, never standalone persistence):
`write_text(prompt)` → short fragment, persist with `revise_content`; `brainstorm_ideas(topic)` → angles,
persist with `generate_outline`; `convert_to_prose(bullets)` → prose, persist with `revise_content`.

**Persistence ownership.** Agentic flows: the skill persists (via `revise_content` / `generate_outline`);
the policy does not auto-save. Deterministic flows: the policy saves inline. Never let both write — a
double write silently overwrites.

## Snippet semantics (`snip_id`)

A section is an ordered list of sentences. Snippet-scoped tools accept:

| `snip_id` | Meaning |
|---|---|
| `None` | Whole section |
| `<int>` | Single sentence at that index (0-based; `-1` = last) |
| `(start, end)` | Slice, Python-style end-exclusive |

- `revise_content`: `<int>` inserts at that index (`-1` appends); `(start, end)` replaces the range.
- `remove_content`: `<int>` deletes one sentence; `(start, end)` deletes the slice.
- **Range rule:** both endpoints are non-negative and `0 ≤ start ≤ end ≤ sentence_count`. `-1` is valid
  only as a single-int `snip_id`, never as a range endpoint.
- Source of truth for the count: `read_metadata(post_id)` returns `sentence_count` per section — read it
  before building a range.

## Content scopes (starter tags)

XML tags wrapping preloaded content in the user message; match the tag to the data's scope.

| Tag | Scope |
|---|---|
| `<post_content>` | Whole post (used when the post is still an outline) |
| `<post_preview>` | Post with sections + first lines of each (used when the post is prose) |
| `<section_content>` | Single-section work (most Revise-intent flows) |
| `<line_snippet>` | Snippet-level work (a sentence or bullet span) |
| `<channel_content>` | Publish-intent flows |

## Outline depth (5 levels)

| Level | Markdown |
|---|---|
| 0 | `# Post Title` (not editable) |
| 1 | `## Section` |
| 2 | `### Sub-section` |
| 3 | `- bullet` |
| 4 | `  * sub-bullet` |

Most outlines use Level 1 + Level 3. Add Level 2 only when a section needs explicit sub-structure; Level 4
only when a bullet needs supporting detail. The live constant is `OUTLINE_LEVELS` in
`backend/prompts/for_orchestrator.py`.

## Blocks

Render-block types and screen zones are cross-assistant — see `_specs/utilities/blocks.md`. Hugo's common
mappings: `card` for Draft/Revise post updates, `selection` for outline options / audit findings, `list`
for find/browse results, `toast` for release/schedule, no block for chat-only flows (the prior screen
stays; chat-only is additive, not a screen-clear).
