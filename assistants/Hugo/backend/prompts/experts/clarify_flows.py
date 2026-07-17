INSTRUCTIONS = (
    'The working intent is Clarify: the request is underspecified, so the safest move is to ask '
    'the user a question rather than guess. Detect a flow ONLY if one reading is overwhelmingly '
    'more plausible than every alternative. Otherwise ABSTAIN by outputting an empty flows list — '
    'an abstention tells the assistant to ask a clarifying question instead of acting.'
)

RULES = (
    'Abstaining is the expected outcome, not a failure. Commit to a flow only when the utterance '
    'plus history leave essentially no doubt; a merely-likely reading is not enough.'
)

EXAMPLES = '''<positive_example>
## Conversation History

User: "can you do something with the draft"
## Output

```json
{"reasoning": "No signal separates revising, summarizing, or publishing the draft. Nothing close to certain, so abstain.", "flows": []}
```
</positive_example>

<positive_example>
## Conversation History

User: "Can you come up with a few angles for describing the bifurcation process?"
## Output

```json
{"reasoning": "'Come up with a few angles' is unambiguous idea generation even though the intent classifier could not place it. Extreme confidence, so commit.", "flows": ["brainstorm"]}
```
</positive_example>

<edge_case>
## Conversation History

User: "hmm, what about the other one"
## Output

```json
{"reasoning": "'The other one' has no antecedent in the history. No reading is even plausible, so abstain.", "flows": []}
```
</edge_case>'''


PROMPTS: dict[str, dict[str, str]] = {
    'Clarify': {
        'instructions': INSTRUCTIONS,
        'rules': RULES,
        'examples': EXAMPLES,
    }
}
