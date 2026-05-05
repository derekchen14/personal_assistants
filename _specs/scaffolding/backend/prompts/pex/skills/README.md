# Skills

One markdown file per agentic flow: `<flow_name>.md`.

Layer 1 of the three-layer prompt architecture (the body that joins persona +
intent Background to form the system prompt). Deterministic flows have no
skill file — they call `tools(name, params)` directly from the policy.

## Frontmatter

Every skill starts with YAML frontmatter:

```yaml
---
name: <flow_name>            # matches flow.name()
description: <1-sentence purpose>
version: 1
stages:                      # optional; only if multi-stage
  - propose
  - direct
tools:                       # optional; explicit allowlist
  - find_posts
  - generate_outline
---
```

`PromptEngineer.load_skill_template(name)` parses + strips the frontmatter;
`load_skill_meta(name)` returns the parsed dict.

## Body Structure

```markdown
[one-line intro]

## Process
1. Read user guidance from `<resolved_details>` and `<recent_conversation>`.
2. <Identify target.>
3. <Do the work.>
4. <Save via the appropriate tool.>
5. End the turn.

## Error Handling
[invalid_input branch + handle_ambiguity branch + tool retry policy]

## Tools
### Task-specific tools
- `tool_name(params)` — description with em dash separator.
### General tools
- `execution_error`, `handle_ambiguity`, `manage_memory`, `call_flow_stack`

## Few-shot examples
### Example 1: <descriptive scenario name>
Resolved Details:
- Source: post=abcd0123
Trajectory:
1. `<tool_call>` → `_success=True`. End turn.
```

Examples must agree with the user message the starter would render — `sec`,
`target_section`, `user_text`, content-tag heading, and recent conversation
all in lockstep.
