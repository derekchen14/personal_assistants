INSTRUCTIONS = {

'explain': (
    'Goal: Hugo explains what it did or plans to do — '
    'transparency into the writing process and recent actions.\n\n'
    'Slots:\n'
    '- turn_id (elective): A specific turn number to explain. '
    '"3 turns ago" → 3, "what you just did" → 1.\n'
    '- source (elective): A post or section the user is asking about. '
    'Helps narrow which action to explain.'
),

'preference': (
    'Goal: Set a persistent writing preference stored in long-term memory — '
    'tone defaults, post length, heading style, Oxford comma, channel defaults.\n\n'
    'Slots:\n'
    '- setting (required): A dict with "key" (preference name) and "value" '
    '(preference value). Parse the user\'s statement into a key-value pair: '
    '"use Oxford comma" → {{"key": "oxford_comma", "value": true}}, '
    '"default length 1500 words" → {{"key": "default_length", "value": 1500}}.'
),

'undo': (
    'Goal: Reverse a recent writing action — roll back an edit, addition, '
    'deletion, or formatting change.\n\n'
    'Slots:\n'
    '- turn (elective): How many actions back to undo. '
    '"Last edit" or "undo that" → 1. Extract only if the user indicates a number.\n'
    '- action (elective): Which type of action to undo. '
    'Use the user\'s description: "tone change", "edit", "deletion".'
),

'endorse': (
    'Goal: Accept Hugo\'s proactive suggestion and trigger the corresponding action.\n\n'
    'Slots:\n'
    '- action (required): Which suggestion to accept. '
    'Extract what the user is confirming, often from context: '
    '"yes, go ahead with the outline" → "outline", '
    '"sure, publish to Medium" → "publish to Medium".'
),

}


EXEMPLARS = {

'explain': '''
---
Flow: explain
Slots: turn_id (PositionSlot, elective), source (SourceSlot, elective)
User: "Why did you restructure the introduction like that?"
_Output_
```json
{{"slots": {{"turn_id": null, "source": {{"sec": "introduction"}}}}, "missing": []}}
```
---
Flow: explain
Slots: turn_id (PositionSlot, elective), source (SourceSlot, elective)
User: "What did you do 3 turns ago?"
_Output_
```json
{{"slots": {{"turn_id": 3, "source": null}}, "missing": []}}
```
''',

'preference': '''
---
Flow: preference
Slots: setting (DictionarySlot, required)
User: "I always want to use the Oxford comma"
_Output_
```json
{{"slots": {{"setting": {{"key": "oxford_comma", "value": true}}}}, "missing": []}}
```
---
Flow: preference
Slots: setting (DictionarySlot, required)
User: "Set my default post length to 1500 words"
_Output_
```json
{{"slots": {{"setting": {{"key": "default_length", "value": 1500}}}}, "missing": []}}
```
''',

'undo': '''
---
Flow: undo
Slots: turn (LevelSlot, elective), action (ExactSlot, elective)
User: "Undo that last edit"
_Output_
```json
{{"slots": {{"turn": 1, "action": null}}, "missing": []}}
```
---
Flow: undo
Slots: turn (LevelSlot, elective), action (ExactSlot, elective)
User: "Revert the tone change you just made"
_Output_
```json
{{"slots": {{"turn": null, "action": "tone change"}}, "missing": []}}
```
''',

'endorse': '''
---
Flow: endorse
Slots: action (ExactSlot, required)
User: "Yes, go ahead with that outline"
_Output_
```json
{{"slots": {{"action": "outline"}}, "missing": []}}
```
---
Flow: endorse
Slots: action (ExactSlot, required)
User: "Sure, publish it to Medium like you suggested"
_Output_
```json
{{"slots": {{"action": "publish to Medium"}}, "missing": []}}
```
''',

}
