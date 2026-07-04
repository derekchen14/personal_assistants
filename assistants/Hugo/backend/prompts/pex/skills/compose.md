---
name: "compose"
description: "Convert an outline into prose. Given a post in standard outline format, this skill provides the process to convert to a first written draft."
version: 4
tools:
  - read_metadata
  - read_section
  - convert_to_prose
  - write_text
  - revise_content
---

This skill describes how to convert an outline into prose. The current outline is provided in the user message inside the `<post_content>` block as per-section previews. Use it to plan scope; read the full bullets with `read_section` before converting each section.

## Process

### Outline depth scheme

| Level | Markdown |
|---|---|
| 0 | `# Post Title` (not editable) |
| 1 | `## Section Subtitle` |
| 2 | `### Sub-section` |
| 3 | `- bullet point` |
| 4 | `  * sub-bullet` |

### Conversion Steps

1. Read the user's guidance from the `<resolved_details>` block to decide what to do. Refer to `<recent_conversation>` for context.
   a. Only focus on the user's last utterance. Prior turns are context only.
   b. Requests from previous turns have already been addressed, so NEVER act on them.
2. Decide scope from the `<post_content>` previews and the user's latest utterance.
   a. If there is a named a single section ("compose the Motivation section") → process ONLY that section.
   b. If asked for the whole post ("convert the entire outline to prose") → process each section one at a time.
3. For each in-scope section, run this following loop:
   a. `read_section(post_id, sec_id)` — get the full bullets.
   b. `convert_to_prose(content)` — does a mechanical conversion to prose.
   c. Smooth out the content to flow smoothly. (See 'Writing Principles' below)
   d. `revise_content(post_id, sec_id, content)` — save the prose back to the section. 
4. Follow the Draft intent's output format — prose paragraphs separated by blank lines, no bullets inside a prose section.
   a. Honor the Guidance parameter as a soft preference (tone, length, hook) without displacing the primary goal.
   b. If Surrounding sections are already prose (visible in previews), match their tone and paragraph length.
   c. Do NOT invent new terminology — jargon must come from the outline or user.

### Writing Principles

Revising the content is your most important task since the other parts are straightforward. Please focus on making the content flow naturally by providing smooth transitions and full sentences rather than short, punchy statements.

- Voice & Tone
  * Write in active voice. Passive voice weakens clarity.
  * Prefer complete sentences that explain a thought fully.
  * Write in a precise tone for a semi-technical audience.
  * Do not exaggerate claims for the sake of impact. Thus, minimize words such 
   as "genuinely", "fundamentally", "remarkably". Instead, let the content speak for itself.

- Structure
  * The structure provided by the outline is your starting point, but it is ok to move things around 
    within a paragraph. If this occurs though, it only be for the sake of improving clarity.
  * Transitions between paragraphs are not required, but they are encouraged to summarize key points.
  * Don't frame points as "It's not X — it's Y." This creates false profundity. Don't build fake tension by negating two things before landing a point.
  * It's ok if paragraphs or sentences vary in length. We are optimizing for meaning, not word counts.

- Word Choice
  * Use concrete nouns and specific verbs over abstract ones.
  * Avoid jargon. Define technical terms on first use.
  * Cut filler phrases: "in order to" → "to", "due to the fact that" → "because".
  * Use plain language. Avoid words like: "load-bearing", "delve", "leverage", or "robust"
  * Avoid hedge words: "just", "really", "very", "quite", "somewhat".

- Common Anti-Patterns
  * No em dashes (—) as dramatic pauses. Use commas or parentheses, or re-write the points into multiple sentences.
  * No "In this article, we will explore..." openings. Start with the point. No "It's worth noting that..." — if it's worth noting, just note it.
  * No "Let's dive in" or "Without further ado" transitions.
  * Only one use of rhetorical questions at most in the entire post.
  * Avoid starting consecutive sentences with the same word.

- Formatting
  * Prefer *italics* for emphasis, use **bold** sparingly, never use ALL CAPS for emphasis.
  * Use bullet lists for 3+ parallel items. Use numbered lists only for sequences.
  * Include a blank line between paragraphs in markdown.

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
2. `convert_to_prose(content=<bullets>)` → rough prose; smooth it with a hook sentence.
3. `revise_content(post_id=abcd0123, sec_id=motivation, content=<smoothed prose>)` → `_success=True`. End turn.

### Example 2 — whole post with skip-on-failure

Resolved Details:
- Source: post=abcd0123
- User asked: "Convert the entire outline into prose."

Trajectory:
1. `read_section`/`convert_to_prose`/`revise_content` for Motivation → `_success=True`.
2. `read_section`/`convert_to_prose` for Process; `convert_to_prose` fails twice — skip Process, note for later.
3. `read_section`/`convert_to_prose`/`revise_content` for Takeaways → `_success=True`.
4. `execution_error(violation='tool_error', message='convert_to_prose failed twice for Process; skipped')`. End turn.
