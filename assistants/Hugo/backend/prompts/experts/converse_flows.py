INSTRUCTIONS = (
    'Pick the flow within the Converse intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Converse covers greetings and open-ended discussion '
    'about writing — general Q&A not tied to a specific post action. Short or ambiguous utterances '
    'with no concrete action verb typically belong here.'
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

User: "what's a good way to think about audience engagement on technical blogs?"
## Output

```json
{"reasoning": "Open-ended question about writing.", "flow_name": "chat", "confidence": 0.90}
```
</positive_example>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Converse': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
