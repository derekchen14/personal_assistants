INSTRUCTIONS = (
    'Pick the flow within the Publish intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Publish covers releasing a post to the primary '
    'channel, syndicating across secondary channels, scheduling for future release, previewing the '
    'published format, promoting, and cancelling scheduled publication.'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "publish it"
## Output

```json
{"reasoning": "Publishing to primary blog.", "flow_name": "release", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "post it on Twitter too"
## Output

```json
{"reasoning": "Cross-posting to a channel.", "flow_name": "syndicate", "confidence": 0.90}
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

User: "let me preview how it will look"
## Output

```json
{"reasoning": "Previewing published format.", "flow_name": "preview", "confidence": 0.85}
```
</positive_example>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Publish': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
