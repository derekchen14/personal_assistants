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
</positive_example>

<positive_example>
## Conversation History

User: "how long should a technical tutorial run before it starts losing people?"
## Output

```json
{"reasoning": "Open-ended question about writing, not tied to a specific post action.", "flow_name": "chat", "confidence": 0.88}
```
</positive_example>

<edge_case>
## Conversation History

User: "Not really sure what to do next with any of this. Where would you even start?"
## Output

```json
{"reasoning": "Vague reflection with no action verb belongs in conversation, not a specific flow.", "flow_name": "chat", "confidence": 0.80}
```
</edge_case>

<edge_case>
## Conversation History

User: "I've got a rough idea about API versioning rattling around. Throw out a few angles I could take."
## Output

```json
{"reasoning": "The casual framing carries a concrete ask for new angles, which is the Draft brainstorm flow.", "flow_name": "brainstorm", "confidence": 0.82}
```
</edge_case>

<edge_case>
## Conversation History

User: "Didn't I write something about container security last year? Pull it up so I can see where I left off."
## Output

```json
{"reasoning": "Locating a past post by topic is the Research find edge flow, not open conversation.", "flow_name": "find", "confidence": 0.82}
```
</edge_case>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Converse': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
