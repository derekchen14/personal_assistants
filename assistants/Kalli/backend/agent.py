"""Agent orchestrator — NLU → PEX → RES turn pipeline with keep_going loop.

Self-check gate: rule-based only (no LLM check for Kalli v1).
"""

from __future__ import annotations

from config import load_config
from backend.modules.nlu import NLU, NLUResult
from backend.modules.pex import PEX
from backend.modules.res import RES
from backend.components.dialogue_state import DialogueState
from backend.components.flow_stack import FlowStack
from backend.components.context_coordinator import ContextCoordinator
from backend.components.prompt_engineer import PromptEngineer
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.memory_manager import MemoryManager


_MAX_KEEP_GOING = 5


class Agent:

    def __init__(self, username: str):
        self.username = username
        self.config = load_config()
        self.conversation_id: str | None = None

        self.dialogue_state = DialogueState(self.config)
        self.flow_stack = FlowStack(self.config)
        self.context = ContextCoordinator(self.config)
        self.prompt_engineer = PromptEngineer(self.config)
        self.display = DisplayFrame(self.config)
        self.ambiguity = AmbiguityHandler(self.config)
        self.memory = MemoryManager(self.config)

        self.nlu = NLU(
            self.config, self.dialogue_state, self.context,
            self.ambiguity, self.prompt_engineer,
        )
        self.pex = PEX(
            self.config, self.dialogue_state, self.flow_stack,
            self.context, self.prompt_engineer, self.memory,
            self.display, self.ambiguity,
        )
        self.res = RES(
            self.config, self.dialogue_state, self.flow_stack,
            self.context, self.prompt_engineer, self.display,
            self.ambiguity, self.memory,
        )

    def handle_turn(self, user_text: str, user_actions: list | None = None,
                    gold_dax: str | None = None) -> dict:
        """Run NLU → PEX → RES. Returns WebSocket-ready response dict."""
        self.context.add_turn('User', user_text)

        if self.ambiguity.present():
            self.ambiguity.resolve()

        nlu_result = self.nlu.understand(user_text, gold_dax)

        if not self._self_check(nlu_result):
            return self._fallback_response(
                "I'm having trouble understanding. Could you try rephrasing?"
            )

        pex_result = None
        keep_going = True
        rounds = 0

        while keep_going and rounds < _MAX_KEEP_GOING:
            pex_result, keep_going = self.pex.execute(nlu_result)
            rounds += 1

            if keep_going:
                active = self.flow_stack.get_active_flow()
                if active:
                    nlu_result = NLUResult(
                        intent=active.intent,
                        dax=active.dax,
                        flow_name=active.flow_name,
                        confidence=1.0,
                        slots=active.slots,
                    )

        response = self.res.respond(pex_result)

        if self.memory.should_summarize(self.dialogue_state.turn_count):
            self.context.save_checkpoint(
                'auto_summarize',
                data={'turn_count': self.dialogue_state.turn_count},
            )

        return response

    # ── Self-check gate ───────────────────────────────────────────────

    def _self_check(self, nlu_result) -> bool:
        if nlu_result.confidence < 0.1:
            return False
        if not nlu_result.flow_name:
            return False
        return True

    def _fallback_response(self, message: str) -> dict:
        self.context.add_turn('Agent', message, turn_type='agent_response')
        return {
            'message': message,
            'raw_utterance': message,
            'actions': [],
            'interaction': {'type': 'default', 'show': False, 'data': {}},
            'code_snippet': None,
            'frame': None,
        }

    # ── Session management ────────────────────────────────────────────

    def reset(self):
        self.dialogue_state.reset()
        self.flow_stack.clear()
        self.context.reset()
        self.display.clear()
        self.ambiguity.resolve()
        self.memory.clear_scratchpad()
        self.conversation_id = None

    def close(self):
        pass
