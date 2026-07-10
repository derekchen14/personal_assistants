INSTRUCTIONS = (
    'Pick the flow within the Research intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Research covers finding and listing posts and notes, '
    'inspecting metrics and metadata (word counts, tags, dates, status), summarizing a draft\'s '
    'content, and comparing posts (including version-to-version comparisons of a single post).'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "how many words is my sourdough draft?"
## Output

```json
{"reasoning": "Asking for a metric (word count) of one post.", "flow_name": "inspect"}
```
</positive_example>

<positive_example>
## Conversation History

User: "find my posts about machine learning"
## Output

```json
{"reasoning": "Finding and listing posts by keyword.", "flow_name": "find"}
```
</positive_example>

<positive_example>
## Conversation History

User: "give me a quick summary of my remote-work draft"
## Output

```json
{"reasoning": "Summarizing a draft's content.", "flow_name": "summarize"}
```
</positive_example>

<positive_example>
## Conversation History

User: "how do these two posts compare structurally?"
## Output

```json
{"reasoning": "Comparing structure across posts.", "flow_name": "compare"}
```
</positive_example>

<edge_case>
## Conversation History

User: "what actually changed between this draft and yesterday's version?"
## Output

```json
{"reasoning": "A version-to-version comparison of one post, not a plain summary.", "flow_name": "compare"}
```
</edge_case>

<edge_case>
## Conversation History

User: "what have I already got saved on API design patterns?"
## Output

```json
{"reasoning": "Locating existing saved posts by topic, not brainstorming new topics.", "flow_name": "find"}
```
</edge_case>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Research': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
