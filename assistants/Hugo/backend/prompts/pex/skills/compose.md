---
name: "compose"
description: "write a section from scratch based on instructions or an outline. If only given a topic, generate an outline first; for editing existing content, use rework"
version: 3
tools:
  - read_metadata
  - read_section
  - convert_to_prose
  - write_text
  - revise_content
---

This skill describes how to convert an outline into prose. The current outline is provided in the user message inside the `<post_content>` block as per-section previews. Use it to plan scope; read the full bullets with `read_section` before converting each section.

## Process

1. Read the user's guidance from the `<resolved_details>` block to decide what to do. Refer to `<recent_conversation>` for context.
   a. Only focus on the user's last utterance. Prior turns are context only.
   b. Requests from previous turns have already been addressed, so NEVER act on them.
2. Decide scope from the `<post_content>` previews and the user's latest utterance.
   a. Named a single section ("compose the Motivation section") → process ONLY that section.
   b. Asked for the whole post ("convert the entire outline to prose") → process each section one at a time.
3. For each in-scope section, run this three-step loop:
   a. `read_section(post_id, sec_id)` — get the full bullets.
   b. `convert_to_prose(content)` — get a rough prose draft; polish for flow.
   c. `revise_content(post_id, sec_id, content)` — save the prose back to the section.
4. Follow the Draft intent's output format — prose paragraphs separated by blank lines, no bullets inside a prose section.
   a. Honor the Guidance parameter as a soft preference (tone, length, hook) without displacing the primary goal.
   b. If Surrounding sections are already prose (visible in previews), match their tone and paragraph length.
   c. Do NOT invent new terminology — jargon must come from the outline or user.

## Error Handling

If the `<post_content>` block looks malformed, best-effort convert the visible sections. If truly unworkable, call `execution_error(violation='invalid_input', message=<short explanation>)` and do NOT save.

If `convert_to_prose` fails for a section, retry ONCE. If it fails again, skip that section and continue — do NOT abort the whole flow. After saving all in-scope sections, note the skipped ones with `execution_error(violation='tool_error', message=<section names>)`.

If the user's request doesn't make sense given the outline, call `handle_ambiguity(level=<specific|partial|confirmation>, ...)`.

## Tools

### Task-specific tools

- `read_section(post_id, sec_id)` — required before composing any section. Never write without reading.
- `convert_to_prose(content)` — bullets → rough prose. Retry once on failure.
- `revise_content(post_id, sec_id, content)` — save prose back. This skill owns persistence: the policy does NOT auto-save.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1 — single named section

Resolved Details:
- Source: post=abcd0123
- User asked: "Compose just the Motivation section."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=motivation)` → bullets.
2. `convert_to_prose(content=<bullets>)` → rough prose; polish with a hook sentence.
3. `revise_content(post_id=abcd0123, sec_id=motivation, content=<polished prose>)` → `_success=True`. End turn.

### Example 2 — whole post with skip-on-failure

Resolved Details:
- Source: post=abcd0123
- User asked: "Convert the entire outline into prose."

Trajectory:
1. `read_section`/`convert_to_prose`/`revise_content` for Motivation → `_success=True`.
2. `read_section`/`convert_to_prose` for Process; `convert_to_prose` fails twice — skip Process, note for later.
3. `read_section`/`convert_to_prose`/`revise_content` for Takeaways → `_success=True`.
4. `execution_error(violation='tool_error', message='convert_to_prose failed twice for Process; skipped')`. End turn.
