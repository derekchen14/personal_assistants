from __future__ import annotations

import logging

from schemas.config import load_config
from backend.modules.nlu import NLU
from backend.modules.pex import PEX
from backend.modules.res import RES
from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame
from backend.components.prompt_engineer import PromptEngineer
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.memory_manager import MemoryManager
from backend.components.world import World

log = logging.getLogger(__name__)
_MAX_KEEP_GOING = 5

class Agent:

    def __init__(self, username: str):
        self.username = username
        self.config = load_config()
        self.conversation_id: str | None = None

        self.world = World(self.config)
        self.engineer = PromptEngineer(self.config)
        self.ambiguity = AmbiguityHandler(self.config)
        self.memory = MemoryManager(self.config)

        self.nlu = NLU(self.config, self.ambiguity, self.engineer, self.world)
        self.pex = PEX(self.config, self.ambiguity, self.engineer, self.memory, self.world)
        self.res = RES(self.config, self.ambiguity, self.engineer, self.world)

    def take_turn(self, user_text: str, user_actions: list | None = None,
                  gold_dax: str | None = None) -> dict:
        self.world.context.add_turn('User', user_text, turn_type='utterance')

        # Resolve any pending ambiguity from the previous turn.
        if self.ambiguity.present():
            if user_actions:
                # User actions are explicit — always resolve immediately.
                self.ambiguity.resolve()
            else:
                # TODO: pass user_text + ambiguity context to a model to
                # check whether the user's utterance actually resolves the
                # ambiguity.  For now, optimistically resolve.
                self.ambiguity.resolve()

        state = self.nlu.understand(user_text, self.world.context, gold_dax)

        log.info(f"{state.pred_intent}: {state.flow_name}; "
                 f"Confidence: {state.confidence:.2f}")

        if not self._self_check(state):
            return self._fallback_response(
                "I'm having trouble understanding. Could you try rephrasing?"
            )

        frame = None
        keep_going = True
        rounds = 0

        while keep_going and rounds < _MAX_KEEP_GOING:
            frame, keep_going = self.pex.execute(state, self.world.context)
            rounds += 1
            log.info('  pex round=%d  keep_going=%s', rounds, keep_going)

            if keep_going:
                active = self.world.flow_stack.get_active_flow()
                if active:
                    new_state = DialogueState(self.config)
                    new_state.update(
                        pred_intent=active.intent,
                        flow_name=active.flow_name,
                        confidence=1.0,
                    )
                    new_state.keep_going = True
                    self.world.insert_state(new_state)
                    state = new_state

        if frame and frame.has_content():
            active = self.world.flow_stack.get_active_flow()
            dax = active.dax if active else ''
            log.info('  frame=%s  source=%s  dax=%s', frame.block_type, frame.source, dax)

        utterance, frame = self.res.respond(frame)

        if self.memory.should_summarize(state.turn_count):
            self.world.context.save_checkpoint(
                'auto_summarize',
                data={'turn_count': state.turn_count},
            )

        return self._build_payload(utterance, frame)

    # ── Self-check gate ───────────────────────────────────────────────

    def _self_check(self, state: DialogueState) -> bool:
        if state.confidence < 0.1:
            return False
        if not state.flow_name:
            return False
        return True

    def _fallback_response(self, message: str) -> dict:
        self.world.context.add_turn('Agent', message, turn_type='agent_response')
        return {
            'message': message,
            'raw_utterance': message,
            'actions': [],
            'interaction': {'type': 'default', 'show': False, 'data': {}},
            'code_snippet': None,
            'frame': None,
        }

    def _build_payload(self, utterance: str, frame: DisplayFrame) -> dict:
        frame_data = None
        if frame and frame.has_content():
            frame_data = {
                'type': frame.block_type,
                'show': True,
                'data': frame.data,
                'source': frame.source,
                'display_name': frame.display_name,
                'panel': frame.panel,
            }

        state = self.world.current_state()
        interaction = {
            'type': frame.block_type if frame and frame.has_content() else 'default',
            'show': frame.block_type != 'default' if frame else False,
            'data': frame.data if frame and frame.has_content() else {},
        }

        message = utterance
        if not message and not frame_data:
            if state and state.pred_intent not in ('Internal', 'Plan'):
                message = (
                    "I've processed your request. Let me know if you need "
                    "anything else."
                )

        return {
            'message': message,
            'raw_utterance': utterance,
            'actions': [],
            'interaction': interaction,
            'code_snippet': None,
            'frame': frame_data,
        }

    # ── Session management ────────────────────────────────────────────

    def reset(self):
        self.world.reset()
        self.ambiguity.resolve()
        self.memory.clear_scratchpad()
        self.conversation_id = None

    def close(self):
        pass
