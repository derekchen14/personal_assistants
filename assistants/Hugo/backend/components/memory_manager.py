class MemoryManager:
    """MEM, the Head — the synchronous facade over the three memory tiers. Holds references to the
    tiers and exposes one read skill per tier (`recap` / `recall` / `retrieve`). Tier-specific
    operations are reached through the sub-component, e.g. `memory.preferences.store_preference`
    or `memory.business.search_faqs`.

    The continuous background MEM loop (auto-promotion, proactive push) is designed-not-built."""

    def __init__(self, context_coordinator, user_preferences, business_context):
        self.context = context_coordinator       # L1 — append-only event stream
        self.preferences = user_preferences      # L2 — per-account defaults
        self.business = business_context         # L3 — business knowledge / FAQs

    def recap(self, n_turns:int|None=None, filter:str|None=None) -> str:
        """L1 — recent session events as formatted history."""
        return self.context.compile_history(look_back=n_turns or 10, keep_system=True)

    def recall(self, query:str, flow_name:str|None=None) -> dict:
        """L2 — the user preferences matching `query`. Semantic lookup is deferred (no vector
        store yet); `flow_name` is accepted but unused."""
        return self.preferences.read(query)

    def retrieve(self, query:str, top_k:int=10, documents:list|None=None) -> dict:
        """L3 — business-knowledge retrieval. `documents=['faq']` takes the FAQ shortcut; otherwise
        rank the supplied documents, or the corpus candidates, down to top_k."""
        documents = documents or []
        if documents and documents[0] == 'faq':
            return self.business.search_faqs(query, top_k=top_k)
        candidates = documents if documents else self.business.search_all(query, top_k=1000)
        return self.business.rerank(query, candidates, top_k=top_k)
