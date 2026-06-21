INSTRUCTIONS = (
    'Pick the flow within the Publish intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Publish covers releasing a post to the primary blog '
    'and cross-posting to secondary channels, scheduling a future release, and adding citations.'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "publish it"
## Output

```json
{"reasoning": "Publishing to the primary blog.", "flow_name": "release", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "schedule it for next Friday at 9am"
## Output

```json
{"reasoning": "Scheduling for later.", "flow_name": "schedule", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "add a citation for that statistic"
## Output

```json
{"reasoning": "Adding a source citation.", "flow_name": "cite", "confidence": 0.88}
```
</positive_example>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Publish': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
