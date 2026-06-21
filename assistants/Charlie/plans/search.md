# Phase 1 — Search {189}

## Current state

`SearchFlow` exists at `backend/components/flow_stack/flows.py:929-942`:

```python
class SearchFlow(InternalParentFlow):
    flow_type = 'search'
    dax = '{189}'
    goal = 'look up vetted FAQs and curated editorial guidelines; most often used to answer questions about Hugo'
    slots = {'query': ExactSlot()}
    tools = ['find_posts']
```

`search_policy` lives at `backend/modules/policies/internal.py:67-75`. It does the
*wrong* thing today: it calls `find_posts`, which searches the user's blog-post directory
(drafts/posts/notes), not the FAQ corpus. The result is written to scratchpad keyed
`f'search:{query}'`, which is harmless but useless.

There is no FAQ retrieval infrastructure. `database/guides/faq_guide.md` has 2 markdown
entries — too few and the wrong shape for retrieval.

The Soleda/Dana JSON at `~/Documents/soleda/Soleda/database/faq_data/faq_answers.json`
is a list of strings (no question key, no tags). Useful as a *category reference* — that
project's FAQ themes ("what can you do?", "who made you?", "how do you handle privacy?")
are exactly the categories Hugo needs.

## Decisions

- **Corpus shape**: JSON `[{question, answer, tags}]`. `tags` are short topic labels
  (e.g. `["capabilities", "scope"]`) used for both retrieval narrowing and authoring
  organization. No embedding for v1.
- **Retrieval**: BM25-style or simple keyword overlap is overkill for a corpus of
  ~20-50 FAQs. **Use LLM-rerank**: pass the entire corpus + user query in a single
  prompt and ask for the top 1-3 matches with confidence scores. Cheap (corpus fits
  in <2k tokens) and zero infrastructure.
- **Tool name**: `search_faqs(query, top_k=3) -> {matches: [{question, answer, score}]}`.
  Distinct name avoids confusion with `find_posts`.
- **Service placement**: small dedicated `FAQService` at
  `backend/utilities/faq_service.py` — loads JSON on init, exposes `search(query, top_k)`.
  Keeps `PostService` and `ContentService` clean. (One narrow injection per CLAUDE.md
  guidance: only `InternalPolicy` needs it.)
- **Corpus location**: `database/faq_data/faqs.json` (mkdir-on-init). Mirrors the Soleda
  convention.

## Implementation steps

### Step 1 — Author the corpus

`database/faq_data/faqs.json` (new). Seed with ~12 entries answering Hugo-specific
versions of the Soleda categories:

```json
[
  {
    "question": "What can Hugo do for me?",
    "answer": "Hugo is a writing assistant for blog posts. It helps you outline, draft, refine, audit, polish, and publish posts across channels. Ask in plain language — Hugo will pick the right action.",
    "tags": ["capabilities", "overview"]
  },
  {
    "question": "Who built Hugo?",
    "answer": "Hugo is part of the Soleda assistant family — a virtual-assistant platform whose mission is to make tedious work simpler with modern AI.",
    "tags": ["origin", "team"]
  },
  ...
]
```

Categories to cover in the seed (one or two FAQs each):
- Capabilities & scope (what flows exist, what does each do at a high level)
- Origin / team (who built it, why)
- Privacy & data handling (what stays local, what's sent to LLMs)
- Channels & publishing (which platforms are supported, draft → publish flow)
- Voice & style (how does Hugo match the user's voice — pointer to Audit)
- Pricing / availability (placeholder if not decided)

### Step 2 — `FAQService`

`backend/utilities/faq_service.py` (new):

```python
import json
from pathlib import Path

_DB_DIR = Path(__file__).parent.parent.parent / 'database'

class FAQService:
    def __init__(self, engineer):
        self._engineer = engineer
        self._corpus = self._load()

    def _load(self):
        path = _DB_DIR / 'faq_data' / 'faqs.json'
        if not path.exists():
            return []
        return json.loads(path.read_text(encoding='utf-8'))

    def search(self, query:str, top_k:int=3) -> dict:
        if not self._corpus:
            return {'_success': False, '_error': 'empty_corpus',
                    '_message': 'No FAQ corpus loaded.'}
        prompt = self._build_rerank_prompt(query, top_k)
        result = self._engineer(prompt, task='skill', schema=FAQ_RERANK_SCHEMA)
        matches = []
        for hit in result['matches']:
            entry = self._corpus[hit['idx']]
            matches.append({'question': entry['question'], 'answer': entry['answer'],
                            'score': hit['score']})
        return {'_success': True, 'matches': matches}

    def _build_rerank_prompt(self, query, top_k):
        rows = [f"  [{i}] {e['question']}" for i, e in enumerate(self._corpus)]
        return (
            f"User query: {query}\n\n"
            f"FAQ index (question only):\n" + '\n'.join(rows) + "\n\n"
            f"Return up to {top_k} indices, ranked by relevance, with score 0.0-1.0."
        )
```

`FAQ_RERANK_SCHEMA` lives in `backend/prompts/pex/support/converse_prompts.py` (created
in phase 2 or here, whichever lands first):

```python
FAQ_RERANK_SCHEMA = {
    'type': 'object',
    'properties': {
        'matches': {
            'type': 'array',
            'items': {
                'type': 'object',
                'properties': {
                    'idx': {'type': 'integer'},
                    'score': {'type': 'number'},
                },
                'required': ['idx', 'score'],
            },
        },
    },
    'required': ['matches'],
}
```

### Step 3 — Tool registration

`backend/modules/pex.py` — add to the `_tools` registry:

```python
'search_faqs': (self._faq_service, 'search'),
```

Inject `FAQService` in PEX `__init__` alongside the other services. Pass `self.engineer`
since FAQService uses LLM rerank.

`schemas/tools.yaml` — add tool entry:

```yaml
search_faqs:
  tool_id: search_faqs
  description: "Search the FAQ corpus for an answer to a user question. Returns the top matches ranked by relevance."
  params:
    query:
      type: string
      description: "User's question or topic keywords."
    top_k:
      type: integer
      default: 3
```

### Step 4 — Rewrite `search_policy`

`backend/modules/policies/internal.py:67-75` — replace `find_posts` with `search_faqs`,
write structured findings to scratchpad:

```python
def search_policy(self, flow, tools):
    query_slot = flow.slots['query']
    if not query_slot.check_if_filled():
        flow.status = 'Completed'
        return TaskArtifact(flow.name())

    query = str(query_slot.to_dict())
    result = tools('search_faqs', {'query': query, 'top_k': 3})

    if result['_success'] and result['matches']:
        top = result['matches'][0]
        summary = f"Top FAQ match for '{query}': {top['question']} → {top['answer']}"
        self.memory.write_scratchpad('search', {
            'query': query,
            'matches': result['matches'],
            'summary': summary,
        })
    else:
        self.memory.write_scratchpad('search', {
            'query': query,
            'matches': [],
            'summary': f"No FAQ match found for '{query}'.",
        })

    flow.status = 'Completed'
    return TaskArtifact(flow.name())
```

Note the scratchpad key is now `'search'` (not `f'search:{query}'`) so chat_policy can
read it back deterministically.

### Step 5 — Update `SearchFlow.tools`

`flows.py:938` — change `tools = ['find_posts']` → `tools = ['search_faqs']`.

## Verification

- **Free tier** must stay green: `pytest utils/tests/unit_tests.py utils/tests/test_artifacts.py`.
- **New unit test** in `unit_tests.py`: instantiate `FAQService` with a tiny in-memory
  corpus, call `search('what can you do')`, assert top match has the expected idx. (The
  rerank LLM is mocked at the engineer level — see existing patterns.)
- **Manual smoke** (after phase 3): start the agent, type "what can Hugo do?", verify
  the response cites FAQ content (not generic LLM hallucination).

## Risks

- **Corpus too small ⇒ rerank lands on the wrong FAQ for adjacent topics.** With 12
  entries, the LLM is essentially picking 1-of-12 — bad coverage means a borderline
  question routes to the closest-but-still-wrong FAQ. Mitigate by authoring the seed
  carefully; failing that, add a `score < 0.5 ⇒ no match` floor in `search_policy`.
- **LLM rerank latency.** ~1-2s extra per search-routed turn. Acceptable for v1; if
  it bites, swap to keyword-overlap retrieval (zero LLM, microseconds).
