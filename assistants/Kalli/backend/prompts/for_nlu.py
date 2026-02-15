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
Flow: scope
Slots: name (required), task (required), boundaries (optional)
User: "the assistant is called Chef and it helps people cook"
_Output_
```json
{{"slots": {{"name": "Chef", "task": "helps people cook", "boundaries": null}}, "missing": []}}
```
---
Flow: intent
Slots: intent_name (required), description (required), abstract_slot (elective)
User: "add a Search intent"
_Output_
```json
{{"slots": {{"intent_name": "Search", "description": null, "abstract_slot": null}}, "missing": ["description"]}}
```
---
Flow: entity
Slots: entities (required)
User: "the key entities are recipe, ingredient, and meal"
_Output_
```json
{{"slots": {{"entities": "recipe, ingredient, meal"}}, "missing": []}}
```
---
Flow: persona
Slots: tone (elective), name (required), response_style (elective), colors (optional)
User: "make it professional"
_Output_
```json
{{"slots": {{"tone": "professional", "name": null, "response_style": null, "colors": null}}, "missing": ["name"]}}
```
---
Flow: lookup
Slots: spec_name (required), section (optional)
User: "show me the Memory Manager spec, specifically the promotion triggers"
_Output_
```json
{{"slots": {{"spec_name": "memory_manager", "section": "Promotion Triggers"}}, "missing": []}}
```
---
Flow: explain
Slots: concept (required)
User: "how does the keep_going loop work?"
_Output_
```json
{{"slots": {{"concept": "keep_going loop"}}, "missing": []}}
```
---
Flow: approve
Slots: flow_name (required)
User: "looks good, approve it"
History: Agent just proposed the "read_recipe" flow
_Output_
```json
{{"slots": {{"flow_name": "read_recipe"}}, "missing": []}}
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
