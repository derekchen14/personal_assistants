---
name: "refine"
description: "refine the bullet points in the outline; adjust headings, reorder points, add or remove subsections, and incorporate feedback"
version: 5
tools:
  - find_posts
  - read_metadata
  - read_section
  - update_post
  - insert_section
  - revise_content
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
   d. Avoid using em-dashes or short, punchy fragments which are signs of AI slop. Write like a human expert.
4. Save your changes. The four operations map to four tools:
   a. **Edit an existing section's body** (rewrite bullets, restructure sub-bullets, edit H3s): `revise_content(post_id, sec_id, content)`. Pass the full rebuilt section body — H3 subsections + bullets, no `## Heading` line. The body replaces the section's content wholesale, so include every line you want kept.
   b. **Rename one or more section headings** (and only the headings): `update_post(post_id, updates={'sections': [<title 0>, <title 1>, ...]})`. The list must have one entry per existing section, in order — pass the current title for sections you don't want to change. Position-based, no slugs needed. Body content is untouched.
   c. **Insert a new H2 at a specific position**: `insert_section(post_id, sec_id=<anchor>, section_title='New Heading', content=<bullet body>)`. The new section is inserted *immediately after* the anchor `sec_id`. For "before X", anchor on the section that precedes X in `section_ids`. For "after X", anchor on X itself.
   d. **Remove a section**: `remove_content(post_id, sec_id)` deletes that H2 outright. One call per section removed.
5. When done, simply close the loop. No summary needed.

## Error Handling

If the `<post_content>` looks malformed (missing `##` headings, bullets outside a section), do your best to fix visible structure while honoring the request. If truly unworkable, call `execution_error(violation='invalid_input', message=<short explanation>)` and do NOT save.

If the user's request does not make sense given the actual outline content, call `handle_ambiguity(level=<partial|specific|confirmation>, ...)` with the supporting detail so Hugo can resolve it on the next turn.

## Tools

### Task-specific tools

- `revise_content(post_id, sec_id, content)` — primary save for body edits. Replaces the section's content wholesale; pass the full rebuilt body.
- `update_post(post_id, updates={'sections': [<title 0>, <title 1>, ...]})` — rename headings. The list runs position-by-position over existing sections and must match their count. Pass current titles for sections you aren't changing.
- `insert_section(post_id, sec_id, section_title, content)` — slot in a brand-new H2 section after the anchor `sec_id`. Pass the body lines directly as `content` (no `## Heading` line — the title goes via `section_title`).
- `remove_content(post_id, sec_id)` — delete an entire H2 section.
- `read_section(post_id, sec_id)` — read the prose of a specific section. Rare in refine; only when the preloaded outline truncated the content you need.
- `write_text(prompt)` — brainstorm candidate bullets or descriptions via an LLM. Use sparingly, only when the user asked for new content without specifying verbatim.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Rewriting a section's bullets

Resolved Details:
- Source: post=abcd0123, section=process
- Feedback: "Add under Process: design scenarios, assign labels, generate conversations."

Trajectory:
1. `revise_content(post_id=abcd0123, sec_id=process, content="- design scenarios\n- assign labels\n- generate conversations\n- evaluate")` → `_success=True`. End turn.

Notice the `content` does NOT include the `## Process` heading — only the body lines.

### Example 2: Inserting a new section before an existing one

Resolved Details:
- Source: post=abcd0123, section=cracking-the-problem-of-control
- Feedback: "Add a section before 'Cracking the Problem of Control' covering what other inventors were doing at the time"
- section_ids (from resolved-entities): ["two-bicycle-mechanics-with-a-dream", "cracking-the-problem-of-control", "building-and-testing-the-flyer", ...]

Trajectory:
1. Identify the anchor: the user wants the new section *before* `cracking-the-problem-of-control`, so anchor on the section that precedes it — `two-bicycle-mechanics-with-a-dream`.
2. `insert_section(post_id=abcd0123, sec_id=two-bicycle-mechanics-with-a-dream, section_title="The Race to the Sky", content="- Samuel Pierpont Langley, backed by a $50,000 War Department grant, twice plunged the Aerodrome into the Potomac in 1903\n- Otto Lilienthal made over 2,000 glider flights but his aircraft offered no roll control and killed him in 1896\n- Hiram Maxim's massive steam-powered test rig briefly lifted off a track in 1894 but lacked any control system\n- Clement Ader claimed a powered hop in 1897 with no independent witnesses\n- A common thread: overemphasis on lift, treating in-flight control as secondary")` → `_success=True`. End turn.

To put a new section *before* a target, pass the *previous* section's `sec_id` as the anchor. To put it *after* a target, pass the target's `sec_id` directly.

### Example 3: Removing a section

Resolved Details:
- Feedback: "Drop the Major Takeaways section."

Trajectory:
1. `remove_content(post_id=<from starter>, sec_id=major-takeaways)` → `_success=True`. End turn.

The `sec_id` is the slug, not the section header.

### Example 4: Renaming a heading

Resolved Details:
- Feedback: "Rename 'Cracking the Problem of Control' to 'Solving Three-Axis Control'."
- section_ids (from resolved-entities): ["two-bicycle-mechanics-with-a-dream", "cracking-the-problem-of-control", "building-and-testing-the-flyer", "from-kitty-hawk-to-the-world-stage"]

Trajectory:
1. Build the new headings list, keeping current titles for the sections that aren't changing: `['Two Bicycle Mechanics with a Dream', 'Solving Three-Axis Control', 'Building and Testing the Flyer', 'From Kitty Hawk to the World Stage']`.
2. `update_post(post_id=<from starter>, updates={'sections': [<the list above>]})` → `_success=True`. End turn.

The body of each section is untouched. If you need to rename AND rewrite bullets, follow with a `revise_content` using the renamed section's new slug (you can compute it by slugifying the new title, or read it back via `read_metadata`).

### Example 5: Reframe subsections with new conceptual angle

Resolved Details:
- Feedback: "Reframe the two subpoints under 'Dealing with Catastrophic Forgetting' as (a) continual learning vs. (b) regularization."

Trajectory:
1. Locate the parent H2 `## Dealing with Catastrophic Forgetting` (sec_id: dealing-with-catastrophic-forgetting) and its children within the `<section_content>`.
2. Rewrite the bullets to actually reflect the new framing — continual learning should speak to ways which allow for remembering more, while regularization bullets should speak to ways to forget less. Do not copy the old bullets verbatim under new headings.
3. `revise_content(post_id=<from starter>, sec_id=dealing-with-catastrophic-forgetting, content="### Continual Learning\n- Maintain a rehearsal buffer of past examples and interleave them with new training data\n- Train a generative model that replays synthetic past examples during new-task updates\n- Use progressive networks: freeze old-task columns and wire lateral connections to new ones\n- Meta-learn an initialization so each new task warm-starts without trampling old features\n\n### Regularization Approaches\n- Apply elastic weight consolidation to penalize drift on parameters that mattered for old tasks\n- Distill the prior model's outputs into the new model to anchor behavior on old inputs\n- Add an L2 penalty on deviation of important weights from their pre-update values")` → `_success=True`. End turn.
