INTENT_INSTRUCTIONS = (
    'Classify the user utterance into exactly one intent.\n\n'
    '## Available Intents\n\n'
    '- **Explore**: User wants to browse, look up, or understand something '
    '(specs, config status, architecture concepts)\n'
    '- **Provide**: User is giving information (scope, persona, intents, '
    'entities, lessons, revisions)\n'
    '- **Design**: User is reviewing, approving, rejecting, or refining '
    'flow/dact proposals\n'
    '- **Deliver**: User wants to generate, export, or preview final output '
    'files\n'
    '- **Converse**: General chat, asking what to do next, giving feedback, '
    'greetings, small talk\n'
    '- **Plan**: User wants to start a multi-step process (full onboarding, '
    'research plan, expansion plan)\n\n'
    'Never predict "Internal" — that intent is agent-initiated only.\n\n'
    'Think step by step about what the user wants to DO, not what they '
    'mention. Someone asking "what is a dact?" is Exploring (wanting to '
    'understand), not Designing (not iterating on dacts).'
)

INTENT_OUTPUT_SHAPE = (
    '```json\n'
    '{{\n'
    '  "thought": "<one sentence reasoning>",\n'
    '  "intent": "<Explore|Provide|Design|Deliver|Converse|Plan>"\n'
    '}}\n'
    '```'
)

INTENT_EXEMPLARS = '''
---
User: "hello"
_Output_
```json
{{"thought": "Greeting — general conversation.", "intent": "Converse"}}
```
---
User: "what should I work on next?"
_Output_
```json
{{"thought": "Asking for guidance on next step.", "intent": "Converse"}}
```
---
User: "thanks, that was helpful"
_Output_
```json
{{"thought": "Giving feedback on the process.", "intent": "Converse"}}
```
---
User: "show me the NLU spec"
_Output_
```json
{{"thought": "Looking up a specific spec file.", "intent": "Explore"}}
```
---
User: "what does the flow stack do?"
_Output_
```json
{{"thought": "Wants to understand an architecture concept.", "intent": "Explore"}}
```
---
User: "where are we in the process?"
_Output_
```json
{{"thought": "Checking current progress/status.", "intent": "Explore"}}
```
---
User: "the assistant should be called Chef"
_Output_
```json
{{"thought": "Providing scope information — assistant name.", "intent": "Provide"}}
```
---
User: "add a Cooking intent that handles recipe queries"
_Output_
```json
{{"thought": "Providing a domain intent definition.", "intent": "Provide"}}
```
---
User: "the key entities are recipe, ingredient, and meal"
_Output_
```json
{{"thought": "Providing key entity definitions.", "intent": "Provide"}}
```
---
User: "make the tone professional and concise"
_Output_
```json
{{"thought": "Providing persona preferences.", "intent": "Provide"}}
```
---
User: "actually change the task description to focus on meal planning"
_Output_
```json
{{"thought": "Revising previously provided config.", "intent": "Provide"}}
```
---
User: "I learned that slot names should match tool parameters"
_Output_
```json
{{"thought": "Sharing a lesson/pattern to store.", "intent": "Provide"}}
```
---
User: "show me the proposed dacts"
_Output_
```json
{{"thought": "Reviewing dact proposals — design iteration.", "intent": "Design"}}
```
---
User: "yes, approve that flow"
_Output_
```json
{{"thought": "Approving a proposed flow.", "intent": "Design"}}
```
---
User: "no, reject that one — the slots don't make sense"
_Output_
```json
{{"thought": "Rejecting a proposal with reason.", "intent": "Design"}}
```
---
User: "can you suggest some flows for the Explore intent?"
_Output_
```json
{{"thought": "Asking agent to suggest new flow designs.", "intent": "Design"}}
```
---
User: "change the output type of that flow to 'list'"
_Output_
```json
{{"thought": "Refining a flow's design attributes.", "intent": "Design"}}
```
---
User: "show me the composed flows for Provide"
_Output_
```json
{{"thought": "Reviewing composed flows — design iteration.", "intent": "Design"}}
```
---
User: "generate the final config files"
_Output_
```json
{{"thought": "Requesting file generation/export.", "intent": "Deliver"}}
```
---
User: "create the ontology.py"
_Output_
```json
{{"thought": "Requesting specific file generation.", "intent": "Deliver"}}
```
---
User: "preview what the YAML will look like"
_Output_
```json
{{"thought": "Previewing generated output before committing.", "intent": "Deliver"}}
```
---
User: "let's build an assistant for a cooking app"
_Output_
```json
{{"thought": "Starting the full onboarding process.", "intent": "Plan"}}
```
---
User: "I want to start from scratch with a new domain"
_Output_
```json
{{"thought": "Initiating multi-step onboarding plan.", "intent": "Plan"}}
```
---
User: "let's research what specs are relevant for scheduling"
_Output_
```json
{{"thought": "Planning a research sequence.", "intent": "Plan"}}
```
---
User: "can you look up how POMDP works in this system?"
_Output_
```json
{{"thought": "Asking to understand an architecture concept.", "intent": "Explore"}}
```
---
User: "I don't think we need that many flows"
_Output_
```json
{{"thought": "Giving feedback — conversational.", "intent": "Converse"}}
```
---
User: "the assistant handles both recipe search and meal planning"
_Output_
```json
{{"thought": "Providing task/scope information.", "intent": "Provide"}}
```
---
User: "what's the difference between a dact and a flow?"
_Output_
```json
{{"thought": "Wants conceptual explanation.", "intent": "Explore"}}
```
---
User: "ok ship it"
_Output_
```json
{{"thought": "Confirming export/delivery.", "intent": "Deliver"}}
```
---
User: "I'd like to set my preference for verbose responses"
_Output_
```json
{{"thought": "Setting a user preference.", "intent": "Converse"}}
```
---
User: "remove the Compare flow"
_Output_
```json
{{"thought": "Rejecting/declining a specific flow.", "intent": "Design"}}
```
---
User: "what lessons have we stored so far?"
_Output_
```json
{{"thought": "Browsing stored lessons.", "intent": "Explore"}}
```
---
User: "let's plan out adding more flows to the Deliver intent"
_Output_
```json
{{"thought": "Planning a flow expansion sequence.", "intent": "Plan"}}
```
'''


FLOW_INSTRUCTIONS = (
    'Given the predicted intent and conversation context, classify the user '
    'utterance into the most specific flow.\n\n'
    'Each flow has a dax code, description, and slots. Pick the flow that '
    'best matches what the user wants to accomplish.\n\n'
    'If multiple flows could match, prefer:\n'
    '1. The flow whose description most closely matches the user\'s goal\n'
    '2. The flow with slots that match extractable information\n'
    '3. The simpler/more common flow over the specialized one\n\n'
    'Also extract any slot values you can identify from the utterance.'
)

FLOW_OUTPUT_SHAPE = (
    '```json\n'
    '{{\n'
    '  "thought": "<reasoning about which flow matches>",\n'
    '  "flow_name": "<flow_name>",\n'
    '  "confidence": <0.0-1.0>,\n'
    '  "slots": {{"<slot_name>": "<value>", ...}}\n'
    '}}\n'
    '```'
)

FLOW_EXEMPLARS = '''
---
Intent: Converse
User: "hi there"
_Output_
```json
{{"thought": "Simple greeting — open-ended chat.", "flow_name": "chat", "confidence": 0.95, "slots": {{}}}}
```
---
Intent: Converse
User: "what should I do next?"
_Output_
```json
{{"thought": "Asking for next step guidance.", "flow_name": "next_step", "confidence": 0.95, "slots": {{}}}}
```
---
Intent: Converse
User: "that explanation was really clear, thanks"
_Output_
```json
{{"thought": "Positive feedback on the process.", "flow_name": "feedback", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Explore
User: "show me the current config"
_Output_
```json
{{"thought": "Viewing current config state.", "flow_name": "status", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Explore
User: "look up the display frame spec"
_Output_
```json
{{"thought": "Looking up a specific spec file.", "flow_name": "lookup", "confidence": 0.95, "slots": {{"spec_name": "display_frame"}}}}
```
---
Intent: Explore
User: "what is a dact and how does the grammar work?"
_Output_
```json
{{"thought": "Asking for conceptual explanation.", "flow_name": "explain", "confidence": 0.90, "slots": {{"concept": "dact grammar"}}}}
```
---
Intent: Explore
User: "what lessons have we recorded?"
_Output_
```json
{{"thought": "Browsing stored lessons.", "flow_name": "review_lessons", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Explore
User: "give me a summary of where we are"
_Output_
```json
{{"thought": "Agent summarizes overall progress.", "flow_name": "summarize", "confidence": 0.85, "slots": {{}}}}
```
---
Intent: Provide
User: "the assistant is called Aria and it handles scheduling"
_Output_
```json
{{"thought": "Defining scope — name and task.", "flow_name": "scope", "confidence": 0.95, "slots": {{"name": "Aria", "task": "scheduling"}}}}
```
---
Intent: Provide
User: "set the tone to friendly and the style to verbose"
_Output_
```json
{{"thought": "Defining persona preferences.", "flow_name": "persona", "confidence": 0.90, "slots": {{"tone": "friendly", "response_style": "verbose"}}}}
```
---
Intent: Provide
User: "add a Search intent for browsing available events"
_Output_
```json
{{"thought": "Providing a domain intent definition.", "flow_name": "intent", "confidence": 0.95, "slots": {{"intent_name": "Search", "description": "browsing available events"}}}}
```
---
Intent: Provide
User: "the key entities are event, calendar, and attendee"
_Output_
```json
{{"thought": "Defining key entities.", "flow_name": "entity", "confidence": 0.95, "slots": {{"entities": "event, calendar, attendee"}}}}
```
---
Intent: Provide
User: "actually change the name to Scheduler instead"
_Output_
```json
{{"thought": "Revising previously defined config.", "flow_name": "revise", "confidence": 0.90, "slots": {{"section": "scope", "field": "name", "value": "Scheduler"}}}}
```
---
Intent: Provide
User: "I noticed that slot types should always be specific"
_Output_
```json
{{"thought": "Sharing a lesson to store.", "flow_name": "teach", "confidence": 0.85, "slots": {{"pattern": "slot types should always be specific"}}}}
```
---
Intent: Design
User: "show me the proposed dacts"
_Output_
```json
{{"thought": "Reviewing proposed dacts.", "flow_name": "propose", "confidence": 0.95, "slots": {{}}}}
```
---
Intent: Design
User: "show the composed flows"
_Output_
```json
{{"thought": "Reviewing composed flow catalog.", "flow_name": "compose", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Design
User: "approve the read_recipe flow"
_Output_
```json
{{"thought": "Approving a specific flow.", "flow_name": "approve", "confidence": 0.95, "slots": {{"flow_name": "read_recipe"}}}}
```
---
Intent: Design
User: "reject nutrition_lookup — too specialized"
_Output_
```json
{{"thought": "Rejecting a flow with reason.", "flow_name": "decline", "confidence": 0.95, "slots": {{"flow_name": "nutrition_lookup", "reason": "too specialized"}}}}
```
---
Intent: Design
User: "suggest some flows for the Deliver intent"
_Output_
```json
{{"thought": "Asking agent to suggest new flows.", "flow_name": "suggest_flow", "confidence": 0.90, "slots": {{"intent_hint": "Deliver"}}}}
```
---
Intent: Design
User: "change the output type of that flow to card"
_Output_
```json
{{"thought": "Refining flow attributes.", "flow_name": "refine", "confidence": 0.85, "slots": {{"change": "output type to card"}}}}
```
---
Intent: Deliver
User: "generate the final config files"
_Output_
```json
{{"thought": "Requesting file generation.", "flow_name": "generate", "confidence": 0.95, "slots": {{}}}}
```
---
Intent: Deliver
User: "create the ontology.py"
_Output_
```json
{{"thought": "Generating ontology specifically.", "flow_name": "ontology", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Deliver
User: "let me preview the YAML first"
_Output_
```json
{{"thought": "Previewing output before committing.", "flow_name": "preview", "confidence": 0.90, "slots": {{"file_type": "yaml"}}}}
```
---
Intent: Deliver
User: "ok export everything"
_Output_
```json
{{"thought": "Confirming export.", "flow_name": "confirm_export", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Plan
User: "let's build an assistant for cooking"
_Output_
```json
{{"thought": "Starting full onboarding process.", "flow_name": "onboard", "confidence": 0.95, "slots": {{"domain": "cooking"}}}}
```
---
Intent: Plan
User: "I want to research what the scheduling specs say"
_Output_
```json
{{"thought": "Planning a research sequence.", "flow_name": "research", "confidence": 0.90, "slots": {{"topic": "scheduling specs"}}}}
```
---
Intent: Plan
User: "let's add more flows to the Design intent"
_Output_
```json
{{"thought": "Planning flow expansion.", "flow_name": "expand", "confidence": 0.85, "slots": {{"intent_filter": "Design"}}}}
```
---
Intent: Explore
User: "look at the persona section in detail"
_Output_
```json
{{"thought": "Inspecting a draft config section.", "flow_name": "inspect", "confidence": 0.85, "slots": {{"section": "persona"}}}}
```
---
Intent: Converse
User: "I prefer short, to-the-point responses"
_Output_
```json
{{"thought": "Setting a user preference.", "flow_name": "preference", "confidence": 0.85, "slots": {{"key": "response_style", "value": "concise"}}}}
```
---
Intent: Converse
User: "sure, go ahead with that"
_Output_
```json
{{"thought": "Endorsing an agent suggestion.", "flow_name": "endorse", "confidence": 0.80, "slots": {{}}}}
```
---
Intent: Design
User: "edit the revise_flow — change the description"
_Output_
```json
{{"thought": "Revising an in-progress flow design.", "flow_name": "revise_flow", "confidence": 0.85, "slots": {{"flow_name": "revise_flow", "field": "description"}}}}
```
'''


def build_intent_prompt(user_text: str, history_text: str) -> str:
    parts = [
        f'## Conversation History\n\n{history_text}\n' if history_text else '',
        f'## Instructions\n\n{INTENT_INSTRUCTIONS}\n',
        f'## Output Format\n\n{INTENT_OUTPUT_SHAPE}\n',
        f'## Examples\n{INTENT_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ]
    return '\n'.join(p for p in parts if p)


def build_flow_prompt(user_text: str, intent: str, history_text: str,
                      candidate_flows: str) -> str:
    parts = [
        f'## Conversation History\n\n{history_text}\n' if history_text else '',
        f'## Predicted Intent: {intent}\n',
        f'## Candidate Flows\n\n{candidate_flows}\n',
        f'## Instructions\n\n{FLOW_INSTRUCTIONS}\n',
        f'## Output Format\n\n{FLOW_OUTPUT_SHAPE}\n',
        f'## Examples\n{FLOW_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ]
    return '\n'.join(p for p in parts if p)
