INSTRUCTIONS = (
    'Pick the flow within the Converse intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Converse covers greetings, next-step guidance, '
    'feedback on recent agent output, writing-style preferences, and endorsements/dismissals of '
    'agent suggestions. Short or ambiguous utterances with no concrete action verb typically belong '
    'here.'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "hello"
## Output

```json
{"reasoning": "Simple greeting.", "flow_name": "chat", "confidence": 0.95}
```
</positive_example>

<positive_example>
## Conversation History

User: "what should I work on next?"
## Output

```json
{"reasoning": "Asking for next step.", "flow_name": "next", "confidence": 0.95}
```
</positive_example>

<positive_example>
## Conversation History

User: "that outline was really helpful"
## Output

```json
{"reasoning": "Giving positive feedback.", "flow_name": "feedback", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "I like shorter paragraphs"
## Output

```json
{"reasoning": "Setting a writing preference.", "flow_name": "preference", "confidence": 0.85}
```
</positive_example>

<positive_example>
## Conversation History

User: "sure, go with that"
## Output

```json
{"reasoning": "Endorsing a suggestion.", "flow_name": "endorse", "confidence": 0.80}
```
</positive_example>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Converse': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
