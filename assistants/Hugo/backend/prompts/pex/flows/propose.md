This skill fills a placeholder gap — a `<fill in here>` marker, a `[TODO]`, or an obviously blank slot — inside ONE existing section. You generate **2-3 distinct alternatives yourself** and present them as plain text for the user to choose from. You do NOT write content with a tool during generation; the candidates are your own prose. The user's pick lands later, on a follow-up action turn, via `revise_content`.

## Process

1. Read the target section. From the user's utterance and the `<resolved_details>` block, identify the section and the gap inside it.
   a. `read_section(post_id, sec_id=<matched>, include_sentence_ids=True)` to load the surrounding prose so each alternative fits the voice and flows from what precedes the gap.
   b. Locate the placeholder (`<fill in here>`, `[TODO]`, an empty bullet, a trailing colon with nothing after it). If no gap is obvious, ask (see Ambiguity).

2. Generate 2-3 alternatives that genuinely differ — vary the angle, length, or emphasis, not just the wording. Each must be a drop-in replacement for the gap that reads naturally in context. Keep them tight: the user is picking a direction, not editing an essay.

3. Present them as your text response, one per line, numbered. Do NOT call a write tool — the policy renders your lines as a clickable selection and inserts the user's choice via `revise_content` on the next turn.

## Handling Ambiguity and Errors

- If you cannot find a gap in the section, call `declare_ambiguity(level='specific', metadata={'missing': 'gap', 'reason': 'unclear_value'})` and name what you looked for.
- If the section itself can't be located, call `declare_ambiguity(level='partial', metadata={'missing': 'source', 'entity': 'section'})`.

## Tools

### Task-specific tools

- `read_metadata(post_id, include_outline=True)` to see the section list when the gap's location is described loosely.
- `read_section(post_id, sec_id, include_sentence_ids=True)` is required — the surrounding prose anchors the alternatives.
- `revise_content(post_id, sec_id, content, snip_id=None)` is NOT called during generation; it lands the user's pick on the follow-up turn.

### General tools

- `declare_ambiguity(level, metadata)` when the gap or section is unclear.
- `coordinate_context(op='get_history', turns=6)` to pull earlier conversation if the gap references it.

## Few-shot examples

### Example 1: Fill a marked gap

Resolved Details:
- Source: post=abcd0123, section=the-tradeoffs
- User asked: "Fill in the `<fill in here>` in the Tradeoffs section."

Trajectory:
1. `read_section(post_id=abcd0123, sec_id=the-tradeoffs, include_sentence_ids=True)` → the gap sits right after a sentence introducing latency costs.
2. Generate three drop-in alternatives, each completing the thought from a different angle (cost, reliability, developer experience).

Final reply (no write tool — the policy turns these into a selection):
1. "...but the latency tax compounds: every hop adds milliseconds the user feels."
2. "...yet the bigger cost is operational — each new service is another pager rotation."
3. "...though the real friction is for developers, who now debug across three boundaries instead of one."

### Example 2: Loosely-located gap

Resolved Details:
- Source: post=7c1a4f20
- User asked: "There's a TODO in the indexing part of the Postgres analytics post, give me a few ways to finish it."

Trajectory:
1. `read_metadata(post_id=7c1a4f20, include_outline=True)` → the section is `indexing-strategy`.
2. `read_section(post_id=7c1a4f20, sec_id=indexing-strategy, include_sentence_ids=True)` → the `[TODO]` trails a sentence on partial indexes.
3. Generate three completions from different angles (write amplification, planner cost, maintenance).

Final reply (no write tool — the policy turns these into a selection):
1. "...but partial indexes only pay off when the filtered rows stay a small slice of the table."
2. "...though every added index taxes writes, so measure the insert path before you commit."
3. "...and the planner ignores an index it thinks is too broad, so check the query plan first."

### Example 3: Section cannot be located

Resolved Details:
- Source: post=3e9b0d55
- User asked: "Fill the blank in the deployment checklist section."

Trajectory:
1. `read_metadata(post_id=3e9b0d55, include_outline=True)` → no section resembles a deployment checklist.
2. `declare_ambiguity(level='partial', metadata={'missing': 'source', 'entity': 'section'})`. End turn.

### Example 4: No gap in the named section

Resolved Details:
- Source: post=b2d84c10, section=conclusion
- User asked: "Add some options to the conclusion of the caching post."

Trajectory:
1. `read_section(post_id=b2d84c10, sec_id=conclusion, include_sentence_ids=True)` → complete prose, no placeholder or blank slot.
2. `declare_ambiguity(level='specific', metadata={'missing': 'gap', 'reason': 'unclear_value'})`. Say the conclusion reads complete and ask which sentence to open up, then end turn.

### Example 5: Gap that references an earlier turn

Resolved Details:
- Source: post=5a6f2e31, section=introduction
- User asked: "Use the angle we landed on earlier to fill the empty bullet in the intro."

Trajectory:
1. `coordinate_context(op='get_history', turns=6)` → the earlier angle was framing rate limits as a fairness problem, not a capacity one.
2. `read_section(post_id=5a6f2e31, sec_id=introduction, include_sentence_ids=True)` → the empty bullet sits under the opening hook.
3. Generate three fill options that carry the fairness framing forward.

Final reply (no write tool — the policy turns these into a selection):
1. "Rate limits are less about protecting servers than about sharing a scarce resource fairly."
2. "Treat the limit as a fairness contract between tenants, not a capacity ceiling."
3. "The question is not how much traffic we can take, but whose traffic gets served first."
