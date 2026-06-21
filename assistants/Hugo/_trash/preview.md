---
name: "preview"
description: "preview how the post will look when published; renders the post in the target channel's format so the user can review layout, images, and formatting before going live"
version: 2
tools:
  - read_metadata
  - read_section
---

This skill produces a publication-ready preview of a post — title, body, metadata, estimated read time, and any pre-publish issues.

## Process

1. Read `<resolved_details>` for `post_id` and optional `channel`.
2. Call `read_metadata(post_id)` to fetch title + section list + status.
3. For each section, call `read_section(post_id, sec_id)` to load the prose.
4. Assemble a preview that mirrors the target channel's format:
   a. If `channel` is filled (e.g. Substack, Medium), adapt headings, image rendering, and metadata fields per that channel's conventions.
   b. If absent, use the primary blog format.
5. Compute estimated read time (~200 words / minute).
6. Surface pre-publish issues: missing hero image, broken-looking links, sections without bullets that should have them, headings deeper than the channel supports.
7. Suggest a follow-up: `polish` for prose fixes, `release` to publish, or `tone` to shift voice.

## Error Handling

If a section read fails, render the preview without that section and note the gap in the issues list.

If the post body is empty, return a short preview noting the post is empty.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — title + section list.
- `read_section(post_id, sec_id)` — prose per section.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Standard preview

Resolved Details:
- Source: post=abcd0123 ("Building User Simulators")
- Channel: blog

Trajectory:
1. `read_metadata(post_id=abcd0123)` → 4 sections, ~2400 words, hero image present.
2. `read_section` for each.

Final reply:
```
**Preview: Building User Simulators** (blog format, ~12 min read)

[Hero image: synthetic-data-flow.png]

## Motivation
[…polished prose…]

## Process
[…]

## Architecture
[…]

## Takeaways
[…]

Pre-publish notes:
- Looks ready. No missing images or broken links detected.
- Want to release, or polish the Architecture section first?
```

### Example 2: Channel-specific preview with issue

Resolved Details:
- Source: post=abcd0123
- Channel: Substack

Final reply:
```
**Preview: Building User Simulators** (Substack format, ~12 min read)

[Cover image will appear at top]

[…body…]

Pre-publish notes:
- Substack truncates H4+ headings — your "Sub-section" header in Architecture won't render with the right hierarchy. Want me to flatten it via polish?
```
