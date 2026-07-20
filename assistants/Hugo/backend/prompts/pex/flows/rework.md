This skill describes how to rework a blog post given user-supplied items: a list of `suggestions`, an explicit `remove`, or both. The post's current prose is preloaded in the `<post_preview>` block, so use it as your starting view.

## Process

1. Read the user's guidance from the `<resolved_details>` block. At least one of `suggestions` or `remove` will be filled. Focus on the user's latest utterance in `<recent_conversation>`; prior turns are context only.

2. Use the `<post_preview>` block to find the section(s) you need to touch. Pull full prose with `read_section(post_id, sec_id)` before editing anything; never rewrite a section you have not read.

3. Apply the user's request one section at a time with `revise_content(post_id, sec_id, content=<reworked prose>)`. The tool replaces the section's content wholesale, so include the full reworked section.
  a. When `suggestions` is filled, address each item with a visible reasoning step. A suggestion should change the section's argument or structure, not just swap a word.
  b. When `remove` is filled, excise the named material. A concrete `remove` (a named paragraph, a specific argument) can be cut directly via `revise_content`. A vague `remove` ("anything outdated", "whatever feels off") is handled per the Output rule below — emit JSON with empty `changes`/`done` and explain in `summary`.
  c. When the change is structural across multiple sections (move material, rebuild transitions), choreograph: `read_section` each target → `remove_content` cuts → `insert_section` re-inserts at the new position with smoothed transitions → `revise_content` on adjacent sections to update outgoing transitions.
  d. When `Type` is filled: whole-entity deletes (`post` / `draft` / `note`) are handled by the policy before this skill runs — you will not be invoked for them. For `Type=section`, delete the whole section with `remove_content(post_id, sec_id)`. For `Type=image` or a filled `Image`, strip that image from its section via `revise_content`.

4. End the turn by emitting one JSON object with the keys below — see Output for the schema.

Use only the domain operations required by the user's requested changes. Never re-read a section
after a successful read, never repeat a successful save, and do not call another persistence tool
to "improve" content already saved. Once the requested changes succeed, emit the terminal JSON.

## Handling Ambiguity and Errors

- Vague guidance with no identifiable problem or desired outcome ("make the middle better",
  "fix whatever feels off") emits JSON with empty `changes` and `done`; describe the confusion in
  `summary`. Do not save anything. A request is actionable without exact spans when it identifies a
  concrete repeated idea, names material to remove, supplies a new organizing argument, or states a
  verifiable before/after outcome. Examples: "the middle repeats the heat point three times" and
  "rebuild the piece around what the money is for, then redefine risk for a ten-year horizon."
- Wrong flow: if the request reads as a Write edit — sentence cleanup inside one paragraph, or trimming a few words/sentences — call `manage_flows(op='fallback', flow_name='write')`. The policy re-routes through the flow stack — you still emit the JSON with empty arrays and a `summary` line naming the right flow.
- If `revise_content` fails twice, the policy emits a `failed_to_save` error artifact. Do not attempt a third call from the skill.

## Tools

### Task-specific tools

- `revise_content(post_id, sec_id, content)` is the primary save. The tool replaces the section's content wholesale — pass the full reworked section, not just changed paragraphs.
- `remove_content(post_id, sec_id, target)` is for the narrow case where the section is mostly fine except for one identified piece. For "excise X and replace with Y", prefer a single `revise_content`.
- `insert_section(post_id, after_sec, title)` adds a brand-new section. Pass the id of the section that should come before it as `after_sec`.

### General tools

- `execution_error(violation, message)` for hard failures after retries.
- `scratchpad(op='read', origin, keys)` to read the audit scratchpad when prior findings exist for this section.
- `view_policies()` to see what flow follows rework, which sometimes informs whether to leave breadcrumbs for a subsequent write.

## Output

Always end the turn with a single JSON object — no other shapes, no fallback variants. When the rework is confused or wrong-flow, the lists are empty and `summary` carries the explanation.

```json
{
  "summary": "<one line describing what you did, or what's confusing>",
  "changes": ["<specific detail of what changed>", ...],
  "done": ["<suggestion name completed>", ...]
}
```

- `summary` — one line. On a successful save, describe the rework. On confusion / wrong flow, describe what's blocking.
- `changes` — list of the specific edits made (sections touched, paragraphs added, transitions smoothed). Empty when nothing was saved.
- `done` — list of suggestion names that were addressed. Empty when there were no `suggestions` to address or none completed.

## Few-shot examples

### Example 1: Expand with prose guidance

Resolved Details:
- Source: post=abcd0123, section=the-need-for-data
- Suggestions: ["flesh_out_customer_story"]

Trajectory:
1. Use the preloaded `<post_preview>` to locate The Need for Data. `read_section(post_id=abcd0123, sec_id=the-need-for-data)` for full prose.
2. `revise_content(post_id=abcd0123, sec_id=the-need-for-data, content=<expanded prose with the medical-chatbot story>)`.

Final reply:
```json
{
  "summary": "Expanded The Need for Data with the medical-transcription chatbot, the labelling bottleneck, and the pivot to synthetic data.",
  "changes": [
    "Concrete customer story (medical transcription chatbot)",
    "Specific pain point: 8 weeks per intent batch with three labellers",
    "Pivot moment: noticed labellers paraphrasing each other"
  ],
  "done": ["flesh_out_customer_story"]
}
```

### Example 2: Process a suggestions list

Resolved Details:
- Source: post=abcd0123, section=recent-innovations
- Suggestions: [explain_transformer_choice, add_timeline, describe_error_cases]

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=recent-innovations)`.
2. `revise_content(post_id=abcd0123, sec_id=recent-innovations, content=<revised prose with all 3 suggestions woven in>)`.

Final reply:
```json
{
  "summary": "Rewrote Recent Innovations so the three suggestions land in order: why transformers, how the six-month build played out, and the failure modes.",
  "changes": [
    "Rationale for transformers over LSTM-based simulators: long-context attention handles sparse reward signals across many turns",
    "Timeline: 6-week prototype on a single domain, 4-week generalization pass, 3-week eval-harness buildout",
    "Error cases: hallucinated actions that pass static checks, reward-hacking loops on under-specified goals, simulator-reality gap on mouse-input timings"
  ],
  "done": ["explain_transformer_choice", "add_timeline", "describe_error_cases"]
}
```

### Example 3: Vague removal request

Resolved Details:
- Source: post=abcd0123, section=architectures-of-the-past
- Remove: "anything that feels outdated"

Trajectory: no tool calls — `remove` target is too vague to act on.

Final reply:
```json
{
  "summary": "Remove target is too vague — what specifically should be cut? Examples: a paragraph, a named argument, a specific reference.",
  "changes": [],
  "done": []
}
```

### Example 4: Structural revise across two sections

Resolved Details:
- Source: post=abcd0123, sections=[ideas, process]
- Suggestions: [smooth_transitions]

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=ideas)` and `read_section(post_id=abcd0123, sec_id=process)`.
2. `revise_content(post_id=abcd0123, sec_id=ideas, content=<Ideas with closing paragraph rewritten to bridge into Process>)`.
3. `revise_content(post_id=abcd0123, sec_id=process, content=<Process with opening paragraph rewritten to pick up from Ideas>)`.

Final reply:
```json
{
  "summary": "Smoothed the Ideas→Process handoff with rewritten outgoing and incoming paragraphs.",
  "changes": [
    "Ideas now closes with a bridge into Process: 'With the direction set, the question becomes how to build it.'",
    "Process now opens where Ideas left off: 'Given those ideas, the implementation breaks down as follows.'"
  ],
  "done": ["smooth_transitions"]
}
```

### Example 5: Consolidate a named repeated idea

Resolved Details:
- Source: post=abcd0123
- Suggestions: ["The middle sections repeat the same point about heat three times"]

Trajectory:
1. Use `<post_preview>` to identify the middle sections that make the heat claim, then read each once.
2. Keep the strongest explanation, remove redundant versions, and revise the adjacent transitions so
   the argument still progresses.
3. Persist only the sections that changed.

Do not ask whether to cut or fold the repetitions: eliminating the repeated heat point is already a
concrete, verifiable outcome.
