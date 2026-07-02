# Trace — research_compare

APPROVED: [ ]

Clean single-flow **Research** turn: compare two seeded posts. The compare flow needs analysis tools outside the read-only allowlist, so the orchestrator MUST dispatch the flow rather than answer from direct lookups. Read-only on the corpus.

Recorded 2026-06-12 on the NEW orchestrator path (session `trace_user_20260612_082556`).

## Turn 1 — user (utterance)

> Compare my hard-won lessons post about shipping evals with the regression testing post. Which one is stronger?

Tool calls:
 1. `detect_and_fill(text="Compare my hard-won lessons post about shipping evals with the regression testing post. Which one is stronger?", intent="Research")` — ok
 2. `find_posts(query="hard-won lessons shipping evals")` — ok
 3. `find_posts(query="regression testing")` — ok
 4. `find_posts(query="evals lessons learned")` — ok
 5. `find_posts(query="shipping evals")` — ok
 6. `find_posts(query="lessons")` — ok
 7. `find_posts(query="hard-won")` — ok
 8. `write_state(op="stackon", flow_name="compare")` — ok
 9. `write_state(op="update_flow", fields={"slots": {"source": [{"post": "TraceFnA", "sec": "", "snip": "", "chl": "", "ver": false}, {"post": "TraceFnB", "sec": "", "snip": "", "chl": "", "ver": false}], "category": "tone"}})` — ok
10. `activate_flow(flow_name="compare")` — ok

Dispatched flows: compare

Completion record — **compare**: The first post uses a punchy, personal tone—comparing development to "gambling" and highlighting team-specific lesson...
  (metadata keys: ['post_ids'])

Note: round budget exhausted — forced wrap-up

Final utterance:

> The comparison is laid out as shown on the right — **Hard-Won Lessons Shipping LLM Evals** is the stronger piece, with a punchy, personal voice that pulls readers in, while the regression testing post is more analytical and technical, which makes it useful but less compelling as a standalone read.

