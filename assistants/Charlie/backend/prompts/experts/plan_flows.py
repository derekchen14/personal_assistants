INSTRUCTIONS = (
    'Pick the flow within the Plan intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Plan covers laying out a single post end-to-end '
    '(blueprint), planning a revision sequence (triage), building a content calendar, and '
    'structuring a multi-part series (digest).'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "let's plan out this blog post"
## Output

```json
{"reasoning": "Planning the post creation workflow.", "flow_name": "blueprint", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "plan a revision for my latest draft"
## Output

```json
{"reasoning": "Planning a revision sequence.", "flow_name": "triage", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "create a content calendar for next month"
## Output

```json
{"reasoning": "Planning content schedule.", "flow_name": "calendar", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "plan a 3-part series on investing"
## Output

```json
{"reasoning": "Planning a multi-part series.", "flow_name": "digest", "confidence": 0.90}
```
</positive_example>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Plan': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
