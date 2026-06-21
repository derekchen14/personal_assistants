# Trace — ambiguity_escalation

APPROVED: [ ]

Ambiguity escalation: two similarly-titled posts make the revise request ambiguous (which post?), and the follow-up answer stays ambiguous. The agent should ask via handle_ambiguity on turn 1 and escalate on turn 2 (concrete options, e.g. the two titles) — never dispatch a domain write while the ambiguity is open.

Recorded 2026-06-12 on the NEW orchestrator path (session `trace_user_20260612_083457`).

## Turn 1 — user (utterance)

> Make the intro of my marketplaces post punchier.

Tool calls:
 1. `read_state()` — ok
 2. `find_posts(query="marketplaces")` — ok

Final utterance:

> Two marketplace posts came up — "Migrating Marketplaces to Event Sourcing" and "Migrating Marketplaces to GraphQL." Which one did you have in mind?

## Turn 2 — user (utterance)

> The marketplace migration one, I just told you.

Tool calls: (none — direct reply)

Final utterance:

> Both posts have "marketplace migration" in the title — one is about **Event Sourcing** and the other about **GraphQL**. Which of those two did you mean?

