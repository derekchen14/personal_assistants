INTENT_INSTRUCTIONS = (
    'Classify the user utterance into exactly one intent.\n\n'
    'Available intents:\n'
    '- Research: browse topics, search posts, view drafts, check channels, '
    'explain concepts, find related content, compare posts\n'
    '- Draft: brainstorm, generate outlines, write or expand content, '
    'create new posts, add/refine sections\n'
    '- Revise: deep revision, polish sections, adjust tone, check consistency, '
    'format for publication, accept/reject changes, compare drafts\n'
    '- Publish: publish, cross-post, schedule, preview, promote, cancel publication\n'
    '- Converse: greetings, next step, feedback, preferences, style, '
    'endorse/dismiss suggestions\n'
    '- Plan: plan a post, plan revision, content calendar, research plan, '
    'series planning\n\n'
    'Do NOT predict "Internal" — that intent is system-only.\n\n'
    'Think step-by-step about the user\'s goal, then classify.'
)

INTENT_EXEMPLARS = '''
---
User: "I want to write about AI trends"
_Output_
```json
{{"reasoning": "User wants to create new content about a topic.", "intent": "Draft"}}
```
---
User: "show me my drafts"
_Output_
```json
{{"reasoning": "User wants to see current draft status.", "intent": "Research"}}
```
---
User: "revise the intro to be more engaging"
_Output_
```json
{{"reasoning": "User wants to improve existing content.", "intent": "Revise"}}
```
---
User: "publish it to Medium"
_Output_
```json
{{"reasoning": "User wants to publish content to a channel.", "intent": "Publish"}}
```
---
User: "hi there"
_Output_
```json
{{"reasoning": "Simple greeting.", "intent": "Converse"}}
```
---
User: "what should I do next?"
_Output_
```json
{{"reasoning": "Asking for next step guidance.", "intent": "Converse"}}
```
---
User: "let's plan out a 5-part series on cooking"
_Output_
```json
{{"reasoning": "Planning a multi-part content series.", "intent": "Plan"}}
```
---
User: "find posts about productivity"
_Output_
```json
{{"reasoning": "Searching through existing content.", "intent": "Research"}}
```
---
User: "make the tone more professional"
_Output_
```json
{{"reasoning": "Adjusting writing style of existing content.", "intent": "Revise"}}
```
---
User: "brainstorm some ideas for a tech blog"
_Output_
```json
{{"reasoning": "Generating new content ideas.", "intent": "Draft"}}
```
---
User: "schedule the post for next Monday"
_Output_
```json
{{"reasoning": "Scheduling a post for future publication.", "intent": "Publish"}}
```
---
User: "what channels do I have connected?"
_Output_
```json
{{"reasoning": "Checking channel configuration.", "intent": "Research"}}
```
---
User: "I prefer shorter paragraphs"
_Output_
```json
{{"reasoning": "Setting a writing preference.", "intent": "Converse"}}
```
---
User: "plan the revision for my latest post"
_Output_
```json
{{"reasoning": "Planning a revision sequence.", "intent": "Plan"}}
```
---
User: "approve those changes"
_Output_
```json
{{"reasoning": "Accepting a revision.", "intent": "Revise"}}
```
---
User: "compare my last two posts"
_Output_
```json
{{"reasoning": "Comparing existing content.", "intent": "Research"}}
```
---
User: "sure, go ahead"
_Output_
```json
{{"reasoning": "Endorsing a suggestion.", "intent": "Converse"}}
```
---
User: "create a content calendar for the next month"
_Output_
```json
{{"reasoning": "Planning content schedule.", "intent": "Plan"}}
```
---
User: "how do I structure a listicle?"
_Output_
```json
{{"reasoning": "Asking about a writing concept.", "intent": "Research"}}
```
---
User: "start a new post about remote work tips"
_Output_
```json
{{"reasoning": "Creating new content.", "intent": "Draft"}}
```
'''


FLOW_INSTRUCTIONS = (
    'Given the predicted intent and conversation context, detect the most '
    'specific flow for the user utterance.\n\n'
    'Each flow has a dax code and description. Pick the flow that best '
    'matches what the user wants to accomplish.\n\n'
    'If multiple flows could match, prefer:\n'
    '1. The flow whose description most closely matches the user\'s goal\n'
    '2. The simpler/more common flow over the specialized one'
)

FLOW_EXEMPLARS = '''
---
Intent: Converse
User: "hello"
_Output_
```json
{{"reasoning": "Simple greeting.", "flow_name": "chat", "confidence": 0.95}}
```
---
Intent: Converse
User: "what should I work on next?"
_Output_
```json
{{"reasoning": "Asking for next step.", "flow_name": "next", "confidence": 0.95}}
```
---
Intent: Converse
User: "that outline was really helpful"
_Output_
```json
{{"reasoning": "Giving positive feedback.", "flow_name": "feedback", "confidence": 0.90}}
```
---
Intent: Converse
User: "I like shorter paragraphs"
_Output_
```json
{{"reasoning": "Setting a writing preference.", "flow_name": "preference", "confidence": 0.85}}
```
---
Intent: Converse
User: "sure, go with that"
_Output_
```json
{{"reasoning": "Endorsing a suggestion.", "flow_name": "endorse", "confidence": 0.80}}
```
---
Intent: Research
User: "show me my current drafts"
_Output_
```json
{{"reasoning": "Checking draft status.", "flow_name": "check", "confidence": 0.95}}
```
---
Intent: Research
User: "search for posts about machine learning"
_Output_
```json
{{"reasoning": "Searching posts by keyword.", "flow_name": "search", "confidence": 0.95}}
```
---
Intent: Research
User: "what channels do I have?"
_Output_
```json
{{"reasoning": "Viewing configured channels.", "flow_name": "survey", "confidence": 0.90}}
```
---
Intent: Research
User: "browse topic ideas"
_Output_
```json
{{"reasoning": "Browsing available topics.", "flow_name": "browse", "confidence": 0.90}}
```
---
Intent: Research
User: "how do I write a good hook?"
_Output_
```json
{{"reasoning": "Asking about a writing concept.", "flow_name": "explain", "confidence": 0.90}}
```
---
Intent: Research
User: "find content related to productivity"
_Output_
```json
{{"reasoning": "Finding related content.", "flow_name": "find", "confidence": 0.85}}
```
---
Intent: Draft
User: "brainstorm ideas for a tech blog"
_Output_
```json
{{"reasoning": "Brainstorming topic ideas.", "flow_name": "brainstorm", "confidence": 0.95}}
```
---
Intent: Draft
User: "create an outline for a post about remote work"
_Output_
```json
{{"reasoning": "Generating an outline.", "flow_name": "outline", "confidence": 0.95}}
```
---
Intent: Draft
User: "start a new post called 10 Tips for Better Sleep"
_Output_
```json
{{"reasoning": "Creating a new post.", "flow_name": "create", "confidence": 0.95}}
```
---
Intent: Draft
User: "expand the introduction section"
_Output_
```json
{{"reasoning": "Expanding content from outline.", "flow_name": "expand", "confidence": 0.85}}
```
---
Intent: Draft
User: "write the conclusion"
_Output_
```json
{{"reasoning": "Writing a specific section.", "flow_name": "write", "confidence": 0.90}}
```
---
Intent: Revise
User: "revise the whole post — it needs work"
_Output_
```json
{{"reasoning": "Major revision needed.", "flow_name": "rework", "confidence": 0.90}}
```
---
Intent: Revise
User: "polish the second paragraph"
_Output_
```json
{{"reasoning": "Polishing a specific section.", "flow_name": "polish", "confidence": 0.90}}
```
---
Intent: Revise
User: "make the tone more professional"
_Output_
```json
{{"reasoning": "Adjusting post tone.", "flow_name": "tone", "confidence": 0.90}}
```
---
Intent: Revise
User: "looks good, accept the changes"
_Output_
```json
{{"reasoning": "Accepting a revision.", "flow_name": "accept", "confidence": 0.90}}
```
---
Intent: Revise
User: "format it for publication"
_Output_
```json
{{"reasoning": "Formatting for publish.", "flow_name": "format", "confidence": 0.90}}
```
---
Intent: Publish
User: "publish it"
_Output_
```json
{{"reasoning": "Publishing to primary blog.", "flow_name": "release", "confidence": 0.90}}
```
---
Intent: Publish
User: "post it on Twitter too"
_Output_
```json
{{"reasoning": "Cross-posting to a channel.", "flow_name": "syndicate", "confidence": 0.90}}
```
---
Intent: Publish
User: "schedule it for next Friday at 9am"
_Output_
```json
{{"reasoning": "Scheduling for later.", "flow_name": "schedule", "confidence": 0.90}}
```
---
Intent: Publish
User: "let me preview how it will look"
_Output_
```json
{{"reasoning": "Previewing published format.", "flow_name": "preview", "confidence": 0.85}}
```
---
Intent: Plan
User: "let's plan out this blog post"
_Output_
```json
{{"reasoning": "Planning the post creation workflow.", "flow_name": "blueprint", "confidence": 0.90}}
```
---
Intent: Plan
User: "plan a revision for my latest draft"
_Output_
```json
{{"reasoning": "Planning a revision sequence.", "flow_name": "triage", "confidence": 0.90}}
```
---
Intent: Plan
User: "create a content calendar for next month"
_Output_
```json
{{"reasoning": "Planning content schedule.", "flow_name": "calendar", "confidence": 0.90}}
```
---
Intent: Plan
User: "plan a 3-part series on investing"
_Output_
```json
{{"reasoning": "Planning a multi-part series.", "flow_name": "digest", "confidence": 0.90}}
```
'''


def build_intent_prompt(user_text: str, convo_history: str) -> str:
    parts = [
        f'## Conversation History\n\n{convo_history}\n' if convo_history else '',
        f'## Instructions\n\n{INTENT_INSTRUCTIONS}\n',
        f'## Examples\n{INTENT_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ]
    return '\n'.join(p for p in parts if p)


def build_flow_prompt(user_text: str, intent: str | None, convo_history: str,
                      candidate_flows: str) -> str:
    parts = [
        f'## Conversation History\n\n{convo_history}\n' if convo_history else '',
    ]
    if intent:
        parts.append(f'## Predicted Intent: {intent}\n')
    parts.extend([
        f'## Candidate Flows\n\n{candidate_flows}\n',
        f'## Instructions\n\n{FLOW_INSTRUCTIONS}\n',
        f'## Examples\n{FLOW_EXEMPLARS}\n',
        f'## Current Utterance\n\nUser: "{user_text}"\n\n',
        '_Output_',
    ])
    return '\n'.join(p for p in parts if p)
