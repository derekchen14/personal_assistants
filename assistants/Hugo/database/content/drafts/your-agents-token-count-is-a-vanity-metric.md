---
title: "Your Agent's Token Count Is a Vanity Metric"
tags: [observability, agents, tokens, metrics, monitoring, llm, traces]
---

## Why Token Counts Mislead
Token count tells you how much text moved through the model, not whether the agent did anything useful. A chatty agent that burns 50k tokens and solves the problem is worth more than a terse one that spends 5k and fails. Optimizing for fewer tokens quietly pushes you toward agents that do less, which is exactly backwards.

## What to Measure Instead
Measure outcomes, not volume. Did the task get done, did it get done correctly, and did the user have to intervene. Those are the numbers that predict whether anyone keeps using your agent, and none of them show up in a token dashboard.

## Cost per Resolved Task
The metric that actually matters is dollars per resolved task. Divide your total spend by the number of tasks that reached a correct, accepted outcome, and suddenly a verbose agent that resolves twice as many tasks looks cheap. This framing also lets you compare a big expensive model against a small one honestly, because it prices in the failures.

## Instrumenting the Right Signals
Log task completion, correction rate, and retries alongside your token counts so you can tie cost to outcomes. Tag every trace with whether the task succeeded and whether a human stepped in. Once those signals are in place, token count becomes a diagnostic you glance at, not a goal you chase.