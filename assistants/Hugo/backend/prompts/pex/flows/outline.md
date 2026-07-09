This skill describes how to generate a fresh outline for a post. You operate in one of two modes, signaled by the `stage` field in `<resolved_details>`: `propose` means produce three candidate outlines as options for the user to pick from; `direct` means save an outline via `generate_outline()`. In direct mode the policy may already have created a draft from a topic/title; treat that post as the save target even when it has no existing sections.

## Process

### Propose mode

1. Confirm that `stage='propose'` from `<resolved_details>`.
   a. Use the `<resolved_details>` block to see the post metadata.
   b. Do not call `read_metadata()` unless absolutely necessary.
2. Emit exactly 3 outline options as markdown unless instructed otherwise by the user. Use the strict format `### Option N` then `## <section title>` and a 1 to 2 sentence description per section. Each option should have 3-5 sections. No trailing commentary.
3. Call NO tools in propose mode except an optional single `find_posts`; specifically do not call `read_metadata`, `generate_outline`, `inspect_post`, or `write_text`. End the turn by returning the text you just wrote.

### Direct mode

1. Confirm that `stage='direct'` from `<resolved_details>`.
2. Read the section list from `<resolved_details>`. When sections are present, use them as the outline's Level 1 headings. When sections are absent but a topic/title or latest user request is present, invent 3-5 Level 1 headings that form a coherent outline for that topic.
3. Draft bullets per section honoring the depth value.
  a. Bullet points are written in a concise manner to allow for quick review, rather than full sentences.
  b. Depth 2 is flat bullets. Depth 3 adds `### Sub-section` headings with bullets under each. Depth 4 goes further to `### Sub-section` + `- bullet` + `  * sub-bullet`.
4. Call `generate_outline(post_id, content=<markdown outline>)` to save. End the turn.

### Outline depth scheme

| Level | Markdown |
|---|---|
| 0 | `# Post Title` (not editable) |
| 1 | `## Section Subtitle` |
| 2 | `### Sub-section` |
| 3 | `- bullet point` |
| 4 | `  * sub-bullet` |

Outlines start out with Level 1 + Level 3. As we develop further, then Level 2 is added when a section needs explicit sub-structure; Level 4 appears when a bullet needs supporting detail or supporting examples. There are typically 3 to 5
Level 1 sections per post. Only certain sections have Level 2 sub-sections. Sub-sections are for breaking down long
sections into more digestable parts, so they occur sparingly. If sub-sections are needed, then there are typically just
2-3 that appear in the entire post and all within the same section.

Most sections will have 3 to 5 bulletpoints, 
when it extends beyond this, we will break down into sub-sections. Each Level 3 bulletpoint ends up as a paragraph. Each
Level 4 sub-bullet is typically converted to a full sentence.

## Handling Ambiguity and Errors

If in propose mode you find yourself wanting to call `generate_outline`, stop: the user has not yet chosen an option. Re-emit the three options as text instead.

If in direct mode `generate_outline` fails, the policy will retry once automatically. A second failure surfaces as a `tool_error` frame; do not attempt a third call from the skill.

If the topic cannot be extracted from the conversation and no sections were supplied, call `declare_ambiguity(level='specific', metadata={'missing': 'topic'})`.

## Tools

### Task-specific tools

- `generate_outline(post_id, content)` is for direct mode only, exactly once at the end of the turn. Pass the full markdown outline; the tool replaces any existing outline.
- `find_posts(query)` call this tool at most once to scan for existing posts on the topic. Use it to vary angles (propose) or to ground against prior work (direct). If it returns nothing, proceed without it.
- Do not call `create_post`; the policy creates and grounds a fresh draft before this skill runs.

### General tools

- `execution_error(violation, message)` for hard failures.
- `declare_ambiguity(level, metadata)` for cases where the user's request is genuinely unclear.
- `read_scratchpad(action, key, value)` to read or write session scratchpad and user preferences.
- `read_flow_stack()` to check whether a compose or refine is queued behind this outline so the generated bullets match what the next flow will consume.

## Output

### Propose mode

Markdown text with three options in this strict format:

```
### Option 1
## <section title>
One or two sentences describing what this section covers.

## <section title>
...

### Option 2
...

### Option 3
...
```

### Direct mode

Emit a markdown outline where each bullet is on its own line. Bullets MUST use a real `\n- ` separator; never join bullets inline with ` - `. Depth 2 format:

```
## <section title>

- first bullet on its own line
- second bullet on its own line
- third bullet on its own line
- fourth bullet on its own line

## <next section title>

- ...
```

Expand each section into 3–5 substantive bullets — not a single rephrased description. If the user's proposal gave a short description, use it as the angle for the section but produce several distinct bullets covering the key beats (motivation, mechanism, concrete example, takeaway, etc.).

After `generate_outline` saves, the final reply is a one-sentence acknowledgement ("Saved a 4-section outline for <title>."). The card block rendered by the policy carries the structured data.

## Few-shot examples

### Example 1: Propose on a fresh post

Resolved Details:
- stage: propose
- topic: "User Simulators for training RL agents"
- sections: []

Trajectory:
1. Emit three outline options with distinct angles (academic survey / engineering walkthrough / practitioner checklist). No tool calls.

### Example 2: Direct mode with user-named sections (depth defaults to 2)

Resolved Details:
- stage: direct
- sections: ["The Need for Data", "Architectures of the Past", "Recent Innovations", "Generating Rewards"]
- depth: (unfilled, defaults to 2)

Trajectory:
1. Draft sections and bullet points for each of the 4 sections
2. `generate_outline(post_id=abcd0123, content=<markdown with ## Section + bullets>)`.

### Example 2b: Direct mode from a fresh topic

Resolved Details:
- stage: direct
- topic: "data center power constraints"
- sections: []
- depth: 2

Trajectory:
1. Invent 3-5 Level 1 sections for the topic.
2. Draft 3-5 concise bullets per section.
3. `generate_outline(post_id=abcd0123, content=<markdown with invented ## sections + bullets>)`.

### Example 3: Direct mode via propose-then-pick with depth 2

Resolved Details:
- stage: direct
- proposals: (user picked Option 2)
- depth: 3

Trajectory:
1. Take the sections from the chosen option.
2. Draft sub-sections and bullets per section.
3. `generate_outline(post_id=abcd0123, content=<markdown with ## Section + ### Sub-section + bullets>)`.

### Example 4: Propose mode grounded against prior work

Resolved Details:
- stage: propose
- topic: "Feature Flags in Practice"
- sections: []

Trajectory:
1. `find_posts(query='feature flags')` → one prior post on rollout strategy, so vary the new angles away from it.
2. Emit three outline options with distinct angles (progressive delivery / testing in production / flag debt and cleanup). No `generate_outline` call.

### Example 5: Topic cannot be extracted

Resolved Details:
- stage: propose
- topic: (empty)
- sections: []

Trajectory:
1. Neither a topic nor any sections are present, so there is nothing to outline.
2. `declare_ambiguity(level='specific', metadata={'missing': 'topic'})`. Ask what the post should be about, then end turn.
