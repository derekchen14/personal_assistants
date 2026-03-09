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
Flow: query
Slots: dataset (required), query (required)
User: "show me all sales over $5000"
_Output_
```json
{{"slots": {{"dataset": null, "query": "SELECT * WHERE revenue > 5000"}}, "missing": ["dataset"]}}
```
---
Flow: retrieve
Slots: dataset (required), source (optional)
User: "load the sales dataset"
_Output_
```json
{{"slots": {{"dataset": "sales", "source": "seed"}}, "missing": []}}
```
---
Flow: profile
Slots: dataset (required), column (required)
User: "what are the stats for the revenue column?"
_Output_
```json
{{"slots": {{"dataset": null, "column": "revenue"}}, "missing": ["dataset"]}}
```
---
Flow: filter
Slots: dataset (required), condition (required)
User: "filter rows where region is North"
_Output_
```json
{{"slots": {{"dataset": null, "condition": "region == 'North'"}}, "missing": ["dataset"]}}
```
---
Flow: plot
Slots: dataset (required), chart_type (elective)
User: "make a bar chart of revenue by product"
_Output_
```json
{{"slots": {{"dataset": null, "chart_type": "bar"}}, "missing": ["dataset"]}}
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
