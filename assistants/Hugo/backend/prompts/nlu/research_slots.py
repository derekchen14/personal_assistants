INSPECT_PROMPT = {
    'instructions': (
        'Report numeric content metrics for a post — word count, section count, reading time, image count, '
        'link count, or file size. Populate `aspect` when the user names a specific metric (or clearly '
        'implies one). Populate `threshold` only when the utterance expresses a comparative boundary. '
        'Descriptive or raw counts do NOT fill `threshold`.'
    ),
    'rules': (
        '1. `aspect` maps phrases to the closed option set {word_count, num_sections, time_to_read, '
        'image_count, num_links, post_size}. "How long" can match word_count, time_to_read, or post_size '
        '— leave `null` when the phrasing is ambiguous so downstream can clarify. "How many sections" → '
        'num_sections. "Stats" or "metrics" with no specific phrasing → `null`.\n'
        '2. `threshold` ONLY fills on comparative phrasing: "over X", "at least X", "more than X", "under '
        'X", "below X", "at most X". Raw counts or descriptive numbers don\'t fill it.\n'
        '3. "My post is about 1000 words" is descriptive, not comparative — `threshold=null`.\n'
        '4. When the user pairs a length framing with "is that enough?" style follow-up, the length term '
        'still maps to an aspect but the subjective follow-up does NOT provide a comparative threshold.'
    ),
    'slots': (
        '### source (required)\n\n'
        'Type: SourceSlot. The post to measure. When an active post is grounded, this slot is pre-filled '
        'and omitted from the schema above.\n\n'
        '### aspect (optional)\n\n'
        'Type: CategorySlot. Options: `word_count`, `num_sections`, `time_to_read`, `image_count`, '
        '`num_links`, `post_size`. Fill when the user names or clearly implies a specific metric.\n\n'
        '### threshold (optional)\n\n'
        'Type: ScoreSlot. Numeric boundary for comparison. Fill ONLY on comparative phrasing ("over X", '
        '"at least X", "under X"). Raw or descriptive numbers leave this `null`.'
    ),
    'examples': '''<positive_example>
## Conversation History

User: "How many words are in my reinforcement learning primer post?"
## Output

```json
{
  "reasoning": "Raw count request → aspect=word_count. No comparison phrasing → threshold empty.",
  "slots": {
    "source": {"post": "reinforcement learning primer"},
    "aspect": "word_count",
    "threshold": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Is my data augmentation post over 1500 words?"
## Output

```json
{
  "reasoning": "'Over 1500 words' is explicit comparison → threshold=1500, aspect=word_count.",
  "slots": {
    "source": {"post": "data augmentation"},
    "aspect": "word_count",
    "threshold": 1500
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "How long is my calibration post?"
## Output

```json
{
  "reasoning": "'How long' could match word_count, time_to_read, or post_size — no single metric dominates, so leave aspect empty for downstream clarification. No comparison → threshold empty.",
  "slots": {
    "source": {"post": "calibration"},
    "aspect": null,
    "threshold": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to dig into my observability traces post."
Agent: "Pulled it up — what's next?"
User: "How many sections does it have?"
## Output

```json
{
  "reasoning": "'How many sections' → aspect=num_sections. Raw count, no comparison → threshold empty. Source inherited from the prior turn's reference.",
  "slots": {
    "source": {"post": "observability traces"},
    "aspect": "num_sections",
    "threshold": null
  }
}
```
</positive_example>

<edge_case>
## Conversation History

User: "Give me stats on my batch normalization post."
## Output

```json
{
  "reasoning": "'Stats' names no specific metric from the allowed set → aspect stays empty so downstream can ask. No comparison → threshold empty.",
  "slots": {
    "source": {"post": "batch normalization"},
    "aspect": null,
    "threshold": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "My trustworthy AI post is about 1200 words — is that enough?"
## Output

```json
{
  "reasoning": "'About 1200 words' is descriptive, not comparative. 'Is that enough' is subjective. Aspect picks up word_count from the length framing, but threshold stays empty.",
  "slots": {
    "source": {"post": "trustworthy AI"},
    "aspect": "word_count",
    "threshold": null
  }
}
```
</edge_case>

<edge_case>
## Conversation History

User: "Does my cooking post have at least 3 images?"
## Output

```json
{
  "reasoning": "'At least 3' is comparison phrasing → threshold=3. 'Images' maps directly to image_count.",
  "slots": {
    "source": {"post": "cooking"},
    "aspect": "image_count",
    "threshold": 3
  }
}
```
</edge_case>''',
}


PROMPTS = {
    'inspect': INSPECT_PROMPT,
    'browse': {
        'instructions': 'Browse available topics, notes, ideas, and content gaps. Excludes existing posts and drafts (use find for those).',
        'rules': '- category (optional): Narrows results to one content type. Only extract if the user explicitly names a category.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What topics have I been writing about lately?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "category": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Show me tutorial ideas I haven't explored yet"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "category": "tutorial"
  }
}
```
</positive_example>''',
    },
    'summarize': {
        'instructions': 'Condense a post into a short paragraph capturing its core argument, target audience, and key takeaways.',
        'rules': '''- source (required): The post to summarize.
- length (optional): Max sentence count for the summary. Only extract if the user states a specific number.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Give me a quick summary of my Regularization post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Regularization"
    },
    "length": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Summarize the attention mechanism draft in 2 sentences"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "attention mechanism"
    },
    "length": 2
  }
}
```
</positive_example>''',
    },
    'check': {
        'instructions': 'Show technical metadata for a post — status (draft/scheduled/published), dates, category tags, channels, featured image flag.',
        'rules': '- source (optional): A specific post to check. If omitted, shows an overview of all drafts.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What's the status of my EMNLP 2020 Highlights post?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "EMNLP 2020 Highlights"
    }
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Which of my drafts are scheduled?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null
  }
}
```
</positive_example>''',
    },
    'find': {
        'instructions': 'Search existing posts and drafts by keyword — returns titles, excerpts, and publication dates.',
        'rules': '''- query (required): The search term. Extract the core topic phrase, not the full utterance.
- count (optional): Max results to return. Only extract if the user states a specific number.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "find my posts about machine learning"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "query": "machine learning",
    "count": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "search for anything I wrote about distributed training"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "query": "distributed training",
    "count": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "show me 5 posts about attention mechanisms"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "query": "attention mechanisms",
    "count": 5
  }
}
```
</positive_example>''',
    },
    'compare': {
        'instructions': 'Compare style or structure across two or more posts — sentence length, paragraph density, heading patterns, vocabulary.',
        'rules': '- source (required): Needs at least 2 post references. Return as a list of entity dicts, one per post.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "How does my ML as Software 2.0 draft compare to The Hype of Machine Learning?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": [
      {
        "post": "ML as Software 2.0"
      },
      {
        "post": "The Hype of Machine Learning"
      }
    ]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Compare my REST API tutorial and my GraphQL API tutorial side by side"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": [
      {
        "post": "REST API tutorial"
      },
      {
        "post": "GraphQL API tutorial"
      }
    ]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "How do those two stack up?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null
  }
}
```
</positive_example>''',
    },
    'diff': {
        'instructions': 'Show what changed between two versions of a post or section — additions, deletions, and modifications.',
        'rules': '''- source (required): The post (and optionally section) to diff.
- lookback (elective): How many versions back to compare. "Last revision" → 1, "two versions ago" → 2. Use this when the user specifies a numeric distance.
- mapping (elective): Named version comparison as key-value pairs (e.g., {"draft": "published"}). Use this when the user names specific stages rather than a numeric lookback. Only one of lookback or mapping should be filled.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What changed in Solving the Long Tail since the last revision?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Solving the Long Tail"
    },
    "lookback": 1,
    "mapping": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Show me the differences between the draft and published version of Data Augmentation"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Data Augmentation"
    },
    "lookback": null,
    "mapping": {
      "draft": "published"
    }
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Compare the current draft of my ML post against two versions ago"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "ML"
    },
    "lookback": 2,
    "mapping": null
  }
}
```
</positive_example>''',
    },
}
