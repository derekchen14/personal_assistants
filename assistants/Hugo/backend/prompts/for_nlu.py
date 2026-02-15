SLOT_FILLING_INSTRUCTIONS = (
    'Extract slot values from the user utterance and conversation context.\n\n'
    'For each slot in the flow schema:\n'
    '1. Check if the value is explicitly stated in the current utterance\n'
    '2. Check if it can be inferred from recent conversation history\n'
    '3. Mark as null if not found\n\n'
    'Only extract values you are confident about. Do not guess or fabricate.'
)

SLOT_FILLING_OUTPUT_SHAPE = (
    '```json\n'
    '{{\n'
    '  "slots": {{"<slot_name>": "<value_or_null>", ...}},\n'
    '  "missing": ["<slot_names_still_needed>"]\n'
    '}}\n'
    '```'
)

SLOT_FILLING_EXEMPLARS = '''
---
Flow: search
Slots: query (required), count (optional)
User: "find my posts about machine learning"
_Output_
```json
{{"slots": {{"query": "machine learning", "count": null}}, "missing": []}}
```
---
Flow: create
Slots: title (required), topic (optional)
User: "start a new post called Getting Started with Python"
_Output_
```json
{{"slots": {{"title": "Getting Started with Python", "topic": null}}, "missing": []}}
```
---
Flow: rework
Slots: post_id (required), section (optional)
User: "revise the introduction of my latest post"
_Output_
```json
{{"slots": {{"post_id": null, "section": "introduction"}}, "missing": ["post_id"]}}
```
---
Flow: schedule
Slots: post_id (required), platform (required), datetime (required)
User: "schedule the post for tomorrow on Medium"
_Output_
```json
{{"slots": {{"post_id": null, "platform": "Medium", "datetime": "tomorrow"}}, "missing": ["post_id"]}}
```
---
Flow: tone
Slots: tone (elective), post_id (required)
User: "make it more casual and friendly"
_Output_
```json
{{"slots": {{"tone": "casual and friendly", "post_id": null}}, "missing": ["post_id"]}}
```
'''


def build_slot_filling_prompt(user_text: str, flow_name: str,
                              slot_schema: str, history_text: str) -> str:
    parts = [
        f'## Flow: {flow_name}\n',
        f'## Slot Schema\n\n{slot_schema}\n',
        f'## Conversation History\n\n{history_text}\n' if history_text else '',
        f'## Instructions\n\n{SLOT_FILLING_INSTRUCTIONS}\n',
        f'## Output Format\n\n{SLOT_FILLING_OUTPUT_SHAPE}\n',
        f'## Examples\n{SLOT_FILLING_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ]
    return '\n'.join(p for p in parts if p)
