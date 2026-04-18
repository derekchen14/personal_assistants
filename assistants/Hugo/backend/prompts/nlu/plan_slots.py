PROMPTS = {
    'blueprint': {
        'instructions': 'Plan the full post creation workflow from idea to publication — orchestrates Research, Draft, Revise, and Publish into a sequenced checklist.',
        'rules': '''- topic (optional): What the post will be about. Only extract if explicitly mentioned.
- steps (optional): User-defined workflow steps as a ChecklistSlot. Each item's "name" is a workflow phase (e.g., "Research", "Outline", "Draft").''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Plan out a full post on retrieval-augmented generation from idea to publish"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "topic": "retrieval-augmented generation",
    "steps": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Blueprint a post about MLOps: research, outline, draft, review, publish"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "topic": "MLOps",
    "steps": [
      {
        "name": "Research",
        "description": "",
        "checked": false
      },
      {
        "name": "Outline",
        "description": "",
        "checked": false
      },
      {
        "name": "Draft",
        "description": "",
        "checked": false
      },
      {
        "name": "Review",
        "description": "",
        "checked": false
      },
      {
        "name": "Publish",
        "description": "",
        "checked": false
      }
    ]
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Help me plan my next post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "topic": null,
    "steps": null
  }
}
```
</positive_example>''',
    },
    'triage': {
        'instructions': 'Examine a draft and prioritize revision tasks — which sections need rework, polish, or restructuring.',
        'rules': '''- source (required): The draft to examine.
- scope (optional): Which dimension to focus on. Choose from: content, structure, style, seo, full.
- count (optional): Maximum number of issues to surface. Only extract if the user states a specific number.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What needs fixing in my Deep NLP draft?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Deep NLP"
    },
    "scope": null,
    "count": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Give me the top 3 structural issues in my latest post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": null,
    "scope": "structure",
    "count": 3
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Do a full review of the Conversational AI Revolution post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Conversational AI Revolution"
    },
    "scope": "full",
    "count": null
  }
}
```
</positive_example>''',
    },
    'calendar': {
        'instructions': 'Plan a publishing schedule over weeks or months — topics to draft, target dates, posting cadence.',
        'rules': '''- timeframe (elective): The period to plan over. Pass the raw expression (e.g., "next 4 weeks", "this quarter").
- count (elective): How many posts to target in the period.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Plan my content calendar for the next 4 weeks"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "timeframe": "next 4 weeks",
    "count": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to publish 8 posts this quarter"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "timeframe": "this quarter",
    "count": 8
  }
}
```
</positive_example>''',
    },
    'scope': {
        'instructions': 'Define what to research before writing — information to gather, posts to reference, questions to answer.',
        'rules': '- topic (required): The subject to research.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What should I research before writing about RLHF?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "topic": "RLHF"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Scope out a post on synthetic data generation"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "topic": "synthetic data generation"
  }
}
```
</positive_example>''',
    },
    'digest': {
        'instructions': 'Split a broad theme into a multi-part blog series — installments, narrative arc, subtopics per part.',
        'rules': '''- theme (required): The broad theme of the series.
- part_count (optional): How many installments. Only extract if the user specifies a number.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Plan a 5-part series on the history of NLP"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "theme": "history of NLP",
    "part_count": 5
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "I want to do a blog series about building recommendation systems"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "theme": "building recommendation systems",
    "part_count": null
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Split my deep learning overview into a multi-part series, maybe 3 parts"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "theme": "deep learning overview",
    "part_count": 3
  }
}
```
</positive_example>''',
    },
    'remember': {
        'instructions': 'Route a memory operation — determine whether to store (L1 session), save as preference (L2), or retrieve from knowledge (L3).',
        'rules': '''- key (elective): What to remember or look up.
- scope (elective): Where to store or retrieve. Choose from: session (current session only), user (persistent preferences), global (business knowledge).''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Remember that I prefer technical tone for all tutorial posts"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "key": "technical tone for tutorials",
    "scope": "user"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Keep in mind we're targeting the methods section for this session"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "key": "targeting methods section",
    "scope": "session"
  }
}
```
</positive_example>''',
    },
}
