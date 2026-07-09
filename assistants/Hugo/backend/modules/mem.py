import logging

from backend.components.context_coordinator import ContextCoordinator
from backend.components.user_preferences import UserPreferences
from backend.components.business_knowledge import BusinessKnowledge
from backend.prompts.for_compressor import build_compression_prompt

log = logging.getLogger(__name__)

class MemoryExtensionModule:
    """MEM, the Head — code-only module over the three memory tiers (no agent, no tool-calling).
    Constructs and owns its components; the World holds the shared references. Exposes one read
    skill per tier (`recap` / `recall` / `retrieve`); tier-specific operations are reached through
    the sub-component, e.g. `world.prefs.store_preference` or `world.knowledge.search_documents`.

    The continuous background MEM loop (auto-promotion, proactive push) is designed-not-built."""

    def __init__(self, config, engineer, username:str):
        self.config = config
        self.engineer = engineer
        self.context_coordinator = ContextCoordinator(config)   # L1 — append-only event stream
        self.user_preferences = UserPreferences(config, username)         # L2 — per-account defaults
        self.business_knowledge = BusinessKnowledge(engineer)    # L3 — business knowledge / FAQs
        self.world = None  # attached by the Assistant after World construction

    def store_turn(self, utterance:str, prompt_tokens:int=0):
        """The end-of-turn store (take_turn step 5): record the agent turn, bump the turn count,
        snapshot the stack onto the state and save state.json — the record of what actually
        happened this turn, MEM's per the time rule — then run the compression check.
        `prompt_tokens` is PEX's real acting-loop usage, passed by the Assistant (the World holds
        components, not modules). Promotion beyond explicit saves (PEX's store_preference tool
        writes L2 during the turn) is designed-not-built."""
        self.context_coordinator.add_turn('Agent', utterance, turn_type='utterance')
        state = self.world.state
        state.turn_count += 1
        state.flow_stack = self.world.flows.to_list()  # refresh the saved copy, then save
        state.save(self.world.state_file())
        # artifact long-term storage (append world.latest_artifact() to artifacts.jsonl in the
        # session dir) # designed-not-built
        self._compression_check(prompt_tokens)

    def _compression_check(self, prompt_tokens:int):
        """Compactor trigger: real prompt-token usage from PEX's last acting-loop API response
        against the configured threshold, checked at the end-of-turn store, never mid-loop. A
        summarizer failure aborts the compaction — the message list stays unchanged and the
        turn's reply still goes out."""
        compression = self.config['compression']
        if prompt_tokens < compression['threshold_tokens']:
            return
        try:
            self.context_coordinator.compress_messages(self._summarize_middle,
                                                       compression['protect_tail'], prompt_tokens)
        except Exception as ecp:  # noqa: BLE001 — aux-LLM failure must not eat the reply
            log.warning('compression aborted, messages unchanged: %s', ecp)

    def _summarize_middle(self, middle:list[dict], previous_summary:str|None, budget:int) -> str:
        """The auxiliary middle-summarizer — the cheap aux model is PromptEngineer's LOW tier.
        The prompt lives in backend/prompts/for_compressor.py."""
        prompt = build_compression_prompt(middle, previous_summary, budget)
        return self.engineer(prompt, task='compress', tier='low', max_tokens=int(budget * 1.3))

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
