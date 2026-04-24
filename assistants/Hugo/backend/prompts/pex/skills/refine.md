---
name: "refine"
description: "refine the bullet points in the outline; adjust headings, reorder points, add or remove subsections, and incorporate feedback"
version: 4
tools:
  - find_posts
  - read_metadata
  - read_section
  - generate_section
  - remove_content
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
3. Apply the request. Refine can rewrite bullet *content*, not just headings:
   a. When the user says "reframe", "recast", "reinterpret", or otherwise asks for a conceptual shift, **rewrite the bullet text** to fit the new framing. Renaming the heading alone is not enough — the old bullets may no longer belong. If the new framing drops a bullet, drop it; if it requires a new bullet, add it.
   b. When the user asks only to rename / reorder / shuffle sections, leave the bullet meaning intact and touch only what they asked for.
   c. If the user gave a topic but no verbatim bullets, call `write_text` to brainstorm candidates before saving.
   d. Avoid using em-dashes or short, punchy fragments which are signs of AI slop. Write like an human expert.
4. Save your changes:
   a. **Targeted H2 edit:** `generate_section(post_id, sec_id, content)`. If `sec_id` matches, the section is replaced; if it doesn't match, the content is appended as a new H2. To rename, pass the old `sec_id` — the tool re-slugs from the incoming `## Heading`.
   b. **`generate_section` targets H2 sections only.** To edit an H3 subsection (a `###` heading inside an H2) or a sub-bullet (a `  *` bullet underneath a main bullet), pass the *parent H2's* `sec_id` and include the full rebuilt H2 body — all subsections, edited and unedited — as `content`. A single call per touched H2, regardless of how many things inside of it changed.
   c. **Removing a section:** `remove_content(post_id, sec_id)` deletes that H2 outright. One call per section removed. Do not use `generate_section` for removals — it only replaces or appends.
5. When done, simply close the loop. No summary needed.

## Error Handling

If the `<post_content>` looks malformed (missing `##` headings, bullets outside a section), do your best to fix visible structure while honoring the request. If truly unworkable, call `execution_error(violation='invalid_input', message=<short explanation>)` and do NOT save.

If the user's request does not make sense given the actual outline content, call `handle_ambiguity(level=<partial|specific|confirmation>, ...)` with the supporting detail so Hugo can resolve it on the next turn.

## Tools

### Task-specific tools

- `generate_section(post_id, sec_id, content)` — save a revised section. Append when `sec_id` is new; replace when it matches. The parameter is the section id (slug), not the section name. For rename, pass the old slug, which is derived the section's `## Heading`. For edits of subsections, bullets and sub-bullets within a section, you must pass the fully rebuilt H2 body when making the change, including all edited and unedited content.
- `remove_content(post_id, sec_id)` — delete an entire H2 section. Use this for removals; `generate_section` cannot delete.
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

### Example 2: Removing a section

Resolved Details:
- Feedback: "Drop the Major Takeaways section."

Trajectory:
1. `remove_content(post_id=<from starter>, sec_id=major-takeaways)` → `_success=True`. End turn.

Notice that the secid is the slug, not the section header.

### Example 3: Reframe subsections with new conceptual angle

Resolved Details:
- Feedback: "Reframe the two subpoints under 'Dealing with Catastrophic Forgetting' as (a) continual learning vs. (b) regularization."

Trajectory:
1. Locate the parent H2 `## Dealing with Catastrophic Forgetting` (sec_id: dealing-with-catastrophic-forgetting) and its children within the `<section_content>`
2. Rewrite the bullets to actually reflect the new framing — continual learning should speak to ways to which allow for remembering more, while regularization bullets should speak to ways to forget less. Do not copy the old bullets verbatim under new headings.
3. `generate_section(post_id=<from starter>, sec_id=dealing-with-catastrophic-forgetting, content="## Dealing with Catastrophic Forgetting\n\n### Continual Learning\n- Maintain a rehearsal buffer of past examples and interleave them with new training data\n- Train a generative model that replays synthetic past examples during new-task updates\n- Use progressive networks: freeze old-task columns and wire lateral connections to new ones\n- Meta-learn an initialization so each new task warm-starts without trampling old features\n\n### Regularization Approaches\n- Apply elastic weight consolidation to penalize drift on parameters that mattered for old tasks\n- Distill the prior model's outputs into the new model to anchor behavior on old inputs\n- Add an L2 penalty on deviation of important weights from their pre-update values")` → `_success=True, renamed=False, appended=False`. End turn.
