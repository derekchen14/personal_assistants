PROMPTS = {
    'recap': {
        'instructions': 'Read back facts from the current session scratchpad (L1) — decisions, constraints, or references stored earlier.',
        'rules': '- key (optional): A specific topic to recall. If omitted, returns everything from the session.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What did we decide about the post topic earlier?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "key": "post topic"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Recap everything from this session"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "key": null
  }
}
```
</positive_example>''',
    },
    'store': {
        'instructions': 'Save a key-value pair to the session scratchpad (L1) for later use in this session.',
        'rules': '- entry (required): A dict with "key" and "value". Parse the statement into a structured pair: "focus on introduction" → {"key": "focus", "value": "introduction"}.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Note that the user wants to focus on the introduction next"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "entry": {
      "key": "focus",
      "value": "introduction"
    }
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Save that the target audience is intermediate ML practitioners"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "entry": {
      "key": "target_audience",
      "value": "intermediate ML practitioners"
    }
  }
}
```
</positive_example>''',
    },
    'recall': {
        'instructions': 'Look up persistent user preferences from long-term memory (L2) — default tone, word count targets, stylistic rules.',
        'rules': '- key (optional): Which preference to look up. If omitted, returns all saved preferences.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What's my preferred default tone?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "key": "default tone"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Look up my writing preferences"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "key": null
  }
}
```
</positive_example>''',
    },
    'retrieve': {
        'instructions': 'Fetch unvetted business context from knowledge memory (L3) — style guides, domain knowledge, reference documents.',
        'rules': '''- topic (required): What to retrieve — the subject area or document type.
- context (optional): Narrows the search scope (e.g., "for technical posts", "about SEO").''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Pull up our style guide for technical posts"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "topic": "style guide",
    "context": "technical posts"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Get the brand voice guidelines"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "topic": "brand voice guidelines",
    "context": null
  }
}
```
</positive_example>''',
    },
    'search': {
        'instructions': 'Look up vetted FAQs and curated editorial guidelines — the unstructured equivalent of a style manual.',
        'rules': '- query (required): The search term — extract the core phrase.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Search our editorial guidelines for image requirements"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "query": "image requirements"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Look up our FAQ on heading style"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "query": "heading style"
  }
}
```
</positive_example>''',
    },
    'reference': {
        'instructions': 'Dictionary and thesaurus lookup — definitions, synonyms, antonyms, or usage examples.',
        'rules': '- word (required): The word to look up. Extract just the target word.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What's a synonym for important?"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "word": "important"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Give me formal alternatives to the word good"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "word": "good"
  }
}
```
</positive_example>''',
    },
    'study': {
        'instructions': 'Load a previous post into agent context to match voice, structure, or vocabulary patterns when writing new content.',
        'rules': '''- source (required): Which post to load.
- scope (optional): What aspect to focus on. Choose from: voice, structure, vocabulary, full.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Load my Ambiguity is the Bottleneck post to match its voice"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "Ambiguity is the Bottleneck"
    },
    "scope": "voice"
  }
}
```
</positive_example>

<positive_example>
## Conversation History

User: "Study the structure of my 100 Research Papers post"
## Output

```json
{
  "reasoning": "(auto-ported from legacy exemplar)",
  "slots": {
    "source": {
      "post": "100 Research Papers"
    },
    "scope": "structure"
  }
}
```
</positive_example>''',
    },
}
