INSTRUCTIONS = (
    'Pick the flow within the Draft intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Draft covers brainstorming topic ideas, generating '
    'outlines, composing prose from an outline, and refining an in-progress outline or its sections.'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "brainstorm ideas for a tech blog"
## Output

```json
{"reasoning": "Brainstorming topic ideas.", "flow_name": "brainstorm", "confidence": 0.95}
```
</positive_example>

<positive_example>
## Conversation History

User: "create an outline for a post about remote work"
## Output

```json
{"reasoning": "Generating an outline.", "flow_name": "outline", "confidence": 0.95}
```
</positive_example>

<positive_example>
## Conversation History

User: "turn this outline into a full draft"
## Output

```json
{"reasoning": "Composing prose from the outline.", "flow_name": "compose", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "reorder the sections and tweak the headings"
## Output

```json
{"reasoning": "Refining the outline structure.", "flow_name": "refine", "confidence": 0.90}
```
</positive_example>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Draft': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
