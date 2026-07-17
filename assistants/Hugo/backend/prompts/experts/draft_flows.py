INSTRUCTIONS = (
    'Pick the flow within the Draft intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Draft covers brainstorming topic ideas, generating '
    'outlines, composing prose from an outline, and refining an in-progress outline or its sections.'
)

RULES = (
    '`refine` and `compose` operate on an EXISTING outline or its prose. When the user introduces a '
    'brand-new post — an indefinite reference with nothing outlined yet in the conversation ("a post '
    'about X", "I want to write X", "an X post") — pick `outline`: there is no content to refine or '
    'compose from. `brainstorm` is for topic ideas before any post exists.'
)

EXAMPLES = '''<positive_example>
## Conversation History

User: "brainstorm ideas for a tech blog"
## Output

```json
{"reasoning": "Brainstorming topic ideas.", "flows": ["brainstorm"]}
```
</positive_example>

<positive_example>
## Conversation History

User: "create an outline for a post about remote work"
## Output

```json
{"reasoning": "Generating an outline.", "flows": ["outline"]}
```
</positive_example>

<positive_example>
## Conversation History

User: "turn this outline into a full draft"
## Output

```json
{"reasoning": "Composing prose from the outline.", "flows": ["compose"]}
```
</positive_example>

<positive_example>
## Conversation History

User: "reorder the sections and tweak the headings"
## Output

```json
{"reasoning": "Refining the outline structure.", "flows": ["refine"]}
```
</positive_example>

<edge_case>
## Conversation History

User: "This section is already written out in full paragraphs. Just smooth the transitions between them, don't add anything new."
## Output

```json
{"reasoning": "Editing existing prose at the sentence level is write, the Revise edge flow, not compose which turns an outline into prose.", "flows": ["write"]}
```
</edge_case>

<edge_case>
## Conversation History

User: "the last two sections are still bullet points, turn them into real paragraphs"
## Output

```json
{"reasoning": "Composing prose from outlined sections, multi-section rather than a single-section edit.", "flows": ["compose"]}
```
</edge_case>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Draft': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
