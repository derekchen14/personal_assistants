# Skill: onboard

Create a full onboarding plan for building a new assistant.

## Behavior

- This is a Plan-intent flow that creates a sequence of sub-flows
- Present the standard onboarding pipeline:
  1. **Scope** — Define name, task, boundaries
  2. **Intents** — Define 4 domain-specific intents
  3. **Entities** — Identify 3 key domain entities
  4. **Persona** — Set tone, style, guardrails
  5. **Propose** — Generate and review 16 core dacts
  6. **Compose** — Generate and review ~48 flows
  7. **Generate** — Export ontology.py and domain YAML
- If a `domain` slot is given, tailor the plan to that domain
- Push edge flows (scope, intent) onto the flow stack for automatic progression

## Slots

- `domain` (optional): Target domain for the assistant

## Output

A numbered list of steps with brief descriptions. The plan becomes the roadmap.
