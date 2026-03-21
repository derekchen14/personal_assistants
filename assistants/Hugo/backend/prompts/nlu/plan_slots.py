INSTRUCTIONS = {

'blueprint': (
    'Goal: Plan the full post creation workflow from idea to publication — '
    'orchestrates Research, Draft, Revise, and Publish into a sequenced checklist.\n\n'
    'Slots:\n'
    '- topic (optional): What the post will be about. '
    'Only extract if explicitly mentioned.\n'
    '- steps (optional): User-defined workflow steps as a ChecklistSlot. '
    'Each item\'s "name" is a workflow phase (e.g., "Research", "Outline", "Draft").'
),

'triage': (
    'Goal: Examine a draft and prioritize revision tasks — '
    'which sections need rework, polish, or restructuring.\n\n'
    'Slots:\n'
    '- source (required): The draft to examine.\n'
    '- scope (optional): Which dimension to focus on. '
    'Choose from: content, structure, style, seo, full.\n'
    '- count (optional): Maximum number of issues to surface. '
    'Only extract if the user states a specific number.'
),

'calendar': (
    'Goal: Plan a publishing schedule over weeks or months — '
    'topics to draft, target dates, posting cadence.\n\n'
    'Slots:\n'
    '- timeframe (elective): The period to plan over. '
    'Pass the raw expression (e.g., "next 4 weeks", "this quarter").\n'
    '- count (elective): How many posts to target in the period.'
),

'scope': (
    'Goal: Define what to research before writing — '
    'information to gather, posts to reference, questions to answer.\n\n'
    'Slots:\n'
    '- topic (required): The subject to research.'
),

'digest': (
    'Goal: Split a broad theme into a multi-part blog series — '
    'installments, narrative arc, subtopics per part.\n\n'
    'Slots:\n'
    '- theme (required): The broad theme of the series.\n'
    '- part_count (optional): How many installments. '
    'Only extract if the user specifies a number.'
),

'remember': (
    'Goal: Route a memory operation — determine whether to store (L1 session), '
    'save as preference (L2), or retrieve from knowledge (L3).\n\n'
    'Slots:\n'
    '- key (elective): What to remember or look up.\n'
    '- scope (elective): Where to store or retrieve. Choose from: '
    'session (current session only), user (persistent preferences), '
    'global (business knowledge).'
),

}


EXEMPLARS = {

'blueprint': '''
---
Flow: blueprint
Slots: topic (ExactSlot, optional), steps (ChecklistSlot, optional)
User: "Plan out a full post on retrieval-augmented generation from idea to publish"
_Output_
```json
{{"slots": {{"topic": "retrieval-augmented generation", "steps": null}}, "missing": []}}
```
---
Flow: blueprint
Slots: topic (ExactSlot, optional), steps (ChecklistSlot, optional)
User: "Blueprint a post about MLOps: research, outline, draft, review, publish"
_Output_
```json
{{"slots": {{"topic": "MLOps", "steps": [{{"name": "Research", "description": "", "checked": false}}, {{"name": "Outline", "description": "", "checked": false}}, {{"name": "Draft", "description": "", "checked": false}}, {{"name": "Review", "description": "", "checked": false}}, {{"name": "Publish", "description": "", "checked": false}}]}}, "missing": []}}
```
---
Flow: blueprint
Slots: topic (ExactSlot, optional), steps (ChecklistSlot, optional)
User: "Help me plan my next post"
_Output_
```json
{{"slots": {{"topic": null, "steps": null}}, "missing": []}}
```
''',

'triage': '''
---
Flow: triage
Slots: source (SourceSlot, required), scope (CategorySlot, optional), count (LevelSlot, optional)
User: "What needs fixing in my Deep NLP draft?"
_Output_
```json
{{"slots": {{"source": {{"post": "Deep NLP"}}, "scope": null, "count": null}}, "missing": []}}
```
---
Flow: triage
Slots: source (SourceSlot, required), scope (CategorySlot, optional), count (LevelSlot, optional)
User: "Give me the top 3 structural issues in my latest post"
_Output_
```json
{{"slots": {{"source": null, "scope": "structure", "count": 3}}, "missing": ["source"]}}
```
---
Flow: triage
Slots: source (SourceSlot, required), scope (CategorySlot, optional), count (LevelSlot, optional)
User: "Do a full review of the Conversational AI Revolution post"
_Output_
```json
{{"slots": {{"source": {{"post": "Conversational AI Revolution"}}, "scope": "full", "count": null}}, "missing": []}}
```
''',

'calendar': '''
---
Flow: calendar
Slots: timeframe (RangeSlot, elective), count (LevelSlot, elective)
User: "Plan my content calendar for the next 4 weeks"
_Output_
```json
{{"slots": {{"timeframe": "next 4 weeks", "count": null}}, "missing": []}}
```
---
Flow: calendar
Slots: timeframe (RangeSlot, elective), count (LevelSlot, elective)
User: "I want to publish 8 posts this quarter"
_Output_
```json
{{"slots": {{"timeframe": "this quarter", "count": 8}}, "missing": []}}
```
''',

'scope': '''
---
Flow: scope
Slots: topic (ExactSlot, required)
User: "What should I research before writing about RLHF?"
_Output_
```json
{{"slots": {{"topic": "RLHF"}}, "missing": []}}
```
---
Flow: scope
Slots: topic (ExactSlot, required)
User: "Scope out a post on synthetic data generation"
_Output_
```json
{{"slots": {{"topic": "synthetic data generation"}}, "missing": []}}
```
''',

'digest': '''
---
Flow: digest
Slots: theme (ExactSlot, required), part_count (LevelSlot, optional)
User: "Plan a 5-part series on the history of NLP"
_Output_
```json
{{"slots": {{"theme": "history of NLP", "part_count": 5}}, "missing": []}}
```
---
Flow: digest
Slots: theme (ExactSlot, required), part_count (LevelSlot, optional)
User: "I want to do a blog series about building recommendation systems"
_Output_
```json
{{"slots": {{"theme": "building recommendation systems", "part_count": null}}, "missing": []}}
```
---
Flow: digest
Slots: theme (ExactSlot, required), part_count (LevelSlot, optional)
User: "Split my deep learning overview into a multi-part series, maybe 3 parts"
_Output_
```json
{{"slots": {{"theme": "deep learning overview", "part_count": 3}}, "missing": []}}
```
''',

'remember': '''
---
Flow: remember
Slots: key (ExactSlot, elective), scope (CategorySlot, elective)
User: "Remember that I prefer technical tone for all tutorial posts"
_Output_
```json
{{"slots": {{"key": "technical tone for tutorials", "scope": "user"}}, "missing": []}}
```
---
Flow: remember
Slots: key (ExactSlot, elective), scope (CategorySlot, elective)
User: "Keep in mind we're targeting the methods section for this session"
_Output_
```json
{{"slots": {{"key": "targeting methods section", "scope": "session"}}, "missing": []}}
```
''',

}
