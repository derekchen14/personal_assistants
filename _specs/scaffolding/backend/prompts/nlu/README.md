# NLU Slot-Filling Prompts

One module per intent: `<intent>_slots.py`. Each module defines the
slot-filling prompt block for the flows in that intent.

## `rules` block — one numbered step per slot, priority order

```
1. <Imperative for required slot 1.> <Default behavior, anchor cases.>
   a. <Sub-rule for nuance, only when needed.>
2. <Imperative for required slot 2.> ...

3. Exactly one of <electives> must fill (or all stay null when <bare-request>).
   a. `<elective 1>` fires when <trigger>.
   b. `<elective 2>` fires when <trigger>.

4. <Imperative for optional slot 1.>
5. <Imperative for optional slot 2.>

6. Treat <slot-class> directives as current-turn-only. Prior-turn directives
   are assumed already applied — do NOT carry them into the current slot fill
   unless the current turn explicitly references them via co-reference
   ('yes', 'do option 2', 'all three'). `source` is the exception: it carries
   forward from `state.active_post`.
```

- **`rules` style.** Verb-first imperatives that tell the LLM what to *do*
  with the slot. Anti-pattern: noun-first descriptions (`source: <description>`)
  — those duplicate the `slots` block.
- **`slots` block discipline.** Descriptions live there. Block reduces to slot
  name + priority label + 1-2 lines naming the slot type and what it stores.
  No when-it-fires logic, no fill semantics — those belong in `rules`.
- **Multi-turn / current-turn rule.** Most agentic flows benefit from the
  cross-slot rule above (item 6 in the skeleton) to protect against the LLM
  re-firing prior-turn directives that the agent has already acted on.

When updating a slot definition in `flow_stack/flows.py`, grep
`<intent>_slots.py` for the slot name and confirm the prompt's slot block,
rules, and examples all stay in lockstep.
