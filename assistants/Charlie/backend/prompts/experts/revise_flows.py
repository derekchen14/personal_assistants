INSTRUCTIONS = (
    'Pick the flow within the Revise intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Revise covers major rework of an existing draft, '
    'polishing specific sections, adjusting tone or voice, auditing consistency, simplifying or '
    'tidying structure, removing content, and accepting/rejecting proposed changes.'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "revise the whole post — it needs work"
## Output

```json
{"reasoning": "Major revision needed.", "flow_name": "rework", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "polish the second paragraph"
## Output

```json
{"reasoning": "Polishing a specific section.", "flow_name": "polish", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "make the tone more professional"
## Output

```json
{"reasoning": "Adjusting post tone.", "flow_name": "tone", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "looks good, accept the changes"
## Output

```json
{"reasoning": "Accepting a revision.", "flow_name": "accept", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "format it for publication"
## Output

```json
{"reasoning": "Formatting for publish.", "flow_name": "format", "confidence": 0.90}
```
</positive_example>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Revise': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
