# Skill

Execute a multi-step plan from a numbered list or complex request — orchestrates domain flows across Clean, Transform, Analyze, and Report.

## Behavior

- Parse the user's instructions into discrete steps.
- For each step, identify the appropriate flow and intent.
- Present the execution plan as a numbered list with flow names and descriptions.
- Execute steps sequentially, reporting progress after each.
- If a step fails or needs clarification, pause and ask the user.

## Slots

- `instructions` (required): The multi-step request or numbered task list.
- `dataset` (optional): The primary dataset for the plan.

## Output

A `list` showing the execution plan and results of each step.
