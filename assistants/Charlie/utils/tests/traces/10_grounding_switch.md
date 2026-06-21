# Trace — grounding_switch

APPROVED: [ ]

Grounding switch between two posts: turn 1 inspects post A (grounds it), turn 2 redirects to post B — the grounding block must follow. Watch the second turn's write_state/grounding for the switch.

Recorded 2026-06-12 on the NEW orchestrator path (session `trace_user_20260612_085014`).

## Turn 1 — user (utterance)

> What are the metrics on the embedding model post?

Tool calls:
 1. `find_posts(query="embedding model")` — ok
 2. `detect_and_fill(text="What are the metrics on the embedding model post?", intent="Research")` — ok
 3. `write_state(op="stackon", flow_name="inspect")` — ok
 4. `write_state(op="update_flow", fields={"slots": {"source": [{"post": "embedding model", "sec": "", "snip": "", "chl": "", "ver": false}]}})` — ok
 5. `activate_flow(flow_name="inspect")` — ok

Dispatched flows: inspect

Completion record — **inspect**: Inspected metrics for post TraceSwA.
  (metadata keys: ['metrics', 'post_id'])

Final utterance:

> Here's a quick snapshot of **Choosing an Embedding Model for Search**:
> 
> | Metric | Value |
> |---|---|
> | Word count | 91 |
> | Sections | 3 |
> | Heading depth | 2 |
> | Images | 0 |
> | Links | 0 |
> | Avg. paragraph length | 30.3 words |
> | Estimated read time | ~1 min |
> | Empty sections | None |
> 
> It's a fairly lean draft — no images or links yet, and quite short at 91 words.

## Turn 2 — user (utterance)

> Now check the rate limiting post instead.

Tool calls:
 1. `find_posts(query="rate limiting")` — ok
 2. `detect_and_fill(text="Now check the rate limiting post instead.", intent="Research")` — ok
 3. `write_state(op="stackon", flow_name="inspect")` — ok
 4. `write_state(op="update_flow", fields={"slots": {"source": [{"post": "TraceSwB", "sec": "", "snip": "", "chl": "", "ver": false}]}})` — ok
 5. `activate_flow(flow_name="inspect")` — ok

Dispatched flows: inspect

Completion record — **inspect**: Inspected metrics for post TraceSwB.
  (metadata keys: ['metrics', 'post_id'])

Final utterance:

> Here are the metrics for **A Practical Guide to Rate Limiting**:
> 
> | Metric | Value |
> |---|---|
> | Word count | 88 |
> | Sections | 3 |
> | Heading depth | 2 |
> | Images | 0 |
> | Links | 0 |
> | Avg. paragraph length | 29.3 words |
> | Estimated read time | ~1 min |
> | Empty sections | None |
> 
> Very similar to the embedding model post — both are short drafts with 3 sections, no images or links, and about the same paragraph density.

