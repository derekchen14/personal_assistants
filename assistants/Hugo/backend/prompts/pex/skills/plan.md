# Workflow Planner

How to handle a Plan turn — a request that spans several steps. This is guidance, not a flow: you
issue the stack operations yourself.

1. Read belief (`understand` op="read"). Belief carries NLU's detection for this turn.
2. Break the request into operations, map each operation to a flow in the EXISTING ontology, then
   group operations owned by the same flow. Several instructions are not automatically a Plan:
   when one flow already supports all of them, put them in that flow's slots or checklist instead
   of creating several steps. Never invent a flow name. If no existing flow fits, drop it or ask.
3. Keep a Plan only when the goal genuinely needs two or more distinct flows. If NLU supplied a
   Plan whose operations collapse to one flow, choose the canonical flow by the artifact or outcome
   the user requested — never merely because that flow is currently Active or sits on top. Treat
   constraints on that artifact as slots/checklist guidance for the canonical flow. Use the existing
   `manage_flows` operations to mark the Plan marker and every redundant queued flow Invalid, pop
   them safely, then stack the canonical flow. Do not run the redundant decomposition.
4. Order genuine plan flows by dependency (e.g. outline before compose, compose before release). Keep the plan
   minimal — the fewest flows that reach the goal.
5. Share a one-line plan with the user so they know the shape of the work.
6. Stack on ALL the flows AT ONCE, in reverse execution order: push the LAST flow first and the
   FIRST flow last, so the first sits on top. Every queued push is `manage_flows` op="stackon"
   with `active: false`; the final push (the flow to run now) is a plain stackon — `active`
   defaults to true, so it runs immediately. The stack now holds the whole plan — it is
   observable by every agent and survives even if you lose track of the plan later.
7. After each flow completes, `manage_flows` op="pop" removes Completed and Invalid flows all at
   once AND runs the Pending flow it surfaces. Judge whether the user's goal is met from each
   result; when it is, stop and report what was accomplished.

## Examples

- "Move the cost section after the setup, rename the ending, and remove the appendix" is one
  structural-edit flow carrying several checklist items, not a three-step Plan.
- "Give the argument five sections, center it on cynicism, and leave out self-care advice" is one
  outline flow: the requested artifact is an outline, while the framing and exclusion are guidance
  for that outline. Do not choose refine merely because NLU placed it on top.
- "Try three different openings for these three sections" is one flow when its checklist can hold
  all three targets; repeated wording does not create repeated plan steps by itself.
- "Research comparable posts, outline the strongest angle, then compose it" is a real Plan because
  it needs distinct research and drafting flows in dependency order.
- "Check the draft, add its missing source, then release it" is a real Plan because inspection,
  citation, and publication are distinct flows.
