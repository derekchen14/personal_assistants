INSTRUCTIONS = {

'rework': (
    'Goal: Major revision of draft content — restructure arguments, replace weak sections, '
    'address reviewer comments. Scope: an entire post or a full section.\n\n'
    'Slots:\n'
    '- source (required): The post or section to rework.\n'
    '- remove (optional): A specific piece to cut during the rework. '
    'Only extract if the user explicitly says to drop, remove, or cut something.\n'
    '- context (elective): The user\'s reasoning or critique — '
    'what\'s wrong, what to improve. '
    '"Sounds too textbook-ish" or "the argument is weak in the middle" goes here.'
),

'polish': (
    'Goal: Fine editing of a specific paragraph or sentence — word choice, '
    'transitions, and flow. Scope: within a single paragraph, not the whole post.\n\n'
    'Slots:\n'
    '- source (required): The paragraph or section to polish. '
    'Include the section name in "sec".\n'
    '- style_notes (optional): Specific direction like "punchier", "shorter", '
    '"more active voice". Only extract if explicitly stated.\n'
    '- image (optional): For polishing an image caption or alt text.'
),

'tone': (
    'Goal: Shift the register across the entire post. '
    'Options: formal, casual, technical, academic, witty, natural.\n\n'
    'Slots:\n'
    '- source (required): The post to restyle.\n'
    '- custom_tone (elective): A user-described tone NOT in the preset list '
    '(e.g., "dry, academic register", "sardonic"). Use when no single preset fits.\n'
    '- chosen_tone (elective): One of the preset tones. '
    'Map synonyms: "conversational" → casual, "professional" → formal, '
    '"laid back" → casual. Only ONE of custom_tone or chosen_tone should be filled.'
),

'audit': (
    'Goal: Check that the post sounds like the user rather than AI — '
    'compare voice, terminology, and style against previous posts.\n\n'
    'Slots:\n'
    '- source (required): The post or section to audit.\n'
    '- reference_count (optional): How many of the user\'s older posts to compare against. '
    'Only extract if the user specifies a number.\n'
    '- threshold (required): Confidence threshold (0 to 1) for flagging AI-sounding content. '
    '"Over 40%%" → 0.4, "above 0.3" → 0.3. If missing, add to the "missing" list.'
),

'simplify': (
    'Goal: Reduce complexity — shorten paragraphs, simplify sentence structure, '
    'remove redundancy. Can target text or an image.\n\n'
    'Slots:\n'
    '- source (elective): The section or note to simplify. '
    'At least one of source or image should be present.\n'
    '- image (elective): An image to simplify or remove.'
),

'remove': (
    'Goal: Delete content — a section, draft, note, paragraph, or image.\n\n'
    'Slots:\n'
    '- source (elective): What to delete. Include post title and section as applicable.\n'
    '- image (elective): A specific image to remove.\n'
    '- type (required): What kind of content is being removed. '
    'Choose from: post, draft, section, paragraph, note, image. '
    '"Delete the draft" → draft; "remove the conclusion section" → section.'
),

'tidy': (
    'Goal: Normalize structural formatting — heading hierarchy, list indentation, '
    'paragraph spacing, whitespace. Does not change wording.\n\n'
    'Slots:\n'
    '- source (required): The post to clean up.\n'
    '- settings (required): Key-value pairs describing what to fix. '
    'Parse user instructions into structured pairs: '
    '"normalize headings, use h2" → {{"headings": "h2", "spacing": "normalize"}}. '
    'Vague requests like "clean up formatting" → {{"task": "formatting"}}.\n'
    '- image (optional): For tidying image alignment or sizing.'
),

}


EXEMPLARS = {

'rework': '''
---
Flow: rework
Slots: source (SourceSlot, required), remove (RemovalSlot, optional), context (FreeTextSlot, elective)
User: "The Components of Dialogue Systems draft needs a full rewrite"
_Output_
```json
{{"slots": {{"source": {{"post": "Components of Dialogue Systems"}}, "remove": null, "context": null}}, "missing": []}}
```
---
Flow: rework
Slots: source (SourceSlot, required), remove (RemovalSlot, optional), context (FreeTextSlot, elective)
User: "Rework the async communication section in my remote work post — drop the anecdote about Slack"
_Output_
```json
{{"slots": {{"source": {{"post": "remote work", "sec": "async communication"}}, "remove": "the anecdote about Slack", "context": null}}, "missing": []}}
```
---
Flow: rework
Slots: source (SourceSlot, required), remove (RemovalSlot, optional), context (FreeTextSlot, elective)
User: "Revise the introduction, it sounds too much like a textbook"
_Output_
```json
{{"slots": {{"source": {{"sec": "introduction"}}, "remove": null, "context": "sounds too much like a textbook"}}, "missing": ["source"]}}
```
''',

'polish': '''
---
Flow: polish
Slots: source (SourceSlot, required), style_notes (FreeTextSlot, optional), image (ImageSlot, optional)
User: "Tighten up the opening paragraph of my Deep NLP post"
_Output_
```json
{{"slots": {{"source": {{"post": "Deep NLP", "sec": "opening"}}, "style_notes": null, "image": null}}, "missing": []}}
```
---
Flow: polish
Slots: source (SourceSlot, required), style_notes (FreeTextSlot, optional), image (ImageSlot, optional)
User: "Polish the conclusion — make it punchier and shorter"
_Output_
```json
{{"slots": {{"source": {{"sec": "conclusion"}}, "style_notes": "punchier and shorter", "image": null}}, "missing": ["source"]}}
```
''',

'tone': '''
---
Flow: tone
Slots: source (SourceSlot, required), custom_tone (ExactSlot, elective), chosen_tone (CategorySlot, elective)
User: "Make the tone of my ambiguity post more conversational"
_Output_
```json
{{"slots": {{"source": {{"post": "ambiguity"}}, "custom_tone": null, "chosen_tone": "casual"}}, "missing": []}}
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
''',

'audit': '''
---
Flow: audit
Slots: source (SourceSlot, required), reference_count (LevelSlot, optional), threshold (ProbabilitySlot, required)
User: "Audit the Thailand travel post — flag anything over 40% AI-sounding"
_Output_
```json
{{"slots": {{"source": {{"post": "Thailand travel"}}, "reference_count": null, "threshold": 0.4}}, "missing": []}}
```
---
Flow: audit
Slots: source (SourceSlot, required), reference_count (LevelSlot, optional), threshold (ProbabilitySlot, required)
User: "Check if this post matches my usual voice, compare against 3 of my older posts"
_Output_
```json
{{"slots": {{"source": null, "reference_count": 3, "threshold": null}}, "missing": ["source", "threshold"]}}
```
---
Flow: audit
Slots: source (SourceSlot, required), reference_count (LevelSlot, optional), threshold (ProbabilitySlot, required)
User: "Run a style audit on the conclusion of my ML paper"
_Output_
```json
{{"slots": {{"source": {{"post": "ML paper", "sec": "conclusion"}}, "reference_count": null, "threshold": null}}, "missing": ["threshold"]}}
```
''',

'simplify': '''
---
Flow: simplify
Slots: source (SourceSlot, elective), image (ImageSlot, elective)
User: "Simplify the methodology section in my NLP survey post"
_Output_
```json
{{"slots": {{"source": {{"post": "NLP survey", "sec": "methodology"}}, "image": null}}, "missing": []}}
```
---
Flow: simplify
Slots: source (SourceSlot, elective), image (ImageSlot, elective)
User: "The hero image on my latest draft is too busy — simplify it"
_Output_
```json
{{"slots": {{"source": null, "image": {{"type": "hero", "description": "too busy"}}}}, "missing": []}}
```
''',

'remove': '''
---
Flow: remove
Slots: source (SourceSlot, elective), image (ImageSlot, elective), type (CategorySlot, required)
User: "Delete the crypto investing draft"
_Output_
```json
{{"slots": {{"source": {{"post": "crypto investing"}}, "image": null, "type": "draft"}}, "missing": []}}
```
---
Flow: remove
Slots: source (SourceSlot, elective), image (ImageSlot, elective), type (CategorySlot, required)
User: "Remove the conclusion section from my ML post"
_Output_
```json
{{"slots": {{"source": {{"post": "ML", "sec": "conclusion"}}, "image": null, "type": "section"}}, "missing": []}}
```
''',

'tidy': '''
---
Flow: tidy
Slots: source (SourceSlot, required), settings (DictionarySlot, required), image (ImageSlot, optional)
User: "Clean up the formatting on my Thailand travel post"
_Output_
```json
{{"slots": {{"source": {{"post": "Thailand travel"}}, "settings": {{"task": "formatting"}}, "image": null}}, "missing": []}}
```
---
Flow: tidy
Slots: source (SourceSlot, required), settings (DictionarySlot, required), image (ImageSlot, optional)
User: "Normalize headings and spacing across EMNLP 2020 Highlights, use h2 for sections"
_Output_
```json
{{"slots": {{"source": {{"post": "EMNLP 2020 Highlights"}}, "settings": {{"headings": "h2", "spacing": "normalize"}}, "image": null}}, "missing": []}}
```
---
Flow: tidy
Slots: source (SourceSlot, required), settings (DictionarySlot, required), image (ImageSlot, optional)
User: "fix the indentation and bullet points in my API guide"
_Output_
```json
{{"slots": {{"source": {{"post": "API guide"}}, "settings": {{"indentation": "fix", "bullet_points": "fix"}}, "image": null}}, "missing": []}}
```
''',

}
