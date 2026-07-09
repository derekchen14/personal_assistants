INSTRUCTIONS = (
    'Pick the flow within the Publish intent set (and its edge flows into adjacent intents) that '
    'most specifically matches the user\'s goal. Publish covers releasing a post to the primary blog '
    'and cross-posting to secondary channels, scheduling a future release, and adding citations.'
)

RULES = ''

EXAMPLES = '''<positive_example>
## Conversation History

User: "publish it"
## Output

```json
{"reasoning": "Publishing to the primary blog.", "flow_name": "release"}
```
</positive_example>

<positive_example>
## Conversation History

User: "schedule it for next Friday at 9am"
## Output

```json
{"reasoning": "Scheduling for later.", "flow_name": "schedule"}
```
</positive_example>

<positive_example>
## Conversation History

User: "add a citation for that statistic"
## Output

```json
{"reasoning": "Adding a source citation.", "flow_name": "cite"}
```
</positive_example>

<edge_case>
## Conversation History

User: "get it ready to go live, but hold it until Monday morning"
## Output

```json
{"reasoning": "A release timed for the future rather than immediately.", "flow_name": "schedule"}
```
</edge_case>

<edge_case>
## Conversation History

User: "the stats in the second section need sources before this goes out"
## Output

```json
{"reasoning": "Adding citations is the blocking step, even though publishing is the eventual goal.", "flow_name": "cite"}
```
</edge_case>

<edge_case>
## Conversation History

User: "once it's up, also push it out to the newsletter and LinkedIn"
## Output

```json
{"reasoning": "Cross-posting to secondary channels is part of releasing the post.", "flow_name": "release"}
```
</edge_case>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Publish': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
