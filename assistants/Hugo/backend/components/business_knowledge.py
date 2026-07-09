import json

from backend.utilities import services


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
                'additionalProperties': False,
            },
        },
    },
    'required': ['matches'],
    'additionalProperties': False,
}


def build_rerank_prompt(query:str, candidates:list, top_k:int) -> str:
    """Rank a small candidate set against a user query. Returns up to `top_k` indices into
    `candidates`, each with a 0.0-1.0 relevance score. The corpus is small enough to fit in a single
    prompt, so we skip embeddings and let the LLM rank by semantic similarity."""
    rows = [f"  [{idx}] {entry['question']}" for idx, entry in enumerate(candidates)]
    index_block = '\n'.join(rows) if rows else '  (corpus empty)'
    return (
        f"User query: {query}\n\n"
        f"Candidate index (question only):\n{index_block}\n\n"
        f"Return up to {top_k} indices ranked by relevance, with score 0.0-1.0. "
        "Score reflects how directly the entry answers the user query — 1.0 means the entry IS the "
        "answer, 0.5 means it's adjacent, below 0.3 means tangential. If no entry is relevant, "
        "return an empty matches array."
    )


class BusinessKnowledge:
    """MEM's L3 tier — the single interface for business-knowledge retrieval, including FAQs. Loads
    the in-RAM corpus once and serves LLM-rerank queries through the engineer. The corpus is small
    enough (<50 entries) that whole-corpus rerank in one prompt is cheaper than embeddings. Reached
    as `memory.business`.

    Vector/embedding retrieval + agent.md cold-start ingestion are designed-not-built."""

    def __init__(self, engineer):
        self._engineer = engineer
        path = services._DB_DIR / 'faq_data' / 'faqs.json'
        self._corpus = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []

    def insert_record(self, record:dict):
        """Ingestion / promotion seam — append one record to the in-RAM corpus."""
        self._corpus.append(record)

    def _candidates(self, query:str, top_k:int=1000) -> list:
        """Candidate retrieval. Without a vector store this returns the whole corpus (capped at
        top_k); a real embedding search lands here, using the shared model in
        `backend.utilities.embeddings` (the same one the eval response scorer uses — one download,
        not several). # designed-not-built (vector retrieval)"""
        return self._corpus[:top_k]

    def _rerank(self, query:str, candidates:list, top_k:int=10) -> dict:
        """LLM rerank of the given candidates down to the top_k matches."""
        if not candidates:
            return {'_success': False, '_error': 'empty_corpus',
                    '_message': 'No documents to rank.'}
        prompt = build_rerank_prompt(query, candidates, top_k)
        result = self._engineer(prompt, task='skill', schema=FAQ_RERANK_SCHEMA)
        matches = []
        for hit in result['matches']:
            idx = hit['idx']
            if 0 <= idx < len(candidates):
                entry = candidates[idx]
                matches.append({'question': entry['question'],
                    'answer': entry['answer'], 'score': hit['score']})
        return {'_success': True, 'matches': matches}

    def search_documents(self, query:str, top_k:int=3) -> dict:
        """Rerank the whole document corpus (FAQs are one document type)."""
        return self._rerank(query, self._corpus, top_k)
