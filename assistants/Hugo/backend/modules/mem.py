import logging

from backend.components.context_coordinator import ContextCoordinator
from backend.components.user_preferences import UserPreferences
from backend.components.business_knowledge import BusinessKnowledge
from backend.prompts.for_compactor import build_compaction_prompt

log = logging.getLogger(__name__)

class MemoryExtensionModule:
    """Own the three memory levels and expose `recap`, `recall`, and `retrieve` for L1, L2, and L3.
    The World shares MEM's components; level-specific operations run through context, preferences, and
    business knowledge. `recap` wraps each turn with start → compaction → finish."""

    def __init__(self, config, engineer, username:str):
        self.config = config
        self.engineer = engineer
        self.context_coordinator = ContextCoordinator(config)   # L1: append-only event stream
        self.user_preferences = UserPreferences(config, username)         # L2: account defaults
        self.business_knowledge = BusinessKnowledge(engineer)    # L3: business knowledge and FAQs
        self.world = None  # Attached by the Assistant after World construction.

    def recap(self, utterance:str, prompt_tokens:int=0, recently_finished:tuple=()):
        """Record the agent turn, checkpoint and reset per-turn state, check compaction, then persist.
        `prompt_tokens` is PEX's actual usage; `recently_finished` contains every popped flow, of which
        MEM stores only Completed members."""
        completed = [flow for flow in recently_finished if flow.status == 'Completed']
        self.context_coordinator.add_turn('agent', {'text': utterance})
        self.start(completed)
        # TODO: artifact long-term storage (save world.artifacts to artifacts.jsonl in the session dir)
        self._compaction_check(prompt_tokens)
        self.finish()

    def start(self, completed:tuple=()):
        """Save the turn-wrap checkpoint with Completed and Active flows and the grounded post, then reset
        per-turn state for `is_newborn` and consumed choices."""
        state = self.world.state
        active = self.world.flows.get_flow(status='Active')
        parts = [f"completed: {', '.join(flow.name() for flow in completed) or 'none'}",
                 f"active: {active.name() if active else 'none'}"]
        data = {'completed': [flow.name() for flow in completed],
                'active': active.name() if active else None}
        active_post = state.get_active_post()
        if active_post:
            parts.append(f"post: {active_post}")
            data['post'] = active_post
        self.context_coordinator.save_checkpoint('turn_wrap', data, text=' | '.join(parts))
        for flow in self.world.flows._stack:  # Nothing on the stack remains newborn after the turn.
            flow.is_newborn = False
        # Clear choices consumed by another Completed flow; Converse may need them for an open question.
        choices = state.grounding['choices']
        sources = {choice['source'] for choice in choices if isinstance(choice, dict)}
        if choices and any(flow.name() not in sources and flow.intent != 'Converse'
                           for flow in completed):
            state.grounding['choices'] = []

    def finish(self):
        """Check the live stack, copy Context's authoritative turn count, and save `state.json`."""
        self._check_turn_end_shape(self.world.flows.to_list())
        self.world.state.turn_id = self.world.context.num_utterances
        self.world.state.save(self.world.session_dir() / 'state.json')

    @staticmethod
    def _check_turn_end_shape(stack:list):
        """Log when a turn ends without an empty stack or an Active top; terminal flows beneath live work are valid.
        This check reports a violation without changing the stack because lifecycle changes remain PEX's responsibility."""
        if stack and stack[-1]['status'] != 'Active':
            log.warning('turn-end stack shape violated: top=%s (%s)',
                        stack[-1]['flow_name'], stack[-1]['status'])

    def _compaction_check(self, prompt_tokens:int):
        """Compact at turn end when PEX's actual prompt-token usage reaches the configured threshold.
        A summarizer failure preserves the message list and does not prevent delivery of the reply."""
        compaction = self.config['compaction']
        if prompt_tokens < compaction['threshold_tokens']:
            return
        try:
            self.context_coordinator.compact_messages(self._summarize_middle,
                                                      compaction['protect_tail'], prompt_tokens)
        except Exception as ecp:  # noqa: BLE001 — aux-LLM failure must not eat the reply
            log.warning('compaction aborted, messages unchanged: %s', ecp)

    def _summarize_middle(self, middle:list[dict], previous_summary:str|None, budget:int) -> str:
        """Summarize the middle context with PromptEngineer's low tier and the compactor prompt."""
        prompt = build_compaction_prompt(middle, previous_summary, budget)
        return self.engineer(prompt, task='compress', tier='low', max_tokens=int(budget * 1.3))

    def recall(self, query:str, flow_name:str|None=None) -> dict:
        """Return L2 user preferences matching `query`; `flow_name` is reserved for semantic lookup."""
        return self.user_preferences.read(query)

    def retrieve(self, query:str, top_k:int=10, documents:list|None=None) -> dict:
        """Retrieve L3 business knowledge, using the FAQ shortcut or reranking documents to `top_k`."""
        documents = documents or []
        if documents and documents[0] == 'faq':
            return self.business_knowledge.search_documents(query, top_k=top_k)
        candidates = documents if documents else self.business_knowledge._candidates(query, top_k=1000)
        return self.business_knowledge._rerank(query, candidates, top_k=top_k)


# Module alias — the module is MEM; the class name spells it out.
MEM = MemoryExtensionModule
