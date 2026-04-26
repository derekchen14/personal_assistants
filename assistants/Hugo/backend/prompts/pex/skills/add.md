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
  d. When the user is asking for a brand-new top-level section (not bullets within an existing section), use `insert_section` to slot it in at the right position.

3. The target section should be provided for you within `<section_content>`. If you need to know the surrounding details, then call upon `read_section(post_id, sec_id)` before editing.

4. Carry out the changes:
  a. Follow the Draft intent's depth scheme for bullet content. Top-level bullets use `- bullet` at Level 3. Sub-bullets use `  * sub-bullet` at Level 4.
  b. Use `revise_content(post_id, sec_id, content, snip_id=idx)` for bullet notes and prose additions. Pass an integer `snip_id` to insert at a specific sentence index. When the user did not name a position, default to appending (`snip_id=-1`).
  c. Use `insert_section(post_id, sec_id, section_title, content)` to add a new H2 section. The `sec_id` is the *anchor* — the new section is inserted *immediately after* it. For "add a section before X", pass the sec_id of the section that comes *before* X in the outline. For "add a section after X", pass X's sec_id directly. `content` is the body bullets or prose only (no `## Heading` line); the title is passed via `section_title`.
  d. Use `insert_media(post_id, sec_id, image_type, description, position)` for images.

## Handling Ambiguity and Errors

If a named section does not exist on the post, make your best guess as to what the user is referring to. If it cannot be resolved, call `handle_ambiguity(level='specific', metadata={'missing_reference': <section_name>})`.

If `revise_content`, `insert_section`, or `insert_media` fails, retry ONCE with the same params. If it fails again, stop and call `execution_error(violation='tool_error', message=<what failed>)`.

## Tools

### Task-specific tools

- `read_section(post_id, sec_id, snip_id=None, include_sentence_ids=False)` required before inserting. Never add to a section you haven't read.
- `revise_content(post_id, sec_id, content, snip_id=...)` — add bullet notes or prose. Integer `snip_id` inserts at that sentence index; `-1` appends; a range `[start, end]` replaces the slice.
- `insert_section(post_id, sec_id, section_title, content)` — slot in a brand-new H2 section after the anchor `sec_id`. Use `section_ids` from the resolved-entities block to pick the right anchor for "before X" / "after X" requests.
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

### Example 2: Targeted changes via `additions`

Resolved Details:
- Source: post=abcd0123
- additions: {"recent-innovations": "Mention the self-play breakthrough from DeepMind"}

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=recent-innovations)` → current bullets.
2. `revise_content(post_id=abcd0123, sec_id=recent-innovations, content=<bullets with the self-play mention woven in>, snip_id=-1)`.

### Example 3: Adding a New Section

Resolved Details:
- Source: post=abcd0123, section=cracking-the-problem-of-control
- additions: {"<top-level>": "Add a section before 'Cracking the Problem of Control' describing what other inventors were attempting at the time"}
- section_ids (from resolved-entities): ["two-bicycle-mechanics-with-a-dream", "cracking-the-problem-of-control", "building-and-testing-the-flyer", ...]

Trajectory:
1. Identify the anchor: user wants the new section *before* `cracking-the-problem-of-control`, so the target anchor is actually the section that precedes it (`two-bicycle-mechanics-with-a-dream`) because `insert_section()` operates by adding a section *after* the anchor.
2. `insert_section(post_id=abcd0123, sec_id=two-bicycle-mechanics-with-a-dream, section_title="The Race to the Sky", content="- Samuel Pierpont Langley, backed by a $50,000 War Department grant, twice plunged the Aerodrome into the Potomac in 1903\n- Otto Lilienthal made over 2,000 glider flights but his aircraft offered no roll control and killed him in 1896\n- Hiram Maxim's massive steam-powered test rig briefly lifted off a track in 1894 but lacked any control system\n- Clement Ader claimed a powered hop in 1897 with no independent witnesses\n- A common thread: overemphasis on lift, treating in-flight control as secondary")` → `_success=True`. End turn.

### Example 4: Image into a section

Resolved Details:
- Source: post=abcd0123, section=recent-innovations
- image: {type: hero, description: "lineage diagram from RNNs to transformers"}
- position: top of section

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=recent-innovations)` → current content.
2. `insert_media(post_id=abcd0123, sec_id=recent-innovations, image_type='hero', description='lineage diagram from RNNs to transformers', position='top')`.
