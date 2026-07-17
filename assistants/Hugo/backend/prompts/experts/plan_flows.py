INSTRUCTIONS = (
    'The working intent is Plan: the request spans multiple distinct operations. Decompose it into '
    'an ordered list of flows, one per step, in EXECUTION order — the order the work must happen, '
    'not the order the user mentioned it. Every step must be a flow from the candidate list; plans '
    'usually run 2-5 steps. If the request turns out to be a single operation after all, output '
    'that one flow alone.'
)

RULES = (
    'Steps must be executable in the listed order: research before drafting, drafting before '
    'revising, revising before publishing. Do not pad the plan with steps the user never asked '
    'for, and do not repeat a flow unless the request clearly runs it twice.'
)

EXAMPLES = '''<positive_example>
## Conversation History

User: "Find my three best posts, draft a new one on that theme, then schedule it."
## Output

```json
{"reasoning": "Three distinct operations: locate past posts, outline a new draft from the theme, then set a publication date. Execution order matches the request.", "flows": ["find", "outline", "schedule"]}
```
</positive_example>

<positive_example>
## Conversation History

User: "Rough out a structure for the caching post and give it a pass for voice when the sections are in."
## Output

```json
{"reasoning": "Two operations: build the outline, then check the writing against the user's voice. The voice pass depends on the outline existing.", "flows": ["outline", "audit"]}
```
</positive_example>

<edge_case>
## Conversation History

User: "Let's get the migration guide out the door today."
## Output

```json
{"reasoning": "Despite the plan-like framing, this is one operation: publishing the post. A single flow covers it.", "flows": ["release"]}
```
</edge_case>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Plan': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
