# Trace — draft_create

APPROVED: [ ]

Clean single-flow **Draft** turn: create a new post from a topic. Expected shape: detect_and_fill, stack + fill the create flow via write_state, activate_flow(create) with a completion record, then a direct reply.

Recorded 2026-06-12 on the NEW orchestrator path (session `trace_user_20260612_081715`).

## Turn 1 — user (utterance)

> Create a new post about Evaluating RAG Pipelines in Production

Tool calls:
 1. `detect_and_fill(text="Create a new post about Evaluating RAG Pipelines in Production", intent="Draft")` — ok
 2. `write_state(op="stackon", flow_name="create")` — ok
 3. `write_state(op="update_flow", fields={"slots": {"title": "Evaluating RAG Pipelines in Production", "type": "draft"}})` — ok
 4. `activate_flow(flow_name="create")` — ok

Dispatched flows: create

Completion record — **create**: Created draft "Evaluating RAG Pipelines in Production".
  (metadata keys: ['post_id', 'status'])

Final utterance:

> Your new draft "Evaluating RAG Pipelines in Production" is ready, as shown on the right. Would you like to start with an outline, or jump straight into drafting content?

