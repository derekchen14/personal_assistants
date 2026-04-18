PROMPTS = {
    'rework': {
        'instructions': 'Major revision of draft content — restructure arguments, replace weak sections, address reviewer comments. Scope: an entire post or a full section.',
        'rules': '''- source (required): The post or section to rework.
- remove (optional): A specific piece to cut during the rework. Only extract if the user explicitly says to drop, remove, or cut something.
- context (elective): The user's reasoning or critique — what's wrong, what to improve. "Sounds too textbook-ish" or "the argument is weak in the middle" goes here.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "The Components of Dialogue Systems draft needs a full rewrite"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Components of Dialogue Systems"
    },
    "remove": null,
    "context": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Rework the async communication section in my remote work post — drop the anecdote about Slack"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "remote work",
      "sec": "async communication"
    },
    "remove": "the anecdote about Slack",
    "context": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Revise the introduction, it sounds too much like a textbook"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "sec": "introduction"
    },
    "remove": null,
    "context": "sounds too much like a textbook"
  }
}
```
</positive_example>''',
    },
    'polish': {
        'instructions': 'Fine editing of a specific paragraph or sentence — word choice, transitions, and flow. Scope: within a single paragraph, not the whole post.',
        'rules': '''- source (required): The paragraph or section to polish. Include the section name in "sec".
- style_notes (optional): Specific direction like "punchier", "shorter", "more active voice". Only extract if explicitly stated.
- image (optional): For polishing an image caption or alt text.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Tighten up the opening paragraph of my Deep NLP post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Deep NLP",
      "sec": "opening"
    },
    "style_notes": null,
    "image": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Polish the conclusion — make it punchier and shorter"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "sec": "conclusion"
    },
    "style_notes": "punchier and shorter",
    "image": null
  }
}
```
</positive_example>''',
    },
    'tone': {
        'instructions': 'Shift the register across the entire post. Options: formal, casual, technical, academic, witty, natural.',
        'rules': '''- source (required): The post to restyle.
- custom_tone (elective): A user-described tone NOT in the preset list (e.g., "dry, academic register", "sardonic"). Use when no single preset fits.
- chosen_tone (elective): One of the preset tones. Map synonyms: "conversational" → casual, "professional" → formal, "laid back" → casual. Only ONE of custom_tone or chosen_tone should be filled.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Make the tone of my ambiguity post more conversational"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "ambiguity"
    },
    "custom_tone": null,
    "chosen_tone": "casual"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Shift History of Seq2Seq to a dry, academic register"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "History of Seq2Seq"
    },
    "custom_tone": "dry, academic",
    "chosen_tone": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "make it more casual and friendly"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "custom_tone": null,
    "chosen_tone": "casual"
  }
}
```
</positive_example>''',
    },
    'audit': {
        'instructions': 'Check that the post sounds like the user rather than AI — compare voice, terminology, and style against previous posts.',
        'rules': '''- source (required): The post or section to audit.
- reference_count (optional): How many of the user's older posts to compare against. Only extract if the user specifies a number.
- threshold (required): Confidence threshold (0 to 1) for flagging AI-sounding content. "Over 40%%" → 0.4, "above 0.3" → 0.3. If missing, add to the "missing" list.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Audit the Thailand travel post — flag anything over 40% AI-sounding"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Thailand travel"
    },
    "reference_count": null,
    "threshold": 0.4
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Check if this post matches my usual voice, compare against 3 of my older posts"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "reference_count": 3,
    "threshold": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Run a style audit on the conclusion of my ML paper"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "ML paper",
      "sec": "conclusion"
    },
    "reference_count": null,
    "threshold": null
  }
}
```
</positive_example>''',
    },
    'simplify': {
        'instructions': 'Reduce complexity — shorten paragraphs, simplify sentence structure, remove redundancy. Can target text or an image.',
        'rules': '''- source (elective): The section or note to simplify. At least one of source or image should be present.
- image (elective): An image to simplify or remove.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Simplify the methodology section in my NLP survey post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "NLP survey",
      "sec": "methodology"
    },
    "image": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "The hero image on my latest draft is too busy — simplify it"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "image": {
      "type": "hero",
      "description": "too busy"
    }
  }
}
```
</positive_example>''',
    },
    'remove': {
        'instructions': 'Delete content — a section, draft, note, paragraph, or image.',
        'rules': '''- source (elective): What to delete. Include post title and section as applicable.
- image (elective): A specific image to remove.
- type (required): What kind of content is being removed. Choose from: post, draft, section, paragraph, note, image. "Delete the draft" → draft; "remove the conclusion section" → section.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Delete the crypto investing draft"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "crypto investing"
    },
    "image": null,
    "type": "draft"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Remove the conclusion section from my ML post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "ML",
      "sec": "conclusion"
    },
    "image": null,
    "type": "section"
  }
}
```
</positive_example>''',
    },
    'tidy': {
        'instructions': 'Normalize structural formatting — heading hierarchy, list indentation, paragraph spacing, whitespace. Does not change wording.',
        'rules': '''- source (required): The post to clean up.
- settings (required): Key-value pairs describing what to fix. Parse user instructions into structured pairs: "normalize headings, use h2" → {"headings": "h2", "spacing": "normalize"}. Vague requests like "clean up formatting" → {"task": "formatting"}.
- image (optional): For tidying image alignment or sizing.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Clean up the formatting on my Thailand travel post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Thailand travel"
    },
    "settings": {
      "task": "formatting"
    },
    "image": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Normalize headings and spacing across EMNLP 2020 Highlights, use h2 for sections"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "EMNLP 2020 Highlights"
    },
    "settings": {
      "headings": "h2",
      "spacing": "normalize"
    },
    "image": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "fix the indentation and bullet points in my API guide"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "API guide"
    },
    "settings": {
      "indentation": "fix",
      "bullet_points": "fix"
    },
    "image": null
  }
}
```
</positive_example>''',
    },
}
