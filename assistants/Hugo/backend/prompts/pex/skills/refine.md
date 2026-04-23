---
name: "refine"
description: "refine the bullet points in the outline; adjust headings, reorder points, add or remove subsections, and incorporate feedback"
version: 3
tools:
  - find_posts
  - read_metadata
  - read_section
  - generate_section
  - generate_outline
  - write_text
---

This skill describes how to refine outlines. The current outline is provided in the user message inside the `<post_content>` block. Use it directly as your starting point rather than creating a new one from scratch.

## Process

1. Read the user's guidance from the `<resolved_details>` block to decide what to do. Refer to the `<recent_conversation>` block for original context.
   a. Only focus on the user's last utterance in the conversation history. Prior turns are context only.
   b. Requests from previous turns have already been addressed, so NEVER act on them.
2. Identify which sections or bullets the user wants changed within the `<post_content>`.
   a. Scope your changes to the specific sections or sub-sections named.
   b. Do NOT try to do more than the user asked.
3. Adjust headings, bullet points, and section order per the user's request. Follow the outline depth scheme from the Draft intent. Insert sub-sections or sub-bullets when appropriate, but do not add unwarranted complexity.
   a. Consider the subject matter of the post when deciding how much depth to add.
   b. If the user asks for new bullet wording but gave only a topic, call `write_text` to brainstorm candidate bullets before saving.
4. Save your changes:
   a. **Targeted edit (default):** call `generate_section(post_id, sec_id, content)` once per changed section. If the section id is new, the content is appended at the tail. If the section id exists, the content replaces that section. To rename, pass the old `sec_id` — the tool re-slugs from the new `## Heading`.
   b. **Full-outline replace (removals only):** call `generate_outline(post_id, content)` once with the complete revised outline. Use this ONLY when removing sections — `generate_section` cannot delete.
5. When done, simply close the loop. No summary needed.

## Error Handling

If the `<post_content>` looks malformed (missing `##` headings, bullets outside a section), do your best to fix visible structure while honoring the request. If truly unworkable, call `execution_error(violation='invalid_input', message=<short explanation>)` and do NOT save.

If the user's request does not make sense given the actual outline content, call `handle_ambiguity(level=<partial|specific|confirmation>, ...)` with the supporting detail so Hugo can resolve it on the next turn.

## Tools

### Task-specific tools

- `generate_section(post_id, sec_id, content)` — save a revised section. Append when `sec_id` is new; replace when it matches. The parameter is the section id (slug), not the section name. For rename, pass the old slug; the tool rederives the slug from the incoming `## Heading`.
- `generate_outline(post_id, content)` — replace the ENTIRE outline. Only call this when removing one or more sections; `generate_section` cannot delete. Exactly one call per turn.
- `read_section(post_id, sec_id)` — read the prose of a specific section. Rare in refine; only when the preloaded outline truncated the content you need.
- `write_text(prompt)` — brainstorm candidate bullets or descriptions via an LLM. Use sparingly, only when the user asked for new content without specifying verbatim.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Appending bullets

Resolved Details:
- Feedback: "Add under Process: design scenarios, assign labels, generate conversations."

Trajectory:
1. `generate_section(post_id=<from starter>, sec_id=process, content="## Process\n  - design scenarios\n  - assign labels\n  - generate conversations\n  - evaluate")` → `_success=True`. End turn.

### Example 2: Reordering and renaming sections

Resolved Details:
- Feedback: "Rename Ideas to Breakthrough Ideas and tighten its bullets."

Trajectory:
1. `generate_section(post_id=<from starter>, sec_id=ideas, content="## Breakthrough Ideas\n  - bullet A tightened\n  - bullet B tightened")` → `_success=True, renamed=True`. End turn.

### Example 3: Removing a section

Resolved Details:
- Feedback: "Drop the Takeaways section."

Trajectory:
1. `generate_outline(post_id=<from starter>, content=<full outline with Takeaways omitted>)` → `_success=True`. End turn.
