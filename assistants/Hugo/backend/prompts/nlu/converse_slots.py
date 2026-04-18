PROMPTS = {
    'explain': {
        'instructions': 'Hugo explains what it did or plans to do — transparency into the writing process and recent actions.',
        'rules': '''- turn_id (elective): A specific turn number to explain. "3 turns ago" → 3, "what you just did" → 1.
- source (elective): A post or section the user is asking about. Helps narrow which action to explain.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Why did you restructure the introduction like that?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "turn_id": null,
    "source": {
      "sec": "introduction"
    }
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "What did you do 3 turns ago?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "turn_id": 3,
    "source": null
  }
}
```
</positive_example>''',
    },
    'preference': {
        'instructions': 'Set a persistent writing preference stored in long-term memory — tone defaults, post length, heading style, Oxford comma, channel defaults.',
        'rules': '''- setting (required): A dict with "key" (preference name) and "value" (preference value). Parse the user's statement into a key-value pair: "use Oxford comma" → {"key": "oxford_comma", "value": true}, "default length 1500 words" → {"key": "default_length", "value": 1500}.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "I always want to use the Oxford comma"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "setting": {
      "key": "oxford_comma",
      "value": true
    }
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Set my default post length to 1500 words"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "setting": {
      "key": "default_length",
      "value": 1500
    }
  }
}
```
</positive_example>''',
    },
    'undo': {
        'instructions': 'Reverse a recent writing action — roll back an edit, addition, deletion, or formatting change.',
        'rules': '''- turn (elective): How many actions back to undo. "Last edit" or "undo that" → 1. Extract only if the user indicates a number.
- action (elective): Which type of action to undo. Use the user's description: "tone change", "edit", "deletion".''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Undo that last edit"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "turn": 1,
    "action": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Revert the tone change you just made"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "turn": null,
    "action": "tone change"
  }
}
```
</positive_example>''',
    },
    'endorse': {
        'instructions': '''Accept Hugo's proactive suggestion and trigger the corresponding action.''',
        'rules': '- action (required): Which suggestion to accept. Extract what the user is confirming, often from context: "yes, go ahead with the outline" → "outline", "sure, publish to Medium" → "publish to Medium".',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Yes, go ahead with that outline"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "action": "outline"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Sure, publish it to Medium like you suggested"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "action": "publish to Medium"
  }
}
```
</positive_example>''',
    },
}
