import json

from backend.prompts.pex.support.converse_prompts import (
    FAQ_RERANK_SCHEMA, build_faq_rerank_prompt,
)
from backend.utilities import services


class FAQService:
    """FAQ corpus retrieval. Loads `database/faq_data/faqs.json` once at construction and
    serves LLM-rerank queries via the engineer. The corpus is small enough (<50 entries)
    that whole-corpus rerank in a single prompt is cheaper and simpler than embeddings."""

    def __init__(self, engineer):
        self._engineer = engineer
        path = services._DB_DIR / 'faq_data' / 'faqs.json'
        self._corpus = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []

    def search_faqs(self, query:str, top_k:int=3) -> dict:
        if not self._corpus:
            return {'_success': False, '_error': 'empty_corpus',
                    '_message': 'No FAQ corpus loaded.'}

        prompt = build_faq_rerank_prompt(query, self._corpus, top_k)
        result = self._engineer(prompt, task='skill', schema=FAQ_RERANK_SCHEMA)

        matches = []
        for hit in result['matches']:
            idx = hit['idx']
            if 0 <= idx < len(self._corpus):
                entry = self._corpus[idx]
                matches.append({'question': entry['question'],
                    'answer': entry['answer'], 'score': hit['score']})
        return {'_success': True, 'matches': matches}
