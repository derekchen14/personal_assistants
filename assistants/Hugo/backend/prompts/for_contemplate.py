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
Failed flow: search (low confidence)
User: "what posts do I have?"
Candidates: check, search, chat
_Output_
```json
{{"thought": "User wants to see existing drafts, not search for specific content.", "flow_name": "check", "confidence": 0.85}}
```
---
Failed flow: outline (missing required slots)
User: "yes"
History: Agent asked "What topic should the outline cover?"
Candidates: outline, chat, feedback
_Output_
```json
{{"thought": "User is continuing the outline flow but 'yes' alone doesn't provide the topic. Route to chat for clarification.", "flow_name": "chat", "confidence": 0.70}}
```
---
Failed flow: write (ambiguous target)
User: "that one looks good"
History: Agent showed multiple outline options
Candidates: select, write, feedback
_Output_
```json
{{"thought": "User is selecting from shown options. Select is the best fit.", "flow_name": "select", "confidence": 0.80}}
```
---
Failed flow: explain (tool error)
User: "tell me about content calendars"
Candidates: search, explain, chat
_Output_
```json
{{"thought": "Explain failed due to tool error. Try search to find related posts.", "flow_name": "search", "confidence": 0.75}}
```
---
Failed flow: check (empty result)
User: "what have I been working on?"
Candidates: search, check, chat
_Output_
```json
{{"thought": "Check returned empty — try search for a broader look at past work.", "flow_name": "search", "confidence": 0.80}}
```
---
Failed flow: brainstorm (low confidence)
User: "give me some ideas for my next post"
History: User was just reviewing a draft
Candidates: brainstorm, next, chat
_Output_
```json
{{"thought": "User is asking for new topic ideas — brainstorm is correct.", "flow_name": "brainstorm", "confidence": 0.85}}
```
---
Failed flow: rework (no prior draft)
User: "revise the introduction"
Candidates: write, rework, chat
_Output_
```json
{{"thought": "No prior draft to rework. Route to write to create content first.", "flow_name": "write", "confidence": 0.75}}
```
---
Failed flow: release (prerequisites not met)
User: "publish everything"
Candidates: preview, release, survey
_Output_
```json
{{"thought": "Release failed on prerequisites. Route to preview so user can see what's ready.", "flow_name": "preview", "confidence": 0.75}}
```
---
Failed flow: next
User: "hmm"
History: Agent just gave a next step suggestion
Candidates: chat, feedback
_Output_
```json
{{"thought": "Short ambiguous response after a suggestion. Treat as general chat.", "flow_name": "chat", "confidence": 0.70}}
```
---
Failed flow: tone (missing post reference)
User: "make it more casual"
History: User was just reviewing an outline
Candidates: tone, polish, chat
_Output_
```json
{{"thought": "User wants tone adjustment — tone is correct but needs a post reference.", "flow_name": "tone", "confidence": 0.80}}
```
---
Failed flow: schedule (no post selected)
User: "schedule it for tomorrow"
Candidates: schedule, preview, chat
_Output_
```json
{{"thought": "No post selected to schedule. Route to preview to pick one first.", "flow_name": "preview", "confidence": 0.75}}
```
---
Failed flow: chat (tool error)
User: "how should I structure a listicle?"
Candidates: explain, outline, chat
_Output_
```json
{{"thought": "User wants content structure advice — explain is the right flow.", "flow_name": "explain", "confidence": 0.85}}
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
