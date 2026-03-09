CONTEMPLATE_INSTRUCTIONS = (
    'The initial flow detection failed or had low confidence. '
    'Re-evaluate the user utterance with the additional context below.\n\n'
    'Consider:\n'
    '1. The failed flow and why it may have been wrong\n'
    '2. The conversation history for additional context\n'
    '3. The narrowed candidate set (excluding the failed flow)\n'
    '4. Whether the user is correcting, clarifying, or continuing\n\n'
    'Pick the best flow from the candidates, or return "chat" if none fit.'
)

CONTEMPLATE_OUTPUT_SHAPE = (
    '```json\n'
    '{{\n'
    '  "thought": "<reasoning about the re-route>",\n'
    '  "flow_name": "<flow_name>",\n'
    '  "confidence": <0.0-1.0>\n'
    '}}\n'
    '```'
)

CONTEMPLATE_EXEMPLARS = '''
---
Failed flow: query (low confidence)
User: "show me the data"
Candidates: describe, chat
_Output_
```json
{{"thought": "User wants to see the dataset info, not run a query.", "flow_name": "describe", "confidence": 0.85}}
```
---
Failed flow: describe (tool error)
User: "what columns does it have?"
Candidates: describe, chat
_Output_
```json
{{"thought": "Describe failed. Try again — same intent.", "flow_name": "describe", "confidence": 0.75}}
```
---
Failed flow: describe (empty result)
User: "tell me about the price column"
Candidates: describe, lookup
_Output_
```json
{{"thought": "Describe returned empty — maybe column doesn't exist. Try again with dataset context.", "flow_name": "describe", "confidence": 0.75}}
```
---
Failed flow: plot (missing dataset)
User: "chart it"
History: User just ran an aggregation
Candidates: plot, trend, chat
_Output_
```json
{{"thought": "User wants to visualize the previous result.", "flow_name": "plot", "confidence": 0.80}}
```
---
Failed flow: lookup (no term specified)
User: "how many are there?"
Candidates: lookup, describe, query
_Output_
```json
{{"thought": "User wants a count — this is a query, not a lookup.", "flow_name": "query", "confidence": 0.80}}
```
---
Failed flow: retrieve (topic not found)
User: "what's our refund policy?"
Candidates: retrieve, chat, summarize
_Output_
```json
{{"thought": "Reference info not found. Let user know.", "flow_name": "chat", "confidence": 0.70}}
```
---
Failed flow: join (missing right table)
User: "combine them"
History: User loaded sales
Candidates: join, append, merge
_Output_
```json
{{"thought": "Combine is ambiguous — need to know what to combine with.", "flow_name": "chat", "confidence": 0.65}}
```
---
Failed flow: recommend
User: "hmm"
History: Agent suggested a next step
Candidates: chat, query
_Output_
```json
{{"thought": "Ambiguous response after suggestion.", "flow_name": "chat", "confidence": 0.70}}
```
---
Failed flow: compare (missing columns)
User: "how do these relate?"
Candidates: compare, describe, chat
_Output_
```json
{{"thought": "Compare needs two specific columns. Ask for clarification.", "flow_name": "chat", "confidence": 0.70}}
```
---
Failed flow: trend (missing time column)
User: "show the trend"
Candidates: plot, trend, chat
_Output_
```json
{{"thought": "Trend needs a time column. Try general plot instead.", "flow_name": "plot", "confidence": 0.75}}
```
---
Failed flow: chat (tool error)
User: "what's the best way to handle nulls?"
Candidates: summarize, blank, chat
_Output_
```json
{{"thought": "User wants an explanation of a data concept — summarize is a Report flow.", "flow_name": "summarize", "confidence": 0.85}}
```
---
Failed flow: validate (ambiguous scope)
User: "find the bad rows in this column"
Candidates: validate, issue, chat
_Output_
```json
{{"thought": "Diagnosing problems is issue detection, not format validation.", "flow_name": "issue", "confidence": 0.80}}
```
---
Failed flow: issue (missing context)
User: "fix the date formats"
Candidates: issue, format, chat
_Output_
```json
{{"thought": "Fixing formats is formatting, not issue diagnosis.", "flow_name": "format", "confidence": 0.80}}
```
---
Failed flow: format (confused with validate)
User: "make sure status is one of active, inactive, or pending"
Candidates: format, validate, chat
_Output_
```json
{{"thought": "Checking values against allowed options is validate; format fixes the form, validate checks if values are from valid options.", "flow_name": "validate", "confidence": 0.85}}
```
---
Failed flow: validate (confused with format)
User: "fix the phone number formatting"
Candidates: validate, format, chat
_Output_
```json
{{"thought": "Format fixes the form of values; validate checks if values are from valid options. Fixing formatting is format.", "flow_name": "format", "confidence": 0.85}}
```
---
Failed flow: outline (confused with insight)
User: "what patterns can you find in the revenue data?"
Candidates: outline, insight, chat
_Output_
```json
{{"thought": "Outline orchestrates multiple intents from instructions; insight chains Analyze + Report only. Open-ended discovery is insight.", "flow_name": "insight", "confidence": 0.85}}
```
---
Failed flow: insight (confused with outline)
User: "first clean the nulls, then join with products, then chart it"
Candidates: insight, outline, chat
_Output_
```json
{{"thought": "Outline orchestrates multiple intents from instructions; insight chains Analyze + Report only. Explicit multi-step instructions is outline.", "flow_name": "outline", "confidence": 0.85}}
```
---
Failed flow: style (ambiguous target)
User: "make the colors brighter"
Candidates: style, design, chat
_Output_
```json
{{"thought": "Color changes on a chart are design, not table style.", "flow_name": "design", "confidence": 0.80}}
```
---
Failed flow: design (wrong target)
User: "highlight the header row"
Candidates: design, style, chat
_Output_
```json
{{"thought": "Highlighting table elements is style, not chart design.", "flow_name": "style", "confidence": 0.80}}
```
---
Failed flow: segment (confused with compare)
User: "compare revenue across regions"
Candidates: segment, compare, chat
_Output_
```json
{{"thought": "Segment breaks down one metric by dimension; compare puts two metrics side by side. This is a single metric across regions — segment.", "flow_name": "segment", "confidence": 0.80}}
```
---
Failed flow: compare (confused with segment)
User: "break down sales by category"
Candidates: compare, segment, chat
_Output_
```json
{{"thought": "Breaking down a single metric by dimension is segment, not compare.", "flow_name": "segment", "confidence": 0.85}}
```
---
Failed flow: summarize (too open-ended)
User: "tell me more about this"
Candidates: summarize, chat
_Output_
```json
{{"thought": "Vague request without data context — route to chat for clarification.", "flow_name": "chat", "confidence": 0.75}}
```
---
Failed flow: chat (needs data interpretation)
User: "why is revenue dropping in Q3?"
Candidates: summarize, chat
_Output_
```json
{{"thought": "User wants data interpretation — summarize is a Report flow for this.", "flow_name": "summarize", "confidence": 0.85}}
```
---
Failed flow: explain (confused with summarize)
User: "what does this chart show?"
Candidates: explain, summarize, chat
_Output_
```json
{{"thought": "Explain is about the analysis process ('what did you do?'); summarize is about a specific artifact ('what does this chart show?'). This asks about a chart.", "flow_name": "summarize", "confidence": 0.85}}
```
---
Failed flow: summarize (confused with explain)
User: "what did you just do?"
Candidates: summarize, explain, chat
_Output_
```json
{{"thought": "Summarize is grounded to a specific chart or table; explain is about the analysis process. This asks about the agent's recent action.", "flow_name": "explain", "confidence": 0.85}}
```
---
Failed flow: interpolate (confused with fill)
User: "fill in the missing sensor readings based on the trend"
Candidates: interpolate, fill, chat
_Output_
```json
{{"thought": "Interpolate estimates from surrounding data; fill uses simple strategies like forward-fill or mean. Trend-based estimation is interpolate.", "flow_name": "interpolate", "confidence": 0.85}}
```
---
Failed flow: fill (confused with interpolate)
User: "just forward-fill the blanks in temperature"
Candidates: fill, interpolate, chat
_Output_
```json
{{"thought": "Fill uses simple strategies like forward-fill or mean; interpolate estimates from surrounding data. Forward-fill is fill.", "flow_name": "fill", "confidence": 0.85}}
```
'''


def build_contemplate_prompt(user_text: str, failed_flow: str,
                             failure_reason: str, candidates: str,
                             history_text: str) -> str:
    parts = [
        f'## Failed Flow: {failed_flow}\n'
        f'Reason: {failure_reason}\n',
        f'## Conversation History\n\n{history_text}\n' if history_text else '',
        f'## Candidate Flows\n\n{candidates}\n',
        f'## Instructions\n\n{CONTEMPLATE_INSTRUCTIONS}\n',
        f'## Output Format\n\n{CONTEMPLATE_OUTPUT_SHAPE}\n',
        f'## Examples\n{CONTEMPLATE_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ]
    return '\n'.join(p for p in parts if p)
