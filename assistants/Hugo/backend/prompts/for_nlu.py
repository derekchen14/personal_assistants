SLOT_FILLING_INSTRUCTIONS = (
    'Extract slot values from the user utterance and conversation context.\n\n'
    'For each slot in the flow schema:\n'
    '1. Check if the value is explicitly stated in the current utterance\n'
    '2. Check if it can be inferred from recent conversation history\n'
    '3. Mark as null if not found\n\n'
    '### SourceSlot (source)\n'
    'References existing posts, sections, notes, or channels. Returns a dict '
    '(or list of dicts for multiple entities) with keys: post, sec, note, chl, ver.\n'
    '- "post": the post title. Strip status words like "draft", "post", "article" from the end.\n'
    '- "sec": section within the post (e.g. "introduction", "conclusion").\n'
    '- "note": a shorter snippet (tweet, comment).\n'
    '- "chl": channel/platform (only when the entity IS a channel).\n'
    '- "ver": boolean, true if user references a specific version.\n'
    'Omit keys that are empty (or set to empty string). At minimum include "post".\n'
    'When the user says "my X post" or "the X draft", extract X as the post title.\n\n'
    '### TargetSlot (target)\n'
    'New entities being created. Same format as SourceSlot.\n\n'
    '### ChannelSlot (channel)\n'
    'A publishing destination. Return the channel name as a string '
    '(e.g. "Substack", "Medium", "Twitter/X", "LinkedIn", "blog").\n\n'
    '### RangeSlot (datetime)\n'
    'A time or value range. Return the raw date/time expression as a string '
    '(e.g. "Friday 8am EST", "next Monday morning", "March 20th"). '
    'Do not attempt to parse or reformat.\n\n'
    '### CategorySlot (chosen_tone, etc.)\n'
    'Choose one from a predefined list. The user may use synonyms or related terms. '
    'Map to the closest valid option from the provided list '
    '(e.g. "laid back" -> "casual", "formal" -> "professional"). '
    'Return null only if no option is a reasonable match.\n\n'
    '### ExactSlot (custom_tone, etc.)\n'
    'A specific term or phrase provided by the user, verbatim.\n\n'
    '### DictionarySlot (settings)\n'
    'Key-value pairs. Parse instructions into structured pairs '
    '(e.g. "normalize headings, use h2" -> {"headings": "h2", "spacing": "normalize"}).\n\n'
    '### FreeTextSlot (instructions, context, query)\n'
    'Open-ended text. Extract the relevant free-form content from the utterance.\n\n'
    '### ChecklistSlot (steps)\n'
    'An ordered list of steps. Extract numbered or sequential instructions.\n\n'
    '### PositionSlot (position)\n'
    'A non-negative integer indicating position in a sequence.\n\n'
    '### LevelSlot / ProbabilitySlot / ScoreSlot\n'
    'Numeric values. Extract the number directly.\n\n'
    '### ImageSlot (image)\n'
    'An image reference with type (hero, diagram, photo) and description.\n\n'
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
Flow: compose
Slots: source (SourceSlot, required), steps (ChecklistSlot, elective), instructions (FreeTextSlot, elective)
User: "Compose a new post about prompt engineering best practices"
_Output_
```json
{{"slots": {{"source": {{"post": "prompt engineering best practices"}}, "steps": null, "instructions": null}}, "missing": []}}
```
---
Flow: compose
Slots: source (SourceSlot, required), steps (ChecklistSlot, elective), instructions (FreeTextSlot, elective)
User: "Write the positional encoding section in my transformer deep dive post"
_Output_
```json
{{"slots": {{"source": {{"post": "transformer deep dive", "sec": "positional encoding"}}, "steps": null, "instructions": null}}, "missing": []}}
```
---
Flow: compose
Slots: source (SourceSlot, required), steps (ChecklistSlot, elective), instructions (FreeTextSlot, elective)
User: "Draft something about how LLMs handle context windows"
_Output_
```json
{{"slots": {{"source": {{"post": "how LLMs handle context windows"}}, "steps": null, "instructions": null}}, "missing": []}}
```
---
Flow: find
Slots: query (FreeTextSlot, required), count (PositionSlot, optional)
User: "find my posts about machine learning"
_Output_
```json
{{"slots": {{"query": "machine learning", "count": null}}, "missing": []}}
```
---
Flow: find
Slots: query (FreeTextSlot, required), count (PositionSlot, optional)
User: "search for anything I wrote about distributed training"
_Output_
```json
{{"slots": {{"query": "distributed training", "count": null}}, "missing": []}}
```
---
Flow: find
Slots: query (FreeTextSlot, required), count (PositionSlot, optional)
User: "show me 5 posts about attention mechanisms"
_Output_
```json
{{"slots": {{"query": "attention mechanisms", "count": 5}}, "missing": []}}
```
---
Flow: rework
Slots: source (SourceSlot, required)
User: "The Components of Dialogue Systems draft needs a full rewrite"
_Output_
```json
{{"slots": {{"source": {{"post": "Components of Dialogue Systems"}}}}, "missing": []}}
```
---
Flow: rework
Slots: source (SourceSlot, required)
User: "Rework the async communication section in my remote work post"
_Output_
```json
{{"slots": {{"source": {{"post": "remote work", "sec": "async communication"}}}}, "missing": []}}
```
---
Flow: rework
Slots: source (SourceSlot, required)
User: "revise the introduction of my latest post"
_Output_
```json
{{"slots": {{"source": {{"sec": "introduction"}}}}, "missing": ["source"]}}
```
---
Flow: schedule
Slots: source (SourceSlot, required), channel (ChannelSlot, required), datetime (RangeSlot, optional)
User: "Schedule my AI roundup post for Friday at 8am EST on Substack"
_Output_
```json
{{"slots": {{"source": {{"post": "AI roundup"}}, "channel": "Substack", "datetime": "Friday 8am EST"}}, "missing": []}}
```
---
Flow: schedule
Slots: source (SourceSlot, required), channel (ChannelSlot, required), datetime (RangeSlot, optional)
User: "schedule the post for tomorrow on Medium"
_Output_
```json
{{"slots": {{"source": null, "channel": "Medium", "datetime": "tomorrow"}}, "missing": ["source"]}}
```
---
Flow: schedule
Slots: source (SourceSlot, required), channel (ChannelSlot, required), datetime (RangeSlot, optional)
User: "Queue the Attention Mechanism post for March 20th"
_Output_
```json
{{"slots": {{"source": {{"post": "Attention Mechanism"}}, "channel": null, "datetime": "March 20th"}}, "missing": ["channel"]}}
```
---
Flow: release
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Push the History of Seq2Seq draft live on Substack"
_Output_
```json
{{"slots": {{"source": {{"post": "History of Seq2Seq"}}, "channel": "Substack"}}, "missing": []}}
```
---
Flow: release
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Release the crypto investing post now"
_Output_
```json
{{"slots": {{"source": {{"post": "crypto investing"}}, "channel": null}}, "missing": []}}
```
---
Flow: release
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Go ahead and publish it"
_Output_
```json
{{"slots": {{"source": null, "channel": null}}, "missing": ["source"]}}
```
---
Flow: tone
Slots: source (SourceSlot, required), custom_tone (ExactSlot, elective), chosen_tone (CategorySlot, elective)
User: "Make the tone of my ambiguity post more conversational"
_Output_
```json
{{"slots": {{"source": {{"post": "ambiguity"}}, "custom_tone": null, "chosen_tone": "conversational"}}, "missing": []}}
```
---
Flow: tone
Slots: source (SourceSlot, required), custom_tone (ExactSlot, elective), chosen_tone (CategorySlot, elective)
User: "Shift History of Seq2Seq to a dry, academic register"
_Output_
```json
{{"slots": {{"source": {{"post": "History of Seq2Seq"}}, "custom_tone": "dry, academic", "chosen_tone": null}}, "missing": []}}
```
---
Flow: tone
Slots: source (SourceSlot, required), custom_tone (ExactSlot, elective), chosen_tone (CategorySlot, elective)
User: "make it more casual and friendly"
_Output_
```json
{{"slots": {{"source": null, "custom_tone": null, "chosen_tone": "casual"}}, "missing": ["source"]}}
```
---
Flow: compare
Slots: source (SourceSlot, required)
User: "How does my ML as Software 2.0 draft compare to The Hype of Machine Learning?"
_Output_
```json
{{"slots": {{"source": [{{"post": "ML as Software 2.0"}}, {{"post": "The Hype of Machine Learning"}}]}}, "missing": []}}
```
---
Flow: compare
Slots: source (SourceSlot, required)
User: "Compare my REST API tutorial and my GraphQL API tutorial side by side"
_Output_
```json
{{"slots": {{"source": [{{"post": "REST API tutorial"}}, {{"post": "GraphQL API tutorial"}}]}}, "missing": []}}
```
---
Flow: compare
Slots: source (SourceSlot, required)
User: "How do those two stack up?"
_Output_
```json
{{"slots": {{"source": null}}, "missing": ["source"]}}
```
---
Flow: diff
Slots: source (SourceSlot, required), lookback (PositionSlot, elective), mapping (DictionarySlot, elective)
User: "What changed in Solving the Long Tail since the last revision?"
_Output_
```json
{{"slots": {{"source": {{"post": "Solving the Long Tail"}}, "lookback": 1, "mapping": null}}, "missing": []}}
```
---
Flow: diff
Slots: source (SourceSlot, required), lookback (PositionSlot, elective), mapping (DictionarySlot, elective)
User: "Show me the differences between the draft and published version of Data Augmentation"
_Output_
```json
{{"slots": {{"source": {{"post": "Data Augmentation"}}, "lookback": null, "mapping": {{"draft": "published"}}}}, "missing": []}}
```
---
Flow: diff
Slots: source (SourceSlot, required), lookback (PositionSlot, elective), mapping (DictionarySlot, elective)
User: "Compare the current draft of my ML post against two versions ago"
_Output_
```json
{{"slots": {{"source": {{"post": "ML"}}, "lookback": 2, "mapping": null}}, "missing": []}}
```
---
Flow: tidy
Slots: source (SourceSlot, required), settings (DictionarySlot, required)
User: "Clean up the formatting on my Thailand travel post"
_Output_
```json
{{"slots": {{"source": {{"post": "Thailand travel"}}, "settings": {{"task": "formatting"}}}}, "missing": []}}
```
---
Flow: tidy
Slots: source (SourceSlot, required), settings (DictionarySlot, required)
User: "Normalize headings and spacing across EMNLP 2020 Highlights, use h2 for sections"
_Output_
```json
{{"slots": {{"source": {{"post": "EMNLP 2020 Highlights"}}, "settings": {{"headings": "h2", "spacing": "normalize"}}}}, "missing": []}}
```
---
Flow: tidy
Slots: source (SourceSlot, required), settings (DictionarySlot, required)
User: "fix the indentation and bullet points in my API guide"
_Output_
```json
{{"slots": {{"source": {{"post": "API guide"}}, "settings": {{"indentation": "fix", "bullet_points": "fix"}}}}, "missing": []}}
```
---
Flow: preview
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Preview my 100 Research Papers post as it would appear on the blog"
_Output_
```json
{{"slots": {{"source": {{"post": "100 Research Papers"}}, "channel": "blog"}}, "missing": []}}
```
---
Flow: preview
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Show me how the newsletter will look on Substack"
_Output_
```json
{{"slots": {{"source": {{"post": "newsletter"}}, "channel": "Substack"}}, "missing": []}}
```
---
Flow: preview
Slots: source (SourceSlot, required), channel (ChannelSlot, optional)
User: "Let me see a preview of that"
_Output_
```json
{{"slots": {{"source": null, "channel": null}}, "missing": ["source"]}}
```
---
Flow: add
Slots: source (SourceSlot, required), target (TargetSlot, required), position (PositionSlot, optional)
User: "Add a street food section to my Bangkok travel post, right after the intro"
_Output_
```json
{{"slots": {{"source": {{"post": "Bangkok travel"}}, "target": {{"sec": "street food"}}, "position": null}}, "missing": []}}
```
---
Flow: add
Slots: source (SourceSlot, required), target (TargetSlot, required), position (PositionSlot, optional)
User: "Add a disclaimer section at the bottom of my crypto investing post"
_Output_
```json
{{"slots": {{"source": {{"post": "crypto investing"}}, "target": {{"sec": "disclaimer"}}, "position": null}}, "missing": []}}
```
---
Flow: add
Slots: source (SourceSlot, required), target (TargetSlot, required), position (PositionSlot, optional)
User: "I need a new section on evaluation metrics"
_Output_
```json
{{"slots": {{"source": null, "target": {{"sec": "evaluation metrics"}}, "position": null}}, "missing": ["source"]}}
```
---
Flow: audit
Slots: source (SourceSlot, required)
User: "Audit the Thailand travel post against the style of my older travel posts"
_Output_
```json
{{"slots": {{"source": {{"post": "Thailand travel"}}}}, "missing": []}}
```
---
Flow: audit
Slots: source (SourceSlot, required)
User: "Check if this post matches my usual voice and formatting standards"
_Output_
```json
{{"slots": {{"source": null}}, "missing": ["source"]}}
```
---
Flow: audit
Slots: source (SourceSlot, required)
User: "Run a style audit on the conclusion of my ML paper"
_Output_
```json
{{"slots": {{"source": {{"post": "ML paper", "sec": "conclusion"}}}}, "missing": []}}
```
---
Flow: view
Slots: source (SourceSlot, required)
User: "Open the ambiguity bottleneck post"
_Output_
```json
{{"slots": {{"source": {{"post": "ambiguity bottleneck"}}}}, "missing": []}}
```
---
Flow: expand
Slots: source (SourceSlot, required), image (ImageSlot, elective)
User: "Expand the methodology section in my NLP survey post"
_Output_
```json
{{"slots": {{"source": {{"post": "NLP survey", "sec": "methodology"}}, "image": null}}, "missing": []}}
```
---
Flow: syndicate
Slots: source (SourceSlot, required), channel (ChannelSlot, required)
User: "Cross-post my data pipeline article to Medium and LinkedIn"
_Output_
```json
{{"slots": {{"source": {{"post": "data pipeline"}}, "channel": "Medium"}}, "missing": []}}
```
'''


def build_slot_filling_prompt(flow_name: str, slot_schema: str, convo_history: str) -> str:
    parts = [
        f'## Flow: {flow_name}\n',
        f'## Slot Schema\n\n{slot_schema}\n',
        f'## Instructions\n\n{SLOT_FILLING_INSTRUCTIONS}\n',
        f'## Output Format\n\n{SLOT_FILLING_OUTPUT_SHAPE}\n',
        f'## Examples\n{SLOT_FILLING_EXEMPLARS}\n',

        f'_Conversation History_\n{convo_history}\n' if convo_history else '',
        '_Output_',
    ]
    return '\n'.join(p for p in parts if p)
