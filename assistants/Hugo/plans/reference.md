# Phase 2 — Reference {139}

## Current state

`ReferenceFlow` exists at `backend/components/flow_stack/flows.py:944-957`:

```python
class ReferenceFlow(InternalParentFlow):
    flow_type = 'reference'
    dax = '{139}'
    goal = 'look up word definitions, synonyms, antonyms, or usage examples via dictionary and thesaurus; e.g., "synonym for important", "definition of ephemeral", "formal alternatives to good"'
    slots = {'target': TargetSlot(1, entity_part='word')}
    tools = []
```

`reference_policy` at `backend/modules/policies/internal.py:77-79` is a stub — it just
sets `flow.status = 'Completed'` and returns an empty frame.

## Decisions

- **Data source**: LLM-knowledge for v1. No WordNet, no WordsAPI, no NLTK install.
  Modern frontier LLMs (Claude/GPT) have reliable coverage of common English vocab.
- **Lookup categories**: definition, synonyms, antonyms, usage examples. Driven by an
  optional `category` slot (default = "all four").
- **No new tool**. Reference is a single LLM call with a structured-JSON schema. Goes
  through `self.engineer(prompt, task='skill', schema=...)`, mirroring the audit
  router's pattern.
- **Output shape** (written to scratchpad under key `'reference'`):
  ```json
  {
    "word": "important",
    "definition": "...",
    "synonyms": ["..."],
    "antonyms": ["..."],
    "examples": ["..."],
    "summary": "Synonyms for 'important' include essential, crucial, vital, ..."
  }
  ```
  `summary` is the human-readable line `chat_policy` will surface in stage
  `'post_dispatch'`.

## Implementation steps

### Step 1 — Reference prompt + schema

`backend/prompts/pex/support/converse_prompts.py` (new file or append):

```python
REFERENCE_LOOKUP_SCHEMA = {
    'type': 'object',
    'properties': {
        'word': {'type': 'string'},
        'definition': {'type': 'string'},
        'synonyms': {'type': 'array', 'items': {'type': 'string'}},
        'antonyms': {'type': 'array', 'items': {'type': 'string'}},
        'examples': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['word', 'definition', 'synonyms', 'antonyms', 'examples'],
    'additionalProperties': False,
}


def build_reference_prompt(word:str, category:str|None=None) -> str:
    """Build a dictionary/thesaurus lookup prompt for a single word.

    `category` narrows the response when set ('definition', 'synonyms', 'antonyms',
    'examples'); when None, return all four (still as full JSON, with empty arrays
    where unsupported). Empty arrays are valid — e.g. proper nouns may have no
    synonyms."""
    scope = (
        f"Focus on '{category}' but populate the other fields with concise content "
        if category else "Populate all fields "
    )
    return (
        f"Look up the word '{word}' as a dictionary and thesaurus entry. {scope}"
        "(definition: 1 sentence; synonyms/antonyms: 5-8 each, common-usage; examples: "
        "2-3 short sentences using the word naturally).\n\n"
        "Return JSON matching the schema. If the word is unknown or not standard "
        "English, return all empty fields with the original word."
    )
```

### Step 2 — Rewrite `reference_policy`

`backend/modules/policies/internal.py:77-79`:

```python
def reference_policy(self, flow, tools):
    target_slot = flow.slots['target']
    if not target_slot.check_if_filled():
        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    word = target_slot.values[0].get('word', '').strip()
    if not word:
        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    prompt = build_reference_prompt(word)
    entry = self.engineer(prompt, task='skill', schema=REFERENCE_LOOKUP_SCHEMA)

    if entry['definition']:
        summary = f"'{entry['word']}' — {entry['definition']}"
        if entry['synonyms']:
            summary += f" Synonyms: {', '.join(entry['synonyms'][:5])}."
    else:
        summary = f"No standard reference entry found for '{word}'."

    self.memory.write_scratchpad('reference', {**entry, 'summary': summary})
    flow.status = 'Completed'
    return TaskArtifact(flow.name())
```

Note: `InternalPolicy` doesn't currently have `self.engineer` injected. Add it in
`__init__`:

```python
def __init__(self, components):
    self.memory = components['memory']
    self.config = components['config']
    self.flow_stack = components['flow_stack']
    self.engineer = components['engineer']  # ← NEW
```

`engineer` is already a registered component (see `BasePolicy.__init__`), so this is
a one-line addition.

### Step 3 — Add the prompt-import

`internal.py` top imports:

```python
from backend.prompts.pex.support.converse_prompts import (
    build_reference_prompt,
    REFERENCE_LOOKUP_SCHEMA,
)
```

(If `converse_prompts.py` was already created in phase 1 for the FAQ schema, append
the reference exports there. Otherwise create it.)

## Verification

- **Free tier**: `pytest utils/tests/unit_tests.py utils/tests/test_artifacts.py` —
  must stay green. The new prompt-builder is straight-line code; no behavioral test
  needed. A schema-shape lint in `test_artifacts.py` (which already validates
  prompt/schema modules) will exercise it.
- **Manual smoke** (after phase 3): "What's a synonym for 'important'?" — should
  return a comma-separated list grounded in the LLM lookup, not a generic answer.
- **Edge case to verify**: nonsense word ("blarghnoodle") — policy should write
  `summary = "No standard reference entry found..."` and chat composes a graceful
  fallback.

## Risks

- **LLM hallucinates synonyms.** Frontier models are usually solid here, but rare
  words can produce confident-sounding wrong answers. v1 ships without validation;
  if eval shows >5% wrong-synonym rate, fall back to WordNet (NLTK,
  ~2MB on-disk).
- **Multi-word phrase queries.** "Synonyms for 'cut to the chase'" — slot extracts
  the whole phrase as a single `target.word`, prompt handles it. Should work, but
  verify in smoke.
- **Slot fill correctness.** The current `TargetSlot(1, entity_part='word')` declares
  the entity_part but NLU's slot prompt for reference doesn't exist yet — phase 3
  doesn't touch NLU because chat dispatches via `flow_stack.stackon('reference')`
  *and fills slots from the router output directly* (see `internal_flows.md` §Step 3).
  No NLU prompt change needed.
