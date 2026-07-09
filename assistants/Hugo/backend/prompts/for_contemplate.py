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
    '}}\n'
    '```'
)

CONTEMPLATE_EXEMPLARS = '''
---
Failed flow: find (low confidence)
User: "what posts do I have?"
Candidates: find, browse, chat
_Output_
```json
{{"thought": "User wants to list existing posts — find is correct.", "flow_name": "find"}}
```
---
Failed flow: outline (missing required slots)
User: "yes"
History: Agent asked "What topic should the outline cover?"
Candidates: outline, chat
_Output_
```json
{{"thought": "User is continuing the outline flow but 'yes' alone doesn't provide the topic. Route to chat for clarification.", "flow_name": "chat"}}
```
---
Failed flow: write (ambiguous target)
User: "that one looks good"
History: Agent showed multiple outline options
Candidates: write, propose, chat
_Output_
```json
{{"thought": "User is reacting to shown options but the target is ambiguous — route to chat to confirm which one.", "flow_name": "chat"}}
```
---
Failed flow: summarize (tool error)
User: "tell me about content calendars"
Candidates: browse, chat
_Output_
```json
{{"thought": "General knowledge question, not about a specific post — route to chat.", "flow_name": "chat"}}
```
---
Failed flow: brainstorm (low confidence)
User: "give me some ideas for my next post"
History: User was just reviewing a draft
Candidates: brainstorm, chat
_Output_
```json
{{"thought": "User is asking for new topic ideas — brainstorm is correct.", "flow_name": "brainstorm"}}
```
---
Failed flow: rework (no prior draft)
User: "revise the introduction"
Candidates: write, rework, chat
_Output_
```json
{{"thought": "No prior draft to rework. Route to write to create content first.", "flow_name": "write"}}
```
---
Failed flow: refine (post not found)
User: "a backyard-composting post I want reading as one piece"
Candidates: outline, compose, brainstorm, chat
_Output_
```json
{{"thought": "There is no post to refine yet — the user is starting a fresh post. Route to outline to build its structure first.", "flow_name": "outline"}}
```
---
Failed flow: release (prerequisites not met)
User: "publish everything"
Candidates: release, schedule, find
_Output_
```json
{{"thought": "No single post is grounded for release — route to find so the user can pick which post to publish.", "flow_name": "find"}}
```
---
Failed flow: audit (missing post reference)
User: "make it more casual"
History: User was just reviewing an outline
Candidates: audit, write, chat
_Output_
```json
{{"thought": "User wants a tone shift — audit handles voice and tone but needs a post reference.", "flow_name": "audit"}}
```
---
Failed flow: schedule (no post selected)
User: "schedule it for tomorrow"
Candidates: schedule, find, chat
_Output_
```json
{{"thought": "No post selected to schedule. Route to find to pick one first.", "flow_name": "find"}}
```
---
Failed flow: chat (tool error)
User: "how should I structure a listicle?"
Candidates: outline, chat
_Output_
```json
{{"thought": "General writing-advice question — answer directly via chat.", "flow_name": "chat"}}
```
'''


def build_contemplate_prompt(user_text: str, failed_flow: str,
                             failure_reason: str, candidates: str,
                             convo_history: str) -> str:
    parts = [
        f'## Failed Flow: {failed_flow}\n'
        f'Reason: {failure_reason}\n',
        f'## Conversation History\n\n{convo_history}\n' if convo_history else '',
        f'## Candidate Flows\n\n{candidates}\n',
        f'## Instructions\n\n{CONTEMPLATE_INSTRUCTIONS}\n',
        f'## Output Format\n\n{CONTEMPLATE_OUTPUT_SHAPE}\n',
        f'## Examples\n{CONTEMPLATE_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ]
    return '\n'.join(p for p in parts if p)
