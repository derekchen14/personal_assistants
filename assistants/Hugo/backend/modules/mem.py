import logging

from backend.components.context_coordinator import ContextCoordinator
from backend.components.user_preferences import UserPreferences
from backend.components.business_knowledge import BusinessKnowledge
from backend.prompts.for_compactor import build_compaction_prompt

log = logging.getLogger(__name__)

class MemoryExtensionModule:
    """MEM, the Head — code-only module over the three memory tiers (no agent, no tool-calling).
    Constructs and owns its components; the World holds the shared references. Main methods are
    `recap` / `recall` / `retrieve` (L1/L2/L3 — the module surface table): `recap` is the turn
    wrap, start → compaction/promote → finish; `remember(op=x)` is reserved as MEM's tool-call
    name. Tier-specific operations are reached through the sub-component, e.g.
    `world.context.compile_history`, `world.prefs.store_preference`, or
    `world.knowledge.search_documents`.

    The continuous background MEM loop (auto-promotion, proactive push) is designed-not-built."""

    def __init__(self, config, engineer, username:str):
        self.config = config
        self.engineer = engineer
        self.context_coordinator = ContextCoordinator(config)   # L1 — append-only event stream
        self.user_preferences = UserPreferences(config, username)         # L2 — per-account defaults
        self.business_knowledge = BusinessKnowledge(engineer)    # L3 — business knowledge / FAQs
        self.world = None  # attached by the Assistant after World construction

    def recap(self, utterance:str, prompt_tokens:int=0, completed:tuple=()):
        """The turn wrap (T20: `store_turn` renamed to match the module surface table —
        `recap`: start → compaction/promote → finish): record the agent turn, run start() (the
        System checkpoint turn + per-turn resets), the compaction check, then finish() (persist).
        `prompt_tokens` is PEX's real acting-loop usage and `completed` the flows that reached
        Completed this turn, both passed by the Assistant (the World holds components, not
        modules). Promotion beyond explicit saves (PEX's store_preference tool writes L2 during
        the turn) is designed-not-built."""
        self.context_coordinator.add_turn('Agent', utterance, turn_type='utterance')
        self.start(completed)
        # artifact long-term storage (append world.latest_artifact() to artifacts.jsonl in the
        # session dir) # designed-not-built
        self._compaction_check(prompt_tokens)
        self.finish()

    def start(self, completed:tuple=()):
        """Canonical turn 'module · start()': the backward-looking System checkpoint turn —
        which flows completed this turn, which flow is still active, the grounded post — plus
        the per-turn resets (is_newborn, consumed choices, turn count)."""
        state = self.world.state
        active = self.world.flows.get_flow(status='Active')
        parts = [f"completed: {', '.join(flow.name() for flow in completed) or 'none'}",
                 f"active: {active.name() if active else 'none'}"]
        active_post = state.get_active_post()
        if active_post:
            parts.append(f"post: {active_post}")
        self.context_coordinator.add_turn('System', f"[checkpoint] {' | '.join(parts)}",
                                          turn_type='checkpoint')
        for flow in self.world.flows._stack:  # the turn is over: nothing on the stack is newborn
            flow.is_newborn = False
        # Round 3.3 (D5): a completed flow other than the choices' writer has consumed them —
        # the chosen value now lives in that flow's slots and completion entry, so the
        # candidates clear. A completed Converse flow doesn't clear them (an open question may
        # still need its candidates when the user comes back).
        choices = state.grounding['choices']
        sources = {choice['source'] for choice in choices if isinstance(choice, dict)}
        if choices and any(flow.name() not in sources and flow.intent != 'Converse'
                           for flow in completed):
            state.grounding['choices'] = []
        state.turn_count += 1

    def finish(self):
        """Canonical turn 'module · finish()': run the turn-end shape check on the one live
        stack (pex.flow_stack, via the world), save state.json."""
        self._check_turn_end_shape(self.world.flows.to_list())
        self.world.state.save(self.world.state_file())

    @staticmethod
    def _check_turn_end_shape(stack:list):
        """Log-only turn-end invariant check (round 2.12): a turn must end with an empty stack or
        an Active flow on top — no Pending flow on top, no Completed/Invalid survivor. Post-hooks
        validate, they never rewrite state; a violation here means PEX's pop discipline slipped
        and the NEXT turn would fill the wrong flow."""
        terminal = [entry['flow_name'] for entry in stack
                    if entry['status'] in ('Completed', 'Invalid')]
        pending_top = bool(stack) and stack[-1]['status'] == 'Pending'
        if terminal or pending_top:
            log.warning('turn-end stack shape violated: top=%s terminal_leftovers=%s',
                        stack[-1]['status'] if stack else 'empty', terminal)

    def _compaction_check(self, prompt_tokens:int):
        """Compactor trigger: real prompt-token usage from PEX's last acting-loop API response
        against the configured threshold, checked at the end-of-turn store, never mid-loop. A
        summarizer failure aborts the compaction — the message list stays unchanged and the
        turn's reply still goes out."""
        compaction = self.config['compaction']
        if prompt_tokens < compaction['threshold_tokens']:
            return
        try:
            self.context_coordinator.compact_messages(self._summarize_middle,
                                                      compaction['protect_tail'], prompt_tokens)
        except Exception as ecp:  # noqa: BLE001 — aux-LLM failure must not eat the reply
            log.warning('compaction aborted, messages unchanged: %s', ecp)

    def _summarize_middle(self, middle:list[dict], previous_summary:str|None, budget:int) -> str:
        """The auxiliary middle-summarizer — the cheap aux model is PromptEngineer's LOW tier.
        The prompt lives in backend/prompts/for_compactor.py."""
        prompt = build_compaction_prompt(middle, previous_summary, budget)
        return self.engineer(prompt, task='compress', tier='low', max_tokens=int(budget * 1.3))

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
