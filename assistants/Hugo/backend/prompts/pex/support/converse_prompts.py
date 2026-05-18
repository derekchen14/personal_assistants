# Supporting prompts for Converse + Internal flows


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


def build_faq_rerank_prompt(query:str, faqs:list, top_k:int=3) -> str:
    """Rank a small FAQ corpus against a user query. Returns up to `top_k` indices into
    `faqs`, each with a 0.0-1.0 relevance score. The corpus is small enough to fit in a
    single prompt so we skip embeddings entirely; the LLM ranks by semantic similarity."""
    rows = [f"  [{idx}] {entry['question']}" for idx, entry in enumerate(faqs)]
    index_block = '\n'.join(rows) if rows else '  (corpus empty)'
    return (
        f"User query: {query}\n\n"
        f"FAQ index (question only):\n{index_block}\n\n"
        f"Return up to {top_k} indices ranked by relevance, with score 0.0-1.0. "
        "Score reflects how directly the FAQ entry answers the user query — 1.0 means "
        "the entry IS the answer, 0.5 means it's adjacent, below 0.3 means tangential. "
        "If no entry is relevant, return an empty matches array."
    )


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
    """Dictionary/thesaurus lookup for a single word or short phrase. `category` narrows
    the focus when set ('definition', 'synonyms', 'antonyms', 'examples'); when None,
    populate all four fields. Empty arrays are valid for fields that don't apply (proper
    nouns lacking synonyms, common adjectives lacking strong antonyms, etc.)."""
    scope = (
        f"Focus on '{category}' but populate the other fields with concise content "
        if category else "Populate all fields "
    )
    return (
        f"Look up '{word}' as a dictionary and thesaurus entry. {scope}"
        "(definition: 1 sentence; synonyms/antonyms: 5-8 each, common-usage; examples: "
        "2-3 short sentences using the word naturally).\n\n"
        "Return JSON matching the schema. If the word is unknown or not standard "
        "English, return all empty fields with the original `word` value."
    )
