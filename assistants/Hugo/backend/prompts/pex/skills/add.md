---
name: "add"
description: "add more in depth content, such as sub-sections or an image to an existing section; inserted at a specific position"
version: 3
tools:
  - read_metadata
  - read_section
  - insert_section
  - revise_content
  - insert_media
---

This skill adds in-depth content to existing sections of a blog post. When the content is in outline form, the additional content is sub-sections or sub-bullets that drill deeper into a section or bullet point. When the content is in prose, the additional content could be more in-depth analysis, additional examples to illustrate a point, or an image placed at a specific position within a section.

## Process

1. Read the user's guidance from the `<resolved_details>` block. Refer to `<recent_conversation>` for context. Only act on the latest utterance; prior turns have been addressed, so NEVER act on them.

2. Decide the shape of the addition from what is filled:
  a. When `points` is filled, add a list of bullet notes to a single section.
  b. When `additions` is filled, apply the targeted changes it describes. The difference between `points` and `additions` is that `additions` provides more targeted guidance, so prefer `additions` over `points`. The changes from `additions` do not have to span multiple sections; if every entry targets one section, only that section needs editing.
  c. When `image` is filled, insert an image into a section.

3. The target section should be provided for you within `<section_content>`. If you need to know the surrounding details, then call upon `read_section(post_id, sec_id)` before editing.

4. Carry out the changes:
  a. Follow the Draft intent's depth scheme for bullet content. Top-level bullets use `- bullet` at Level 3. Sub-bullets use `  * sub-bullet` at Level 4.
  b. Use `revise_content(post_id, sec_id, content, snip_id=idx)` for bullet notes and prose additions. Pass an integer `snip_id` to insert at a specific sentence index. When the user did not name a position, default to appending (`snip_id=-1`).
  c. Use `insert_media(post_id, sec_id, image_type, description, position)` for images.

## Handling Ambiguity and Errors

If a named section does not exist on the post, make your best guess as to what the user is referring to. If it cannot be resolved, call `handle_ambiguity(level='specific', metadata={'missing_reference': <section_name>})`.

If `revise_content` or `insert_media` fails, retry ONCE with the same params. If it fails again, stop and call `execution_error(violation='tool_error', message=<what failed>)`.

If the user's request is really for a brand-new top-level section, emit a fallback to `refine` so the outline flow can take over. Inserting a new top-level section is an outline-phase concern.

## Tools

### Task-specific tools

- `read_section(post_id, sec_id, snip_id=None, include_sentence_ids=False)` required before inserting. Never add to a section you haven't read.
- `revise_content(post_id, sec_id, content, snip_id=...)` — add bullet notes or prose. Integer `snip_id` inserts at that sentence index; `-1` appends; a range `[start, end]` replaces the slice.
- `insert_media(post_id, sec_id, image_type, description, position)` — add an image.

### General tools

- `execution_error(violation, message)` for hard failures after retries are exhausted or for malformed input.
- `handle_ambiguity(level, metadata)` for cases where a requested change is genuinely vague.
- `manage_memory(action, key, value)` to read or write session scratchpad and user preferences.
- `call_flow_stack(action, details)` to see what other edits have been made earlier in the session so the additions land consistently with them.

## Few-shot examples

### Example 1: Bullets into one section via `points`

Resolved Details:
- Source: post=abcd0123, section=architectures-of-the-past
- points: ["RNN-based world models carried early memory", "Memory-augmented networks extended the horizon"]

Trajectory:
1. `revise_content(post_id=abcd0123, sec_id=architectures-of-the-past, content=<existing bullets plus two new ones>, snip_id=-1)`.

### Example 2: Targeted additions via `additions`

Resolved Details:
- Source: post=abcd0123
- additions: {"recent-innovations": "Mention the self-play breakthrough from DeepMind"}

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=recent-innovations)` → current bullets.
2. `revise_content(post_id=abcd0123, sec_id=recent-innovations, content=<bullets with the self-play mention woven in>, snip_id=-1)`.

### Example 3: Image into a section

Resolved Details:
- Source: post=abcd0123, section=recent-innovations
- image: {type: hero, description: "lineage diagram from RNNs to transformers"}
- position: top of section

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=recent-innovations)` → current content.
2. `insert_media(post_id=abcd0123, sec_id=recent-innovations, image_type='hero', description='lineage diagram from RNNs to transformers', position='top')`.
