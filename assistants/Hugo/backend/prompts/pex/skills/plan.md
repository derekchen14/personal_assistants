# Workflow Planner

How to handle a Plan turn — a request that spans several steps. This is guidance, not a flow: you
issue the stack operations yourself.

1. Read belief (`understand` op="read"). Belief carries NLU's detection for this turn.
2. Break the request into sub-tasks. Map each sub-task to a flow in the EXISTING ontology — never
   invent a flow name. If no existing flow fits a sub-task, drop it or ask the user.
3. Order the flows by dependency (e.g. outline before write, write before release). Keep the plan
   minimal — the fewest flows that reach the goal.
4. Share a one-line plan with the user so they know the shape of the work.
5. Stack on ALL the flows AT ONCE, in reverse execution order: push the LAST flow first and the
   FIRST flow last, so the first sits on top. Every queued push is `manage_flows` op="stackon"
   with `active: false`; the final push (the flow to run now) is a plain stackon — `active`
   defaults to true, so it runs immediately. The stack now holds the whole plan — it is
   observable by every agent and survives even if you lose track of the plan later.
6. After each flow completes, `manage_flows` op="pop" removes Completed and Invalid flows all at
   once AND runs the Pending flow it surfaces. Judge whether the user's goal is met from each
   result; when it is, stop and report what was accomplished.
