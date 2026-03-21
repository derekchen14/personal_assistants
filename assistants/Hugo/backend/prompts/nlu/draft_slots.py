INSTRUCTIONS = {

'brainstorm': (
    'Goal: Generate ideas, angles, hooks, or new perspectives for a topic — '
    'can be open-ended or anchored to an existing post.\n\n'
    'Slots:\n'
    '- source (elective): An existing post or section to brainstorm about. '
    'When present, ideas are grounded to that content.\n'
    '- topic (elective): A topic or phrase to brainstorm around. '
    'Used when no existing post is referenced.\n'
    '- ideas (optional): Agent-generated options — '
    'not typically filled during slot extraction.'
),

'create': (
    'Goal: Initialize a new post record with title and type. '
    'Does not generate content (use outline or compose for that).\n\n'
    'Slots:\n'
    '- title (required): A clean Proper Case title for the new post. '
    'Distill the user\'s description into a concise title '
    '(e.g., "write about how transformers work" → "How Transformers Work").\n'
    '- type (required): "draft" for a formal article, "note" for a shorter snippet. '
    'Default to "draft" when the user says "post" or "article".\n'
    '- topic (optional): A longer description of what the post is about. '
    'Only extract if the user provides detail beyond just the title.'
),

'outline': (
    'Goal: Generate section headings, bullet points, estimated word counts, '
    'and reading order for a post.\n\n'
    'Slots:\n'
    '- source (required): The post to outline. Extract the post title.\n'
    '- topic (elective): A topic angle if it differs from the post title — '
    'adds context for outline generation.\n'
    '- depth (optional): Level of detail — higher means more sub-bullets per section. '
    'Only extract if the user gives a specific number.\n'
    '- sections (elective): User-provided section headings as a ChecklistSlot. '
    'Each item\'s "name" becomes the starting point of a section title. '
    'IMPORTANT: When the user lists topics to cover, headings, or sections '
    '("cover X, Y, and Z"), those go into sections — NOT into topic or instructions.'
),

'refine': (
    'Goal: Adjust an existing outline — reorder sections, add/remove subsections, '
    'incorporate feedback.\n\n'
    'Slots:\n'
    '- source (required): The post whose outline to refine.\n'
    '- feedback (elective): The user\'s critique or direction for changes '
    '(e.g., "more detail in the methods section", "trim to 4 sections").\n'
    '- steps (elective): A replacement list of section headings when the user '
    'specifies a new order explicitly. Each item is a ChecklistSlot entry.'
),

'cite': (
    'Goal: Attach a citation to a note. If a URL is provided, use it directly; '
    'otherwise search the web for a supporting source.\n\n'
    'Slots:\n'
    '- source (elective): The note to cite. This slot looks for snippet references '
    'specifically — use the "snip" entity key.\n'
    '- url (elective): A direct URL to attach. Preserve the full URL verbatim.'
),

'compose': (
    'Goal: Write a section from scratch based on instructions or an outline.\n\n'
    'Slots:\n'
    '- source (required): The post and optionally section to write for. '
    'If the user only gives a topic, the post title may match the topic.\n'
    '- steps (elective): Sub-points to cover in order, as a ChecklistSlot. '
    'When the user lists points to cover ("cover X, Y, Z"), put them here.\n'
    '- instructions (elective): Qualitative writing guidance — tone, length, '
    'angle, constraints, or stylistic direction. '
    'Descriptive text about how to write goes here, not what to write about.'
),

'add': (
    'Goal: Insert new sections into an existing post.\n\n'
    'Slots:\n'
    '- source (required): The post to add sections to.\n'
    '- steps (elective): The new sections to create. Each item\'s "name" '
    'becomes the section heading.\n'
    '- instructions (elective): Guidance for the new sections '
    '(e.g., content direction, length hints).\n'
    '- image (elective): Images to include in the new sections.\n'
    '- position (optional): Where to insert among existing sections '
    'as a 0-based index. "Right after the intro" → 1. '
    'Only extract if the user specifies placement.'
),

}


EXEMPLARS = {

'brainstorm': '''
---
Flow: brainstorm
Slots: source (SourceSlot, elective), topic (ExactSlot, elective), ideas (ProposalSlot, optional)
User: "Brainstorm some angles for a post about prompt engineering"
_Output_
```json
{{"slots": {{"source": null, "topic": "prompt engineering", "ideas": null}}, "missing": []}}
```
---
Flow: brainstorm
Slots: source (SourceSlot, elective), topic (ExactSlot, elective), ideas (ProposalSlot, optional)
User: "Give me ideas for the introduction of my transformer post"
_Output_
```json
{{"slots": {{"source": {{"post": "transformer", "sec": "introduction"}}, "topic": null, "ideas": null}}, "missing": []}}
```
---
Flow: brainstorm
Slots: source (SourceSlot, elective), topic (ExactSlot, elective), ideas (ProposalSlot, optional)
User: "What could I write about next?"
_Output_
```json
{{"slots": {{"source": null, "topic": null, "ideas": null}}, "missing": []}}
```
''',

'create': '''
---
Flow: create
Slots: title (ExactSlot, required), type (CategorySlot, required), topic (ExactSlot, optional)
User: "Let's make a new post about the wright brothers inventing flight back in the day."
_Output_
```json
{{"slots": {{"title": "The Discovery of Flight", "type": "draft", "topic": "Wright Brothers and the invention of flight"}}, "missing": []}}
```
---
Flow: create
Slots: title (ExactSlot, required), type (CategorySlot, required), topic (ExactSlot, optional)
User: "Start a note about why batch normalization helps training stability"
_Output_
```json
{{"slots": {{"title": "Batch Normalization and Training Stability", "type": "note", "topic": "why batch normalization helps training stability"}}, "missing": []}}
```
---
Flow: create
Slots: title (ExactSlot, required), type (CategorySlot, required), topic (ExactSlot, optional)
User: "Create a draft called Regularization Techniques"
_Output_
```json
{{"slots": {{"title": "Regularization Techniques", "type": "draft", "topic": null}}, "missing": []}}
```
''',

'outline': '''
---
Flow: outline
Slots: source (SourceSlot, required), topic (ExactSlot, elective), depth (LevelSlot, optional), sections (ChecklistSlot, elective)
User: "Outline a post about the Wright Brothers — cover their experiments, struggles, breakthrough, and legacy"
_Output_
```json
{{"slots": {{"source": {{"post": "The Wright Brothers"}}, "topic": null, "depth": null, "sections": [{{"name": "Their Experiments", "description": "", "checked": false}}, {{"name": "Struggles They Faced", "description": "", "checked": false}}, {{"name": "The Breakthrough", "description": "", "checked": false}}, {{"name": "Their Legacy", "description": "", "checked": false}}]}}, "missing": []}}
```
---
Flow: outline
Slots: source (SourceSlot, required), topic (ExactSlot, elective), depth (LevelSlot, optional), sections (ChecklistSlot, elective)
User: "Create an outline for my post on transfer learning"
_Output_
```json
{{"slots": {{"source": {{"post": "transfer learning"}}, "topic": "transfer learning", "depth": null, "sections": null}}, "missing": []}}
```
---
Flow: outline
Slots: source (SourceSlot, required), topic (ExactSlot, elective), depth (LevelSlot, optional), sections (ChecklistSlot, elective)
User: "Outline the discovery of flight post with sections on intro, methods, results, and conclusion"
_Output_
```json
{{"slots": {{"source": {{"post": "discovery of flight"}}, "topic": null, "depth": null, "sections": [{{"name": "Introduction", "description": "", "checked": false}}, {{"name": "Methods", "description": "", "checked": false}}, {{"name": "Results", "description": "", "checked": false}}, {{"name": "Conclusion", "description": "", "checked": false}}]}}, "missing": []}}
```
''',

'refine': '''
---
Flow: refine
Slots: source (SourceSlot, required), feedback (FreeTextSlot, elective), steps (ChecklistSlot, elective)
User: "The outline for my discovery of flight post needs more detail in the methods section"
_Output_
```json
{{"slots": {{"source": {{"post": "discovery of flight"}}, "feedback": "more detail in the methods section", "steps": null}}, "missing": []}}
```
---
Flow: refine
Slots: source (SourceSlot, required), feedback (FreeTextSlot, elective), steps (ChecklistSlot, elective)
User: "Reorder the outline to put background first, then experiments, then results"
_Output_
```json
{{"slots": {{"source": null, "feedback": null, "steps": [{{"name": "Background", "description": "", "checked": false}}, {{"name": "Experiments", "description": "", "checked": false}}, {{"name": "Results", "description": "", "checked": false}}]}}, "missing": ["source"]}}
```
---
Flow: refine
Slots: source (SourceSlot, required), feedback (FreeTextSlot, elective), steps (ChecklistSlot, elective)
User: "Trim the transformer post outline down to just 4 sections"
_Output_
```json
{{"slots": {{"source": {{"post": "transformer"}}, "feedback": "trim down to just 4 sections", "steps": null}}, "missing": []}}
```
''',

'cite': '''
---
Flow: cite
Slots: source (SourceSlot, elective), url (ExactSlot, elective)
User: "Add a citation to my attention mechanism note"
_Output_
```json
{{"slots": {{"source": {{"snip": "attention mechanism"}}, "url": null}}, "missing": []}}
```
---
Flow: cite
Slots: source (SourceSlot, elective), url (ExactSlot, elective)
User: "Cite https://arxiv.org/abs/1706.03762 in my transformer post"
_Output_
```json
{{"slots": {{"source": {{"post": "transformer"}}, "url": "https://arxiv.org/abs/1706.03762"}}, "missing": []}}
```
''',

'compose': '''
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
''',

'add': '''
---
Flow: add
Slots: source (SourceSlot, required), steps (ChecklistSlot, elective), instructions (FreeTextSlot, elective), image (ChecklistSlot, elective), position (PositionSlot, optional)
User: "Add a street food section to my Bangkok travel post, right after the intro"
_Output_
```json
{{"slots": {{"source": {{"post": "Bangkok travel"}}, "steps": [{{"name": "street food", "description": "", "checked": false}}], "instructions": null, "image": null, "position": 1}}, "missing": []}}
```
---
Flow: add
Slots: source (SourceSlot, required), steps (ChecklistSlot, elective), instructions (FreeTextSlot, elective), image (ChecklistSlot, elective), position (PositionSlot, optional)
User: "Add sections on evaluation metrics and future work to my ML post"
_Output_
```json
{{"slots": {{"source": {{"post": "ML"}}, "steps": [{{"name": "Evaluation Metrics", "description": "", "checked": false}}, {{"name": "Future Work", "description": "", "checked": false}}], "instructions": null, "image": null, "position": null}}, "missing": []}}
```
---
Flow: add
Slots: source (SourceSlot, required), steps (ChecklistSlot, elective), instructions (FreeTextSlot, elective), image (ChecklistSlot, elective), position (PositionSlot, optional)
User: "I need a new section on evaluation metrics"
_Output_
```json
{{"slots": {{"source": null, "steps": [{{"name": "evaluation metrics", "description": "", "checked": false}}], "instructions": null, "image": null, "position": null}}, "missing": ["source"]}}
```
''',

}
