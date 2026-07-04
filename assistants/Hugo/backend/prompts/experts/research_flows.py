INSTRUCTIONS = (
    'Pick the flow within the Research intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Research covers browsing topics and saved ideas, '
    'finding and listing posts, summarizing a draft\'s content, and comparing posts (including '
    'version-to-version comparisons of a single post).'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "browse topic ideas"
## Output

```json
{"reasoning": "Browsing available topics.", "flow_name": "browse", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "find my posts about machine learning"
## Output

```json
{"reasoning": "Finding and listing posts by keyword.", "flow_name": "find", "confidence": 0.95}
```
</positive_example>

<positive_example>
## Conversation History

User: "give me a quick summary of my remote-work draft"
## Output

```json
{"reasoning": "Summarizing a draft's content.", "flow_name": "summarize", "confidence": 0.90}
```
</positive_example>

<positive_example>
## Conversation History

User: "how do these two posts compare structurally?"
## Output

```json
{"reasoning": "Comparing structure across posts.", "flow_name": "compare", "confidence": 0.90}
```
</positive_example>

<edge_case>
## Conversation History

User: "what actually changed between this draft and yesterday's version?"
## Output

```json
{"reasoning": "A version-to-version comparison of one post, not a plain summary.", "flow_name": "compare", "confidence": 0.84}
```
</edge_case>

<edge_case>
## Conversation History

User: "what have I already got saved on API design patterns?"
## Output

```json
{"reasoning": "Locating existing saved posts by topic, not brainstorming new topics.", "flow_name": "find", "confidence": 0.83}
```
</edge_case>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Research': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
