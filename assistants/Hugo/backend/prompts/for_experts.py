INTENT_INSTRUCTIONS = (
    'Classify the user utterance into exactly one intent.\n\n'
    'Available intents:\n'
    '- Research: browse topics, search posts, view drafts, check platforms, '
    'explain concepts, find related content, compare posts\n'
    '- Draft: brainstorm, generate outlines, write or expand content, '
    'create new posts, add/refine sections\n'
    '- Revise: deep revision, polish sections, adjust tone, check consistency, '
    'format for publication, accept/reject changes, compare drafts\n'
    '- Publish: publish, cross-post, schedule, preview, confirm/cancel publication\n'
    '- Converse: greetings, next step, feedback, preferences, style, '
    'endorse/dismiss suggestions\n'
    '- Plan: plan a post, plan revision, content calendar, research plan, '
    'series planning\n\n'
    'Do NOT predict "Internal" — that intent is system-only.\n\n'
    'Think step-by-step about the user\'s goal, then classify.'
)

INTENT_OUTPUT_SHAPE = (
    '```json\n'
    '{{"thought": "<reasoning>", "intent": "<Intent>"}}\n'
    '```'
)

INTENT_EXEMPLARS = '''
---
User: "I want to write about AI trends"
_Output_
```json
{{"thought": "User wants to create new content about a topic.", "intent": "Draft"}}
```
---
User: "show me my drafts"
_Output_
```json
{{"thought": "User wants to see current draft status.", "intent": "Research"}}
```
---
User: "revise the intro to be more engaging"
_Output_
```json
{{"thought": "User wants to improve existing content.", "intent": "Revise"}}
```
---
User: "publish it to Medium"
_Output_
```json
{{"thought": "User wants to publish content to a platform.", "intent": "Publish"}}
```
---
User: "hi there"
_Output_
```json
{{"thought": "Simple greeting.", "intent": "Converse"}}
```
---
User: "what should I do next?"
_Output_
```json
{{"thought": "Asking for next step guidance.", "intent": "Converse"}}
```
---
User: "let's plan out a 5-part series on cooking"
_Output_
```json
{{"thought": "Planning a multi-part content series.", "intent": "Plan"}}
```
---
User: "find posts about productivity"
_Output_
```json
{{"thought": "Searching through existing content.", "intent": "Research"}}
```
---
User: "make the tone more professional"
_Output_
```json
{{"thought": "Adjusting writing style of existing content.", "intent": "Revise"}}
```
---
User: "brainstorm some ideas for a tech blog"
_Output_
```json
{{"thought": "Generating new content ideas.", "intent": "Draft"}}
```
---
User: "schedule the post for next Monday"
_Output_
```json
{{"thought": "Scheduling a post for future publication.", "intent": "Publish"}}
```
---
User: "what platforms do I have connected?"
_Output_
```json
{{"thought": "Checking platform configuration.", "intent": "Research"}}
```
---
User: "I prefer shorter paragraphs"
_Output_
```json
{{"thought": "Setting a writing preference.", "intent": "Converse"}}
```
---
User: "plan the revision for my latest post"
_Output_
```json
{{"thought": "Planning a revision sequence.", "intent": "Plan"}}
```
---
User: "approve those changes"
_Output_
```json
{{"thought": "Accepting a revision.", "intent": "Revise"}}
```
---
User: "compare my last two posts"
_Output_
```json
{{"thought": "Comparing existing content.", "intent": "Research"}}
```
---
User: "sure, go ahead"
_Output_
```json
{{"thought": "Endorsing a suggestion.", "intent": "Converse"}}
```
---
User: "create a content calendar for the next month"
_Output_
```json
{{"thought": "Planning content schedule.", "intent": "Plan"}}
```
---
User: "how do I structure a listicle?"
_Output_
```json
{{"thought": "Asking about a writing concept.", "intent": "Research"}}
```
---
User: "start a new post about remote work tips"
_Output_
```json
{{"thought": "Creating new content.", "intent": "Draft"}}
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
User: "hello"
_Output_
```json
{{"thought": "Simple greeting.", "flow_name": "chat", "confidence": 0.95, "slots": {{}}}}
```
---
Intent: Converse
User: "what should I work on next?"
_Output_
```json
{{"thought": "Asking for next step.", "flow_name": "next", "confidence": 0.95, "slots": {{}}}}
```
---
Intent: Converse
User: "that outline was really helpful"
_Output_
```json
{{"thought": "Giving positive feedback.", "flow_name": "feedback", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Converse
User: "I like shorter paragraphs"
_Output_
```json
{{"thought": "Setting a writing preference.", "flow_name": "preference", "confidence": 0.85, "slots": {{"key": "paragraph_length", "value": "short"}}}}
```
---
Intent: Converse
User: "sure, go with that"
_Output_
```json
{{"thought": "Endorsing a suggestion.", "flow_name": "endorse", "confidence": 0.80, "slots": {{}}}}
```
---
Intent: Research
User: "show me my current drafts"
_Output_
```json
{{"thought": "Checking draft status.", "flow_name": "check", "confidence": 0.95, "slots": {{}}}}
```
---
Intent: Research
User: "search for posts about machine learning"
_Output_
```json
{{"thought": "Searching posts by keyword.", "flow_name": "search", "confidence": 0.95, "slots": {{"query": "machine learning"}}}}
```
---
Intent: Research
User: "what platforms do I have?"
_Output_
```json
{{"thought": "Viewing configured platforms.", "flow_name": "survey", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Research
User: "browse topic ideas"
_Output_
```json
{{"thought": "Browsing available topics.", "flow_name": "browse", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Research
User: "how do I write a good hook?"
_Output_
```json
{{"thought": "Asking about a writing concept.", "flow_name": "explain", "confidence": 0.90, "slots": {{"concept": "writing a good hook"}}}}
```
---
Intent: Research
User: "find content related to productivity"
_Output_
```json
{{"thought": "Finding related content.", "flow_name": "find", "confidence": 0.85, "slots": {{"topic": "productivity"}}}}
```
---
Intent: Draft
User: "brainstorm ideas for a tech blog"
_Output_
```json
{{"thought": "Brainstorming topic ideas.", "flow_name": "brainstorm", "confidence": 0.95, "slots": {{"topic": "tech blog"}}}}
```
---
Intent: Draft
User: "create an outline for a post about remote work"
_Output_
```json
{{"thought": "Generating an outline.", "flow_name": "outline", "confidence": 0.95, "slots": {{"topic": "remote work"}}}}
```
---
Intent: Draft
User: "start a new post called 10 Tips for Better Sleep"
_Output_
```json
{{"thought": "Creating a new post.", "flow_name": "create", "confidence": 0.95, "slots": {{"title": "10 Tips for Better Sleep"}}}}
```
---
Intent: Draft
User: "expand the introduction section"
_Output_
```json
{{"thought": "Expanding content from outline.", "flow_name": "expand", "confidence": 0.85, "slots": {{"section": "introduction"}}}}
```
---
Intent: Draft
User: "write the conclusion"
_Output_
```json
{{"thought": "Writing a specific section.", "flow_name": "write", "confidence": 0.90, "slots": {{"section": "conclusion"}}}}
```
---
Intent: Revise
User: "revise the whole post — it needs work"
_Output_
```json
{{"thought": "Major revision needed.", "flow_name": "rework", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Revise
User: "polish the second paragraph"
_Output_
```json
{{"thought": "Polishing a specific section.", "flow_name": "polish", "confidence": 0.90, "slots": {{"section": "second paragraph"}}}}
```
---
Intent: Revise
User: "make the tone more professional"
_Output_
```json
{{"thought": "Adjusting post tone.", "flow_name": "tone", "confidence": 0.90, "slots": {{"tone": "professional"}}}}
```
---
Intent: Revise
User: "looks good, accept the changes"
_Output_
```json
{{"thought": "Accepting a revision.", "flow_name": "accept", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Revise
User: "format it for publication"
_Output_
```json
{{"thought": "Formatting for publish.", "flow_name": "format", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Publish
User: "publish it"
_Output_
```json
{{"thought": "Publishing to primary blog.", "flow_name": "release", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Publish
User: "post it on Twitter too"
_Output_
```json
{{"thought": "Cross-posting to a platform.", "flow_name": "syndicate", "confidence": 0.90, "slots": {{"platform": "Twitter"}}}}
```
---
Intent: Publish
User: "schedule it for next Friday at 9am"
_Output_
```json
{{"thought": "Scheduling for later.", "flow_name": "schedule", "confidence": 0.90, "slots": {{"datetime": "next Friday at 9am"}}}}
```
---
Intent: Publish
User: "let me preview how it will look"
_Output_
```json
{{"thought": "Previewing published format.", "flow_name": "preview", "confidence": 0.85, "slots": {{}}}}
```
---
Intent: Plan
User: "let's plan out this blog post"
_Output_
```json
{{"thought": "Planning the post creation workflow.", "flow_name": "blueprint", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Plan
User: "plan a revision for my latest draft"
_Output_
```json
{{"thought": "Planning a revision sequence.", "flow_name": "triage", "confidence": 0.90, "slots": {{}}}}
```
---
Intent: Plan
User: "create a content calendar for next month"
_Output_
```json
{{"thought": "Planning content schedule.", "flow_name": "calendar", "confidence": 0.90, "slots": {{"timeframe": "next month"}}}}
```
---
Intent: Plan
User: "plan a 3-part series on investing"
_Output_
```json
{{"thought": "Planning a multi-part series.", "flow_name": "digest", "confidence": 0.90, "slots": {{"theme": "investing", "part_count": "3"}}}}
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


def build_flow_prompt(user_text: str, intent: str | None, history_text: str,
                      candidate_flows: str) -> str:
    parts = [
        f'## Conversation History\n\n{history_text}\n' if history_text else '',
    ]
    if intent:
        parts.append(f'## Predicted Intent: {intent}\n')
    parts.extend([
        f'## Candidate Flows\n\n{candidate_flows}\n',
        f'## Instructions\n\n{FLOW_INSTRUCTIONS}\n',
        f'## Output Format\n\n{FLOW_OUTPUT_SHAPE}\n',
        f'## Examples\n{FLOW_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ])
    return '\n'.join(p for p in parts if p)
