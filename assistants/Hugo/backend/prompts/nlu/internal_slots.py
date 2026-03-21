INSTRUCTIONS = {

'recap': (
    'Goal: Read back facts from the current session scratchpad (L1) — '
    'decisions, constraints, or references stored earlier.\n\n'
    'Slots:\n'
    '- key (optional): A specific topic to recall. '
    'If omitted, returns everything from the session.'
),

'store': (
    'Goal: Save a key-value pair to the session scratchpad (L1) '
    'for later use in this session.\n\n'
    'Slots:\n'
    '- entry (required): A dict with "key" and "value". '
    'Parse the statement into a structured pair: '
    '"focus on introduction" → {{"key": "focus", "value": "introduction"}}.'
),

'recall': (
    'Goal: Look up persistent user preferences from long-term memory (L2) — '
    'default tone, word count targets, stylistic rules.\n\n'
    'Slots:\n'
    '- key (optional): Which preference to look up. '
    'If omitted, returns all saved preferences.'
),

'retrieve': (
    'Goal: Fetch unvetted business context from knowledge memory (L3) — '
    'style guides, domain knowledge, reference documents.\n\n'
    'Slots:\n'
    '- topic (required): What to retrieve — the subject area or document type.\n'
    '- context (optional): Narrows the search scope '
    '(e.g., "for technical posts", "about SEO").'
),

'search': (
    'Goal: Look up vetted FAQs and curated editorial guidelines — '
    'the unstructured equivalent of a style manual.\n\n'
    'Slots:\n'
    '- query (required): The search term — extract the core phrase.'
),

'reference': (
    'Goal: Dictionary and thesaurus lookup — definitions, synonyms, '
    'antonyms, or usage examples.\n\n'
    'Slots:\n'
    '- word (required): The word to look up. Extract just the target word.'
),

'study': (
    'Goal: Load a previous post into agent context to match voice, '
    'structure, or vocabulary patterns when writing new content.\n\n'
    'Slots:\n'
    '- source (required): Which post to load.\n'
    '- scope (optional): What aspect to focus on. '
    'Choose from: voice, structure, vocabulary, full.'
),

}


EXEMPLARS = {

'recap': '''
---
Flow: recap
Slots: key (ExactSlot, optional)
User: "What did we decide about the post topic earlier?"
_Output_
```json
{{"slots": {{"key": "post topic"}}, "missing": []}}
```
---
Flow: recap
Slots: key (ExactSlot, optional)
User: "Recap everything from this session"
_Output_
```json
{{"slots": {{"key": null}}, "missing": []}}
```
''',

'store': '''
---
Flow: store
Slots: entry (DictionarySlot, required)
User: "Note that the user wants to focus on the introduction next"
_Output_
```json
{{"slots": {{"entry": {{"key": "focus", "value": "introduction"}}}}, "missing": []}}
```
---
Flow: store
Slots: entry (DictionarySlot, required)
User: "Save that the target audience is intermediate ML practitioners"
_Output_
```json
{{"slots": {{"entry": {{"key": "target_audience", "value": "intermediate ML practitioners"}}}}, "missing": []}}
```
''',

'recall': '''
---
Flow: recall
Slots: key (ExactSlot, optional)
User: "What's my preferred default tone?"
_Output_
```json
{{"slots": {{"key": "default tone"}}, "missing": []}}
```
---
Flow: recall
Slots: key (ExactSlot, optional)
User: "Look up my writing preferences"
_Output_
```json
{{"slots": {{"key": null}}, "missing": []}}
```
''',

'retrieve': '''
---
Flow: retrieve
Slots: topic (ExactSlot, required), context (ExactSlot, optional)
User: "Pull up our style guide for technical posts"
_Output_
```json
{{"slots": {{"topic": "style guide", "context": "technical posts"}}, "missing": []}}
```
---
Flow: retrieve
Slots: topic (ExactSlot, required), context (ExactSlot, optional)
User: "Get the brand voice guidelines"
_Output_
```json
{{"slots": {{"topic": "brand voice guidelines", "context": null}}, "missing": []}}
```
''',

'search': '''
---
Flow: search
Slots: query (ExactSlot, required)
User: "Search our editorial guidelines for image requirements"
_Output_
```json
{{"slots": {{"query": "image requirements"}}, "missing": []}}
```
---
Flow: search
Slots: query (ExactSlot, required)
User: "Look up our FAQ on heading style"
_Output_
```json
{{"slots": {{"query": "heading style"}}, "missing": []}}
```
''',

'reference': '''
---
Flow: reference
Slots: word (ExactSlot, required)
User: "What's a synonym for important?"
_Output_
```json
{{"slots": {{"word": "important"}}, "missing": []}}
```
---
Flow: reference
Slots: word (ExactSlot, required)
User: "Give me formal alternatives to the word good"
_Output_
```json
{{"slots": {{"word": "good"}}, "missing": []}}
```
''',

'study': '''
---
Flow: study
Slots: source (SourceSlot, required), scope (CategorySlot, optional)
User: "Load my Ambiguity is the Bottleneck post to match its voice"
_Output_
```json
{{"slots": {{"source": {{"post": "Ambiguity is the Bottleneck"}}, "scope": "voice"}}, "missing": []}}
```
---
Flow: study
Slots: source (SourceSlot, required), scope (CategorySlot, optional)
User: "Study the structure of my 100 Research Papers post"
_Output_
```json
{{"slots": {{"source": {{"post": "100 Research Papers"}}, "scope": "structure"}}, "missing": []}}
```
''',

}
