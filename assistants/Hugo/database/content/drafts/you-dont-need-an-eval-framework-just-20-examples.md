---
title: "You Don't Need an Eval Framework, Just 20 Examples"
tags: [evals, evaluation, llm evals, testing, frameworks, agents, examples]
---

## The Framework Trap
Teams reach for an eval framework before they have anything to evaluate, and spend a week wiring up harnesses, adapters, and dashboards. By the time the plumbing works, nobody remembers what question they were trying to answer. The framework becomes the project, and the actual quality of the agent goes unexamined.

## Twenty Examples First
Before any tooling, write down twenty real examples of what the agent should do. Pull them from actual user requests, cover the cases you are scared of, and keep them in a plain file. Twenty concrete examples will teach you more about your agent's failures than any generic benchmark.

## Grading by Hand
Run those twenty through your agent and read every output yourself. Grading by hand is slow on purpose, because it forces you to notice the weird failure modes a pass or fail script would hide. You will find patterns in the first afternoon that no automated metric would have surfaced for weeks.

## When to Add Tooling
Add tooling only when the manual loop actually hurts, usually when your example set grows past a hundred or you need to re-run on every change. At that point you know exactly what to automate because you have been doing it by hand. The framework you build then fits your problem instead of some imagined one.