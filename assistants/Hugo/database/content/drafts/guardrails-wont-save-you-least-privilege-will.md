---
title: "Guardrails Won't Save You; Least Privilege Will"
tags: [security, guardrails, least privilege, agents, red-teaming, permissions]
---

## Guardrails Are Porous
Prompt-based guardrails ask the model to please not do the bad thing, and models are very good at being talked out of their instructions. Every guardrail is a filter with holes, and attackers only need to find one. Treating a system prompt as a security boundary is wishful thinking, not defense.

## Scoping the Blast Radius
The real question is not whether the agent can be tricked but what happens when it is. If a compromised agent can only read one folder and call two harmless tools, the blast radius is small no matter what it is convinced to do. Design for the assumption that the model will eventually be manipulated, and make that outcome boring.

## Least Privilege in Practice
Give each agent the narrowest set of tools and data it needs for its actual job, and nothing else. A drafting agent does not need delete permissions, and a research agent does not need write access to production. Scope credentials per task, expire them fast, and default to denying anything you did not explicitly grant.

## Auditing Tool Access
Review what every agent can actually reach, not what you assume it can reach, because permissions drift as features get added. Keep a log of which tools each agent invoked and flag the ones it never uses so you can revoke them. An unused permission is pure risk with no upside, so cut it.