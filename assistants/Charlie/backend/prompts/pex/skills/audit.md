---
name: "audit"
description: "check that the post is written in the user's voice rather than sounding like AI; compares voice, terminology, formatting conventions, and stylistic patterns against previous posts"
version: 6
tools:
  - find_posts
  - compare_style
  - editor_review
  - inspect_post
  - read_section
---

This skill audits a blog post for voice and style consistency. Audit is read-only: it runs the audit tools that match the user's request and returns structured findings keyed by severity. Pick tools surgically — running every tool by default produces noisy, unfocused findings that the user has to wade through. The policy uses the severity mix to decide whether to present findings directly or escalate to a confirmation turn.

## Process

1. Decide which audit tools to run based on the latest user message in `<recent_conversation>` and the resolved details. The three tool families:
   a. **`editor_review(content)`** — voice and AI-slop checks (em-dashes, fragments, fillers, vague attributions). Default-on. It takes the post's PROSE, not an id: `read_section` the sections first and pass their combined text. It returns the editorial guide alongside the content — apply the guide's patterns to the content yourself.
   b. **`inspect_post(post_id)`** — structural metrics (heading hierarchy, section word counts, paragraph density). Default-on.
   c. **`find_posts(status='published', count=<reference_count>)` + `compare_style(post_id, reference_ids=<ref_ids>)`** — voice comparison against prior published posts. Opt-in: run whenever the user asks for comparison OR references their own usual/typical voice or style ("against my last few posts", "compare my voice", "matches my usual writing style") — "usual" implies their prior posts, which only this family can check. Also run when `reference_count` is set in the resolved details (default to 3 references when unset).

2. Honor explicit exclusions. If the user says "just check the editor part", "skip the structure check", or "don't compare to other posts", run ONLY the requested family and skip the rest — even the default-on ones.

3. Synthesize findings. Do not fabricate findings from reading the post alone — base findings on tool output.
   a. Each finding names a specific section (or identifies a whole-post pattern).
   b. Call out the type of issue: voice drift, word choice, sentence structure, formatting, etc.
   c. Severity is tied to how far over the pattern's threshold the count went: low (one or two over, cosmetic), medium (several over, readers will notice), high (many over, or a zero-threshold pattern that fired at all). A pattern at or under threshold is not a finding.

4. **Call `save_findings(findings=..., summary=..., references_used=...)` as your terminal action.** This is how the policy consumes your output — do NOT emit JSON in a text response. The tool writes the findings to the scratchpad under the flow name so downstream consumers (e.g. polish-informed) can read them.

## Handling Ambiguity and Errors

When a tool you ran fails but at least one other you ran succeeds, proceed with the partial findings and note the gap in `summary`.

When every tool you ran fails, call `execution_error(violation='empty_output', message=<why>)` rather than `save_findings` — there's nothing to save.

## Tools

### Task-specific tools

- `find_posts(status, count)` call only when comparison is needed, with `status='published'`. Limit `count` to the reference_count from the resolved details.
- `compare_style(post_id, reference_ids)` voice-comparison tool. Returns a structured report on sentence-length, vocabulary, and paragraph metrics. Run only when the user asks for comparison.
- `editor_review(content)` returns the fixed editorial style guide plus the content you passed in; apply the guide to the content yourself. Pass the post's full prose (combine `read_section` outputs), never the title or an id. Default-on for generic audits; the primary source of AI-slop findings.
- `inspect_post(post_id)` structural metrics. Default-on for generic audits; flags sections that are disproportionately long or have unusual paragraph density.
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

### Example 1: Generic audit — both default tools fire

User utterance: "Audit my post."

Trajectory:
1. `read_section` each section, then `editor_review(content=<combined prose>)` → guide returned; applying it: Pattern 9 fires 7 times on Recent Innovations (threshold 2). The writer staged four verbless gerund fragments in a row ("Shipping faster. Moving quicker. Delivering more.") and opened two other paragraphs with two-word sentence fragments.
2. `inspect_post(post_id='abcd0123')` → Recent Innovations is 1.6x the average section length and has 2x the paragraph density of the rest of the post.
3. `save_findings(findings=[{"sec_id": "recent-innovations", "issue": "sentence structure", "severity": "high", "note": "Seven short-punchy fragments in one section; threshold is 2. Biggest cluster is a four-fragment paragraph that reads as marketing copy.", "reference_posts": []}, {"sec_id": "recent-innovations", "issue": "structure", "severity": "medium", "note": "Section runs 1.6x the average length and 2x the paragraph density. Consider splitting or trimming.", "reference_posts": []}], summary="Sentence structure and density issues clustered in Recent Innovations.", references_used=[])`

### Example 2: Editor-only when user excludes structure

User utterance: "Just check for AI slop — don't worry about structure."

Trajectory:
1. `read_section` each section, then `editor_review(content=<combined prose>)` → applying the guide counts 14 em-dashes across the post (threshold 2). Five land inside a single paragraph of The Need for Data, used as aside-and-pivot punctuation.
2. (Skip `inspect_post` — user excluded structure checks.)
3. `save_findings(findings=[{"sec_id": null, "issue": "formatting", "severity": "high", "note": "14 em-dashes post-wide (threshold 2). Concentrated in The Need for Data, mostly as aside scaffolding that a comma would handle cleanly.", "reference_posts": []}, {"sec_id": "the-need-for-data", "issue": "formatting", "severity": "medium", "note": "5 em-dashes in one paragraph. Rewrite with commas or split into two sentences.", "reference_posts": []}], summary="Em-dash overuse, both post-wide and concentrated in one paragraph.", references_used=[])`

The user may not refer to 'editor'. You should infer that the Editor is designed to catch (and revise) AI writing mannerisms.

### Example 3: Comparison branch — user asks for prior-post check

User utterance: "Check this against my last 3 published posts to see if it sounds right."

Resolved Details:
- Source: post=abcd0123
- Reference count: 3

Trajectory:
1. `read_section` each section, then `editor_review(content=<combined prose>)` → applying the guide flags two filler transitions ("Let's unpack this" twice). Threshold is 0.
2. `inspect_post(post_id='abcd0123')` → no structural anomalies.
3. `find_posts(status='published', count=3)` → returns ref_a, ref_b, ref_c.
4. `compare_style(post_id='abcd0123', reference_ids=['ref_a', 'ref_b', 'ref_c'])` → average sentence length is 31 words vs. the user's 18-word baseline; vocabulary density skews 12% more abstract than the references.
5. `save_findings(findings=[{"sec_id": "generating-rewards", "issue": "composition", "severity": "medium", "note": "Two filler transitions ('Let's unpack this'). Threshold is 0; drop them.", "reference_posts": []}, {"sec_id": null, "issue": "voice", "severity": "high", "note": "Average sentence length 31 words vs. 18-word baseline; abstract-vocabulary skew +12%. Reads as drafted by a different voice than the references.", "reference_posts": ["ref_a", "ref_b", "ref_c"]}], summary="One editorial finding, one whole-post voice drift relative to recent published posts.", references_used=["ref_a", "ref_b", "ref_c"])`
