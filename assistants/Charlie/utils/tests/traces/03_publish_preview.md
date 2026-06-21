# Trace — publish_preview

APPROVED: [ ]

Clean single-flow **Publish** turn: preview how a seeded post will render when published. Read-only on the post; no channel writes.

Recorded 2026-06-12 on the NEW orchestrator path (session `trace_user_20260612_081756`).

## Turn 1 — user (utterance)

> Show me a preview of how the webhook service post will look when published.

Tool calls:
 1. `find_posts(query="webhook service")` — ok
 2. `detect_and_fill(text="Show me a preview of how the webhook service post will look when published.", intent="Publish")` — ok
 3. `write_state(op="stackon", flow_name="preview")` — ok
 4. `write_state(op="update_flow", fields={"slots": {"source": [{"post": "webhook service", "sec": "", "snip": "", "chl": "", "ver": false}]}})` — ok
 5. `activate_flow(flow_name="preview")` — ok

Dispatched flows: preview

Completion record — **preview**: **Preview: Field Notes from Building a Webhook Service** (blog format, ~1 min read) ## Motivation Webhooks look triv...
  (metadata keys: ['post_id'])

Final utterance:

> Here's the rendered preview of **Field Notes from Building a Webhook Service**, as shown on the right — it reads cleanly in blog format, but the flow flagged that it's quite brief (under 100 words), so you may want to expand the Design section before hitting publish. Want me to flesh that section out, or go ahead and release it as-is?

