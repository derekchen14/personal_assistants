PROMPTS = {
    'recap': {
        'instructions': 'Read back facts from the current session scratchpad (L1) — decisions, constraints, or references stored earlier. The scratchpad holds natural-language snippets, so the lookup is a free-text topic, not a structured key.',
        'rules': '- topic (optional): A free-text description of what to recall. If omitted, returns everything from the session.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What did we decide about the post topic earlier?"
## Output

```json
{
  "reasoning": "the user is asking about a prior decision around the post's topic",
  "slots": {
    "topic": ["post topic"]
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
  "reasoning": "no specific topic — return all snippets",
  "slots": {
    "topic": null
  }
}
```
</positive_example>''',
    },
    'store': {
        'instructions': 'Save a natural-language snippet to the session scratchpad (L1) for later use in this session. L1 stores reflective summaries (per memory_manager spec), not structured key-value pairs — extract the user\'s statement as a single sentence.',
        'rules': '''- target (required): The snippet to save, as a natural-language sentence. Quote/paraphrase the salient observation rather than splitting into key/value.
- origin (optional): The flow_name that produced this snippet, if the user mentions one (e.g., "from outline", "after the audit"). Usually omitted.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "Note that the user wants to focus on the introduction next"
## Output

```json
{
  "reasoning": "save the user's stated focus as a free-text snippet for L1",
  "slots": {
    "target": ["The user wants to focus on the introduction next."],
    "origin": null
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
  "reasoning": "narrative snippet about audience — no producing flow named",
  "slots": {
    "target": ["The target audience is intermediate ML practitioners."],
    "origin": null
  }
}
```
</positive_example>''',
    },
    'recall': {
        'instructions': 'Look up persistent user preferences from long-term memory (L2) — default tone, word count targets, stylistic rules. L2 keys are short specific words (e.g., "default_tone", "word_count_target"); use `target` for the key. The `preference` slot captures any free-text descriptor when the user is fuzzy ("my style preferences").',
        'rules': '''- target (required): The specific preference key to look up. A short word or phrase (e.g., "default tone", "post length"). If the user is fuzzy and doesn't name a key, leave null and rely on `preference`.
- preference (optional): Free-text description of what the user is asking for, when the key is not specific.''',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What's my preferred default tone?"
## Output

```json
{
  "reasoning": "specific preference key named",
  "slots": {
    "target": [{"snip": "default tone"}],
    "preference": null
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
  "reasoning": "fuzzy ask — no specific key, use preference for free-text",
  "slots": {
    "target": null,
    "preference": ["writing preferences"]
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
        'instructions': 'Dictionary and thesaurus lookup — definitions, synonyms, antonyms, or usage examples. The word being looked up is grounded as `target`; store the bare string in the `snip` field.',
        'rules': '- target (required): The word to look up. Emit as a single-element list with the word in `snip`.',
        'slots': '',
        'examples': '''<positive_example>
## Conversation History

User: "What's a synonym for important?"
## Output

```json
{
  "reasoning": "lookup target = important",
  "slots": {
    "target": [{"snip": "important"}]
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
  "reasoning": "lookup target = good",
  "slots": {
    "target": [{"snip": "good"}]
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
