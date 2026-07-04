INSTRUCTIONS = (
    'Pick the flow within the Revise intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Revise covers major rework of an existing draft, '
    'sentence-level editing of specific sections, auditing voice and consistency, and proposing '
    'alternatives to fill placeholder gaps.'
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

User: "edit the second paragraph — tighten the phrasing"
## Output

```json
{"reasoning": "Sentence-level edit within one paragraph.", "flow_name": "write", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "make the tone more professional"
## Output

```json
{"reasoning": "Voice and tone shift across the post.", "flow_name": "audit", "confidence": 0.85}
```
</positive_example>

<positive_example>
## Conversation History

User: "fill in the placeholder in the intro with a couple of options"
## Output

```json
{"reasoning": "Generate alternatives for a placeholder gap.", "flow_name": "propose", "confidence": 0.88}
```
</positive_example>

<edge_case>
## Conversation History

User: "The middle three sections keep restating the same idea. Reorganize them so the argument builds instead of repeating."
## Output

```json
{"reasoning": "Restructuring the argument across several sections is post-level rework, not a single-section edit.", "flow_name": "rework", "confidence": 0.82}
```
</edge_case>

<edge_case>
## Conversation History

User: "The opening of the pricing section reads flat. Rework just those couple of sentences so the hook lands harder."
## Output

```json
{"reasoning": "Despite the word rework, the scope is a few sentences inside one section, so this is a sentence-level edit.", "flow_name": "write", "confidence": 0.80}
```
</edge_case>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Revise': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
