---
name: "audit"
description: "check that the post is written in the user's voice rather than sounding like AI, then fix the drift directly; compares voice, terminology, formatting, and stylistic patterns against previous posts, and applies any requested tone shift"
version: 7
tools:
  - find_posts
  - compare_style
  - editor_review
  - inspect_post
  - read_section
  - revise_content
---

This skill audits a blog post for voice and style consistency and **fixes the drift itself**. First detect issues with the audit tools, then rewrite the affected sections via `revise_content` so they read in the user's voice. If a `tone` directive is present, shift the register across the post in the same pass. When the post already reads cleanly, make no edits and say so.

## Process

1. **Detect.** Run the audit tools that match the request:
   a. **`editor_review(content)`** — voice and AI-slop checks (em-dashes, fragments, fillers, vague attributions). Default-on. It takes PROSE, not an id: `read_section` the sections first and pass their combined text. It returns the editorial guide alongside the content — apply the guide's patterns yourself.
   b. **`inspect_post(post_id)`** — structural metrics (heading hierarchy, section word counts, paragraph density). Default-on.
   c. **`find_posts(status='published', count=<reference_count>)` + `compare_style(post_id, reference_ids=...)`** — voice comparison against prior published posts. Opt-in: run when the user asks for comparison or references their usual/typical voice, or when `reference_count` is set (default 3 references).
   Honor explicit exclusions ("just the editor part", "skip structure") — run only the requested family.

2. **Fix.** For each section that drifted, `read_section` it (if not already read), rewrite the prose to remove the AI tells / match the reference voice, and save with `revise_content(post_id, sec_id, content=<revised prose>)`. Preserve facts, structure, and headings — change voice and phrasing only. One `revise_content` call per section you change.

3. **Tone.** When `tone` is set in `<resolved_details>`, also shift the register across the post (sentence length, vocabulary, formality) toward the requested tone while fixing voice drift — fold it into the same per-section `revise_content` rewrites. `suggestions`, when present, are itemized tonal changes to apply.

4. **Summarize.** End the turn with a one-line summary of what you changed (or that nothing needed changing). The policy renders the updated post card.

## Handling Ambiguity and Errors

When a detection tool fails but another succeeds, proceed with the partial signal and note the gap in the summary.

If `revise_content` fails for a section, retry ONCE; if it fails again, skip that section, keep the others, and note it. If every tool fails, call `execution_error(violation='tool_error', message=<why>)`.

If the post already matches the user's voice and needs no edits, make no `revise_content` calls and return a summary saying so — that is a valid outcome, not an error.

## Tools

### Task-specific tools

- `editor_review(content)` returns the fixed editorial style guide plus the content you passed; apply the guide yourself. Pass the post's full prose (combine `read_section` outputs), never the title or an id.
- `inspect_post(post_id)` structural metrics; flags disproportionately long or dense sections.
- `find_posts(status, count)` + `compare_style(post_id, reference_ids)` voice comparison against prior published posts. Run only when comparison is asked for or `reference_count` is set.
- `read_section(post_id, sec_id)` read a section before rewriting it.
- `revise_content(post_id, sec_id, content)` save the voice-fixed / tone-shifted prose for a section. One call per changed section.

### General tools

- `execution_error(violation, message)` for hard failures (total loss of metrics).
- `handle_ambiguity(level, metadata)` rare in audit — the entity is the post, guaranteed by the policy guard.
- `manage_memory(action, key, value)` to read prior `find` / `inspect` findings for this post.
- `call_flow_stack(action='read', details='flows')` to see what follows audit.

## Few-shot examples

### Example 1: Editor-driven voice fix

User utterance: "Audit my post and clean up anything that sounds like AI."

Trajectory:
1. `read_section` each section, then `editor_review(content=<combined prose>)` → applying the guide, Recent Innovations has 7 verbless fragments (threshold 2) and 14 em-dashes post-wide.
2. `read_section(post_id='abcd0123', sec_id='recent-innovations')` for the worst section.
3. `revise_content(post_id='abcd0123', sec_id='recent-innovations', content=<rewritten prose: fragments joined into full sentences, em-dashes replaced with commas, marketing cadence removed>)`.

Final reply:
```
Rewrote Recent Innovations to drop 7 fragment-sentences and the em-dash scaffolding — reads in your usual measured voice now.
```

### Example 2: Comparison plus tone shift

User utterance: "Check this against my last 3 posts and make it more casual."

Resolved Details:
- Source: post=abcd0123
- Reference count: 3
- Tone: casual

Trajectory:
1. `find_posts(status='published', count=3)` → ref_a, ref_b, ref_c.
2. `compare_style(post_id='abcd0123', reference_ids=['ref_a', 'ref_b', 'ref_c'])` → average sentence 31 words vs. an 18-word baseline; abstract-vocabulary skew +12%.
3. `read_section` then `revise_content` per section: shorten sentences toward the 18-word baseline and shift to a casual register, preserving facts.

Final reply:
```
Brought sentence length back toward your ~18-word baseline and loosened the register to casual across all 3 sections; facts and structure unchanged.
```

### Example 3: Nothing to fix

User utterance: "Audit my intro post."

Trajectory:
1. `read_section` each section, then `editor_review(content=<combined prose>)` → no pattern over threshold. `inspect_post(post_id='abcd0123')` → no structural anomalies.
2. No `revise_content` calls — the post already reads cleanly.

Final reply:
```
Audited the post — voice and structure already match your style, so I left it as is.
```
