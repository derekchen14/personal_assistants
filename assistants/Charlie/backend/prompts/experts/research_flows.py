INSTRUCTIONS = (
    'Pick the flow within the Research intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Research covers browsing topics and saved ideas, '
    'searching past posts, checking post metadata and channel status, inspecting numeric content '
    'metrics, explaining writing concepts, finding related content, and comparing/diffing posts.'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "show me my current drafts"
## Output

```json
{"reasoning": "Checking draft status.", "flow_name": "check", "confidence": 0.95}
```
</positive_example>

<positive_example>
## Conversation History

User: "search for posts about machine learning"
## Output

```json
{"reasoning": "Searching posts by keyword.", "flow_name": "search", "confidence": 0.95}
```
</positive_example>

<positive_example>
## Conversation History

User: "what channels do I have?"
## Output

```json
{"reasoning": "Viewing configured channels.", "flow_name": "survey", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "browse topic ideas"
## Output

```json
{"reasoning": "Browsing available topics.", "flow_name": "browse", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "how do I write a good hook?"
## Output

```json
{"reasoning": "Asking about a writing concept.", "flow_name": "explain", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "find content related to productivity"
## Output

```json
{"reasoning": "Finding related content.", "flow_name": "find", "confidence": 0.85}
```
</positive_example>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Research': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
