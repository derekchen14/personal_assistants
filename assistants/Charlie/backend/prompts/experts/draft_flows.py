INSTRUCTIONS = (
    'Pick the flow within the Draft intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Draft covers brainstorming topic ideas, generating '
    'outlines, creating new posts, writing or expanding sections, adding structured elements, '
    'citing sources, and refining in-progress drafts.'
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

User: "start a new post called 10 Tips for Better Sleep"
## Output

```json
{"reasoning": "Creating a new post.", "flow_name": "create", "confidence": 0.95}
```
</positive_example>

<positive_example>
## Conversation History

User: "expand the introduction section"
## Output

```json
{"reasoning": "Expanding content from outline.", "flow_name": "expand", "confidence": 0.85}
```
</positive_example>

<positive_example>
## Conversation History

User: "write the conclusion"
## Output

```json
{"reasoning": "Writing a specific section.", "flow_name": "write", "confidence": 0.90}
```
</positive_example>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Draft': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
