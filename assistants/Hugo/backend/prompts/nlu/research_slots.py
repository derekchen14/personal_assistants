INSTRUCTIONS = {

'browse': (
    'Goal: Browse available topics, notes, ideas, and content gaps. '
    'Excludes existing posts and drafts (use find for those).\n\n'
    'Slots:\n'
    '- category (optional): Narrows results to one content type. '
    'Only extract if the user explicitly names a category.'
),

'summarize': (
    'Goal: Condense a post into a short paragraph capturing its core argument, '
    'target audience, and key takeaways.\n\n'
    'Slots:\n'
    '- source (required): The post to summarize.\n'
    '- length (optional): Max sentence count for the summary. '
    'Only extract if the user states a specific number.'
),

'check': (
    'Goal: Show technical metadata for a post — status (draft/scheduled/published), '
    'dates, category tags, channels, featured image flag.\n\n'
    'Slots:\n'
    '- source (optional): A specific post to check. If omitted, shows an overview of all drafts.'
),

'inspect': (
    'Goal: Report numeric content metrics — word count, section count, reading time, '
    'image count, link count, or file size.\n\n'
    'Slots:\n'
    '- source (required): The post to measure.\n'
    '- aspect (optional): Limits to a single metric. Map user phrases: '
    '"how long" → word_count, "reading time" → time_to_read, '
    '"how many sections" → num_sections.\n'
    '- threshold (optional): A numeric cutoff to compare against '
    '(e.g., "under 10 minutes" → 10). Only extract if the user states a boundary.'
),

'find': (
    'Goal: Search existing posts and drafts by keyword — returns titles, '
    'excerpts, and publication dates.\n\n'
    'Slots:\n'
    '- query (required): The search term. Extract the core topic phrase, '
    'not the full utterance.\n'
    '- count (optional): Max results to return. '
    'Only extract if the user states a specific number.'
),

'compare': (
    'Goal: Compare style or structure across two or more posts — sentence length, '
    'paragraph density, heading patterns, vocabulary.\n\n'
    'Slots:\n'
    '- source (required): Needs at least 2 post references. '
    'Return as a list of entity dicts, one per post.'
),

'diff': (
    'Goal: Show what changed between two versions of a post or section — '
    'additions, deletions, and modifications.\n\n'
    'Slots:\n'
    '- source (required): The post (and optionally section) to diff.\n'
    '- lookback (elective): How many versions back to compare. '
    '"Last revision" → 1, "two versions ago" → 2. '
    'Use this when the user specifies a numeric distance.\n'
    '- mapping (elective): Named version comparison as key-value pairs '
    '(e.g., {{"draft": "published"}}). Use this when the user names '
    'specific stages rather than a numeric lookback. '
    'Only one of lookback or mapping should be filled.'
),

}


EXEMPLARS = {

'browse': '''
---
Flow: browse
Slots: category (CategorySlot, optional)
User: "What topics have I been writing about lately?"
_Output_
```json
{{"slots": {{"category": null}}, "missing": []}}
```
---
Flow: browse
Slots: category (CategorySlot, optional)
User: "Show me tutorial ideas I haven't explored yet"
_Output_
```json
{{"slots": {{"category": "tutorial"}}, "missing": []}}
```
''',

'summarize': '''
---
Flow: summarize
Slots: source (SourceSlot, required), length (LevelSlot, optional)
User: "Give me a quick summary of my Regularization post"
_Output_
```json
{{"slots": {{"source": {{"post": "Regularization"}}, "length": null}}, "missing": []}}
```
---
Flow: summarize
Slots: source (SourceSlot, required), length (LevelSlot, optional)
User: "Summarize the attention mechanism draft in 2 sentences"
_Output_
```json
{{"slots": {{"source": {{"post": "attention mechanism"}}, "length": 2}}, "missing": []}}
```
''',

'check': '''
---
Flow: check
Slots: source (SourceSlot, optional)
User: "What's the status of my EMNLP 2020 Highlights post?"
_Output_
```json
{{"slots": {{"source": {{"post": "EMNLP 2020 Highlights"}}}}, "missing": []}}
```
---
Flow: check
Slots: source (SourceSlot, optional)
User: "Which of my drafts are scheduled?"
_Output_
```json
{{"slots": {{"source": null}}, "missing": []}}
```
''',

'inspect': '''
---
Flow: inspect
Slots: source (SourceSlot, required), aspect (CategorySlot, optional), threshold (ScoreSlot, optional)
User: "How long is my Deep NLP post?"
_Output_
```json
{{"slots": {{"source": {{"post": "Deep NLP"}}, "aspect": "word_count", "threshold": null}}, "missing": []}}
```
---
Flow: inspect
Slots: source (SourceSlot, required), aspect (CategorySlot, optional), threshold (ScoreSlot, optional)
User: "Check if the reading time on my latest draft is under 10 minutes"
_Output_
```json
{{"slots": {{"source": null, "aspect": "time_to_read", "threshold": 10}}, "missing": ["source"]}}
```
---
Flow: inspect
Slots: source (SourceSlot, required), aspect (CategorySlot, optional), threshold (ScoreSlot, optional)
User: "Give me the full metrics on the Conversational AI Revolution post"
_Output_
```json
{{"slots": {{"source": {{"post": "Conversational AI Revolution"}}, "aspect": null, "threshold": null}}, "missing": []}}
```
''',

'find': '''
---
Flow: find
Slots: query (ExactSlot, required), count (LevelSlot, optional)
User: "find my posts about machine learning"
_Output_
```json
{{"slots": {{"query": "machine learning", "count": null}}, "missing": []}}
```
---
Flow: find
Slots: query (ExactSlot, required), count (LevelSlot, optional)
User: "search for anything I wrote about distributed training"
_Output_
```json
{{"slots": {{"query": "distributed training", "count": null}}, "missing": []}}
```
---
Flow: find
Slots: query (ExactSlot, required), count (LevelSlot, optional)
User: "show me 5 posts about attention mechanisms"
_Output_
```json
{{"slots": {{"query": "attention mechanisms", "count": 5}}, "missing": []}}
```
''',

'compare': '''
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
''',

'diff': '''
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
''',

}
