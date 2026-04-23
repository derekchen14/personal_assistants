---
name: "audit"
description: "check that the post is written in the user's voice rather than sounding like AI; compares voice, terminology, formatting conventions, and stylistic patterns against previous posts"
version: 4
tools:
  - find_posts
  - compare_style
  - editor_review
  - inspect_post
  - read_section
---

This skill audits a blog post for voice and style consistency against the user's prior published writing. Audit is read-only: it compares the target post to a few reference posts, runs editorial-style checks, and returns structured findings keyed by severity. The policy uses the severity mix to decide whether to present findings directly or escalate to a confirmation turn.

## Process

1. Call `editor_review(post_id)` to run editorial-style-guide checks (catch common signs of AI slop).
   a. Run regardless of reference availability because the rules are absolute.
   b. This is your primary source of data for chances to improve the post.

2. Gather metrics using `inspect_post(post_id)`.
   a. This returns structural metrics such as heading hierarchy, section word counts, paragraph density.
   b. Use this to flag sections that read as structurally off compared to the rest of the post.

3. Optionally compare against other posts if the reference count is filled, or if the user requested an audit with comparisons.
   a. Start with `find_posts(status='published', count=<reference_count>)` to locate reference posts. If the user has requested references but did not state how many, default to searching for up to 5.
   b. Only published posts count as reference material; drafts and notes do not represent the user's established voice.
   c. `compare_style(post_id, references=<ref_ids>)` compares sentence-length distribution, vocabulary density, and paragraph rhythm against the references.

4. Synthesize findings. Do not fabricate findings from reading the post alone — base findings on tool output.
   a. Each finding names a specific section (or identifies a whole-post pattern).
   b. Call out the type of issue: voice drift, word choice, sentence structure, formatting, etc.
   c. Severity is tied to how far over the pattern's threshold the count went: low (one or two over, cosmetic), medium (several over, readers will notice), high (many over, or a zero-threshold pattern that fired at all). A pattern at or under threshold is not a finding.

5. **Call `save_findings(findings=..., summary=..., references_used=...)` as your terminal action.** This is how the policy consumes your output — do NOT emit JSON in a text response. The tool writes the findings to the scratchpad under the flow name so downstream consumers (e.g. polish-informed) can read them.

## Handling Ambiguity and Errors

When `compare_style` fails but `editor_review` succeeds, proceed with editorial findings only and note the gap in `summary`.

When `editor_review` fails but `compare_style` succeeds, mirror the above: report voice findings only and note the gap in `summary`.

When every metric tool fails, call `execution_error(violation='empty_output', message=<why>)` rather than `save_findings` — there's nothing to save.

## Tools

### Task-specific tools

- `find_posts(status, count)` call once, early, with `status='published'`. Limit `count` to the reference_count from the resolved details. References are the comparison baseline; without them, no voice-comparison findings are possible.
- `compare_style(post_id, references)` the primary voice-comparison tool. Returns a structured report on sentence-length, vocabulary, and paragraph metrics.
- `editor_review(post_id)` applies the fixed editorial style guide. Run regardless of reference availability.
- `inspect_post(post_id)` structural metrics. Use to flag sections that are disproportionately long or have unusual paragraph density.
- `read_section(post_id, sec_id)` read a section in more detail when a structural or style finding needs grounding in the actual prose.

### General tools

- `save_findings(findings, summary, references_used)` the terminal action for this skill. Always called exactly once on success.
- `execution_error(violation, message)` for hard failures. Audit tolerates partial tool failures; only total loss of metrics triggers this.
- `handle_ambiguity(level, metadata)` rare in audit because the entity is the post and is guaranteed by the policy guard.
- `call_flow_stack(action='read', details='flows')` to see what flow follows audit. When polish-informed or rework is queued, tag findings with explicit section references so the consumer can filter.

## Output

Your terminal action is a `save_findings(...)` tool call with this shape (the `findings` list may be empty if nothing fired):

```
save_findings(
  findings=[
    {
      "sec_id": "<section id or null for whole-post>",
      "issue": "composition" | "word choice" | "formatting" | "sentence structure" | ...,
      "severity": "low" | "medium" | "high",
      "note": "<one sentence>",
      "reference_posts": ["<ref_post_id>", ...]
    },
    ...
  ],
  summary="<short text>",
  references_used=["<ref_id>", ...],
)
```

After `save_findings` returns, your text response is the summary one-liner — e.g. *"Saved 3 findings: 1 high-severity fragment issue, 2 medium-severity composition notes."* Keep it short; the card rendered by the policy carries the structured detail.

## Few-shot examples

### Example 1: Short punchy fragments

Trajectory:
1. `editor_review(post_id='abcd0123')` → Pattern 9 fires 7 times on Recent Innovations (threshold 2). The writer staged four verbless gerund fragments in a row ("Shipping faster. Moving quicker. Delivering more.") and opened two other paragraphs with two-word sentence fragments.
2. `save_findings(findings=[{"sec_id": "recent-innovations", "issue": "sentence structure", "severity": "high", "note": "Seven short-punchy fragments in one section; threshold is 2. Biggest cluster is a four-fragment paragraph that reads as marketing copy.", "reference_posts": []}], summary="High-severity sentence-structure issue in Recent Innovations: fragment stacking.", references_used=[])`

### Example 2: Em-dash addiction

Trajectory:
1. `editor_review(post_id='abcd0123')` → counts 14 em-dashes across the post (threshold 2). Five land inside a single paragraph of The Need for Data, used as aside-and-pivot punctuation.
2. `save_findings(findings=[{"sec_id": null, "issue": "formatting", "severity": "high", "note": "14 em-dashes post-wide (threshold 2). Concentrated in The Need for Data, mostly as aside scaffolding that a comma would handle cleanly.", "reference_posts": []}, {"sec_id": "the-need-for-data", "issue": "formatting", "severity": "medium", "note": "5 em-dashes in one paragraph. Rewrite with commas or split into two sentences.", "reference_posts": []}], summary="Two formatting issues tied to em-dash overuse. The whole-post count is the primary hit; the single-paragraph cluster is the concrete fix.", references_used=[])`

### Example 3: Filler sentences and vague attributions (both zero-threshold)

Trajectory:
1. `editor_review(post_id='abcd0123')` → flags three filler sentences ("Let's unpack this" twice, "Here's the thing" once) and two vague attributions ("industry reports suggest", "experts argue"). Both thresholds are 0 so every occurrence is a violation.
2. `save_findings(findings=[{"sec_id": "generating-rewards", "issue": "composition", "severity": "medium", "note": "Three filler transitions: 'Let's unpack this' twice, 'Here's the thing' once. Threshold is 0; drop them.", "reference_posts": []}, {"sec_id": "architectures-of-the-past", "issue": "word choice", "severity": "medium", "note": "Two vague attributions: 'industry reports suggest' and 'experts argue'. Threshold is 0. Name the source or delete the attribution.", "reference_posts": []}], summary="Generating Rewards has filler, Architectures of the Past has vague attributions.", references_used=[])`
