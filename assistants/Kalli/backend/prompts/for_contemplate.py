CONTEMPLATE_INSTRUCTIONS = (
    'The initial flow prediction failed or had low confidence. '
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
Failed flow: lookup (low confidence)
User: "what is the NLU?"
Candidates: explain, lookup, chat
_Output_
```json
{{"thought": "User is asking for a concept explanation, not a spec file lookup.", "flow_name": "explain", "confidence": 0.85}}
```
---
Failed flow: scope (missing required slots)
User: "yes"
History: Agent asked "What should the assistant be called?"
Candidates: scope, endorse, chat
_Output_
```json
{{"thought": "User is continuing the scope flow — answering a clarification question. But 'yes' alone doesn't provide the name. Route to chat for clarification.", "flow_name": "chat", "confidence": 0.70}}
```
---
Failed flow: approve (ambiguous target)
User: "that one looks good"
History: Agent showed multiple flow proposals
Candidates: approve, endorse, feedback
_Output_
```json
{{"thought": "User is endorsing the most recently shown proposal. Approve is correct but needs slot clarification.", "flow_name": "approve", "confidence": 0.75}}
```
---
Failed flow: explain (tool error)
User: "tell me about memory manager"
Candidates: lookup, explain, chat
_Output_
```json
{{"thought": "Explain failed due to tool error. Try lookup to read the spec directly.", "flow_name": "lookup", "confidence": 0.80}}
```
---
Failed flow: status (empty result)
User: "what have we done so far?"
Candidates: summarize, status, review_lessons
_Output_
```json
{{"thought": "Status returned empty — try summarize for a broader progress overview.", "flow_name": "summarize", "confidence": 0.80}}
```
---
Failed flow: propose (no config data)
User: "show me the dacts"
Candidates: compose, propose, lookup
_Output_
```json
{{"thought": "Propose failed because no config is set up yet. Compose might work if dacts exist, otherwise chat.", "flow_name": "compose", "confidence": 0.65}}
```
---
Failed flow: persona (low confidence)
User: "make it more casual"
History: User was just defining scope
Candidates: persona, preference, style, feedback
_Output_
```json
{{"thought": "User is adjusting tone — persona is correct for defining assistant personality.", "flow_name": "persona", "confidence": 0.85}}
```
---
Failed flow: generate (prerequisites not met)
User: "export everything"
Candidates: confirm_export, generate, preview
_Output_
```json
{{"thought": "Generate failed on prerequisites. Route to preview so user can see what's ready.", "flow_name": "preview", "confidence": 0.75}}
```
---
Failed flow: next_step
User: "hmm"
History: Agent just gave a next step suggestion
Candidates: chat, feedback, endorse
_Output_
```json
{{"thought": "Short ambiguous response after a suggestion. Treat as general chat.", "flow_name": "chat", "confidence": 0.70}}
```
---
Failed flow: intent (missing description)
User: "Search"
History: Agent asked "What intents does your assistant need?"
Candidates: intent, scope, chat
_Output_
```json
{{"thought": "User is providing an intent name in response to a question. Route back to intent.", "flow_name": "intent", "confidence": 0.80}}
```
---
Failed flow: entity
User: "those are the main ones"
History: Agent asked about key entities, user previously said "recipe, ingredient"
Candidates: entity, chat, endorse
_Output_
```json
{{"thought": "User is confirming the entities already provided. Endorse is the best fit.", "flow_name": "endorse", "confidence": 0.75}}
```
---
Failed flow: chat (tool error on spec_read)
User: "how are components organized?"
Candidates: explain, lookup, chat
_Output_
```json
{{"thought": "User wants architecture explanation — explain is the right flow.", "flow_name": "explain", "confidence": 0.85}}
```
---
Failed flow: revise (no prior config)
User: "change the name"
Candidates: scope, revise, persona
_Output_
```json
{{"thought": "No prior config to revise. Route to scope to set the name first.", "flow_name": "scope", "confidence": 0.80}}
```
---
Failed flow: feedback
User: "I think the flow catalog needs more Explore flows"
Candidates: expand, suggest_flow, feedback
_Output_
```json
{{"thought": "User is suggesting design expansion, not just giving feedback.", "flow_name": "suggest_flow", "confidence": 0.80}}
```
---
Failed flow: decline (no active proposal)
User: "no"
History: Agent asked a clarification question
Candidates: chat, decline, dismiss
_Output_
```json
{{"thought": "User is responding 'no' to a clarification, not declining a proposal. Route to chat.", "flow_name": "chat", "confidence": 0.70}}
```
---
Failed flow: compose (empty catalog)
User: "what flows exist?"
Candidates: status, compose, lookup
_Output_
```json
{{"thought": "No flows composed yet. Status can show what config is defined.", "flow_name": "status", "confidence": 0.75}}
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
