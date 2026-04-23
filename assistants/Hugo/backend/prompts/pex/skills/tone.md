---
name: "tone"
description: "adjust tone or voice across the entire post; shifts register (formal, casual, technical, academic, witty, natural), adjusts sentence length and vocabulary complexity"
version: 2
tools:
  - read_metadata
  - read_section
  - revise_content
  - channel_status
---

This skill shifts the tone of a post — sentence length, vocabulary complexity, register. Preserves factual content and structure; only changes voice.

## Process

1. Read `<resolved_details>` for `source` (post), `chosen_tone` (CategorySlot: casual / professional / witty / authoritative / natural), and `custom_tone` (FreeTextSlot for user-described tone).
2. The policy commits a default tone if neither elective is filled — trust whatever value arrives.
3. For each section in the post:
   a. `read_section(post_id, sec_id)` to load current prose.
   b. Rewrite to the target tone. Preserve facts, paragraph breaks, headings.
   c. `revise_content(post_id, sec_id, content=<tone-shifted prose>)`.
4. Note any sections where the tone shift was structurally awkward (technical-heavy sections may resist a casual shift).

## Error Handling

If `revise_content` fails for a section, retry ONCE. If it fails again, skip that section and continue. After all sections are processed, call `execution_error(violation='tool_error', message=<sections that failed>, failed_tool='revise_content')`.

If both `chosen_tone` and `custom_tone` are filled and they conflict (e.g. casual + academic), call `handle_ambiguity(level='confirmation', observation='Two conflicting tones — pick one?')`.

## Tools

### Task-specific tools

- `read_metadata(post_id)` — fallback for section list when `<resolved_details>` is missing it.
- `read_section(post_id, sec_id)` — required before each rewrite.
- `revise_content(post_id, sec_id, content)` — save tone-shifted prose.

### General tools

- `execution_error(violation, message)`
- `handle_ambiguity(**params)`
- `manage_memory(**params)`
- `call_flow_stack(action, details)`

## Few-shot examples

### Example 1: Casual shift across the post

Resolved Details:
- Source: post=abcd0123 (3 sections: motivation, process, takeaways)
- Chosen_tone: casual

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=motivation)` → formal prose.
2. `revise_content(post_id=abcd0123, sec_id=motivation, content=<casual rewrite>)` → `_success=True`.
3. Repeat for process and takeaways.

Final reply:
```
Shifted all 3 sections to a casual tone. Process resisted slightly — the technical bits stayed precise but the framing loosened.
```

### Example 2: Custom tone description

Resolved Details:
- Source: post=abcd0123
- Custom_tone: "warmly skeptical — like a smart friend who likes the idea but pokes holes"

Trajectory:
1-3. Read each section, rewrite with the warmly-skeptical voice, save.

Final reply:
```
Reshaped the voice to be warmly skeptical across all 3 sections. Added a few "but here's the catch" moments where the original was too credulous.
```
