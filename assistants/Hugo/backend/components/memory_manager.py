from backend.components.context_coordinator import ContextCoordinator
from backend.components.user_preferences import UserPreferences
from backend.components.business_knowledge import BusinessKnowledge


class MemoryExtensionModule:
    """MEM, the Head — code-only module over the three memory tiers (no agent, no tool-calling).
    Constructs and owns its components; the World holds the shared references. Exposes one read
    skill per tier (`recap` / `recall` / `retrieve`); tier-specific operations are reached through
    the sub-component, e.g. `world.prefs.store_preference` or `world.knowledge.search_documents`.

    The continuous background MEM loop (auto-promotion, proactive push) is designed-not-built."""

    def __init__(self, config, engineer):
        self.config = config
        self.context_coordinator = ContextCoordinator(config)   # L1 — append-only event stream
        self.user_preferences = UserPreferences(config)         # L2 — per-account defaults
        self.business_knowledge = BusinessKnowledge(engineer)    # L3 — business knowledge / FAQs
        self.world = None  # attached by the Assistant after World construction

    def recap(self, n_turns:int|None=None, filter:str|None=None) -> str:
        """L1 — recent session events as formatted history."""
        return self.context_coordinator.compile_history(look_back=n_turns or 10, keep_system=True)

    def recall(self, query:str, flow_name:str|None=None) -> dict:
        """L2 — the user preferences matching `query`. Semantic lookup is deferred (no vector
        store yet); `flow_name` is accepted but unused."""
        return self.user_preferences.read(query)

    def retrieve(self, query:str, top_k:int=10, documents:list|None=None) -> dict:
        """L3 — business-knowledge retrieval. `documents=['faq']` takes the FAQ shortcut; otherwise
        rank the supplied documents, or the corpus candidates, down to top_k."""
        documents = documents or []
        if documents and documents[0] == 'faq':
            return self.business_knowledge.search_documents(query, top_k=top_k)
        candidates = documents if documents else self.business_knowledge._candidates(query, top_k=1000)
        return self.business_knowledge._rerank(query, candidates, top_k=top_k)


# Module alias — the module is MEM; the class name spells it out.
MEM = MemoryExtensionModule
