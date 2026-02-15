# Skill: explain

Explain an architecture concept from the assistants framework.

## Behavior

- Use `spec_read` to look up relevant specs for the concept
- Explain the concept in plain language, relating it to the user's assistant-building context
- Include how the concept fits into the overall POMDP architecture:
  - 3 Modules: NLU, PEX, RES
  - 7 Components: Dialogue State, Flow Stack, Context Coordinator, Prompt Engineer, Display Frame, Ambiguity Handler, Memory Manager
  - 4 Utilities: Evaluation, Server Setup, Configuration, Visual Primitives
- Give concrete examples when possible

## Slots

- `concept` (required): The architecture concept to explain

## Output

A clear explanation at the appropriate level of detail.
