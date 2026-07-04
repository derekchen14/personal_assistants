# Workflow Planner

How to handle a Plan turn — a request that spans several steps. This is guidance, not a flow: you
issue the stack operations yourself.

1. Read belief (`read_state`) and the flow catalog. Belief carries NLU's detection for this turn.
2. Break the request into sub-tasks. Map each sub-task to an EXISTING catalog flow — never invent a
   flow name. If no catalog flow fits a sub-task, drop it or ask the user.
3. Order the flows by dependency (e.g. outline before write, write before release). Keep the plan
   minimal — the fewest flows that reach the goal.
4. Share a one-line plan with the user so they know the shape of the work.
5. Stage and run ONE flow at a time: `write_state` op=stackon with `active: true` for the first
   flow, and stage the next only AFTER the current one completes. Do not stack the whole sequence up
   front — one flow is Active at a time.
6. After each flow completes, judge whether the user's goal is met. If not, stage the next flow. If
   it is, stop and report what was accomplished.
