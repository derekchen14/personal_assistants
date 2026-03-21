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
        self.ambiguity = AmbiguityHandler(self.config, engineer=self.engineer)
        self.memory = MemoryManager(self.config)

        self.nlu = NLU(self.config, self.ambiguity, self.engineer, self.world)
        self.pex = PEX(self.config, self.ambiguity, self.engineer, self.memory, self.world)
        self.res = RES(self.config, self.ambiguity, self.engineer, self.world)

    def take_turn(self, text:str, dax:str|None=None, payload:dict|None=None) -> dict:
        turn_type = 'action' if text.startswith('<action>') else 'utterance'
        self.world.context.add_turn('User', text, turn_type=turn_type)
        log.info('USER (%s): %s', turn_type, text)

        if self.ambiguity.present():
            self.ambiguity.resolve()

        state = self.nlu.understand(text, self.world.context, dax, payload)

        flow = self.world.flow_stack.get_active_flow()
        dax = flow.dax if flow else ''
        slots = flow.slot_values_dict() if flow else {}
        log.info('pred = %s {%s}  score=%.2f   slots=%s',
                 flow.name(True) if flow else state.flow_name,
                 dax, state.confidence, slots)

        if not self._self_check(state):
            fallback_message = "I'm having trouble understanding. Could you try rephrasing?"
            return self._fallback_response(fallback_message)

        frame = None
        keep_going = True
        rounds = 0

        while keep_going and rounds < _MAX_KEEP_GOING:
            frame, keep_going = self.pex.execute(state, self.world.context)
            rounds += 1
            log.info('  pex round=%d  keep_going=%s', rounds, keep_going)

            if keep_going:
                flow = self.world.flow_stack.get_active_flow()
                if flow:
                    new_state = DialogueState(self.config)
                    new_state.update(pred_intent=flow.intent,
                        flow_name=flow.name(), confidence=1.0)
                    new_state.keep_going = True
                    self.world.insert_state(new_state)
                    state = new_state

        if frame and frame.has_content():
            log.info('  frame=%s  origin=%s', frame.block_type, frame.origin)

        utterance, frame = self.res.respond(frame)

        if utterance:
            log.info('AGENT: %s', utterance[:200])

        if self.memory.should_summarize(state.turn_count):
            self.world.context.save_checkpoint(
                'auto_summarize',
                data={'turn_count': state.turn_count},
            )

        return self._build_payload(utterance, frame)

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
            'frame': None,
        }

    def _build_payload(self, utterance: str, frame: DisplayFrame) -> dict:
        frame_data = frame.to_dict() if frame and frame.has_content() else None

        message = utterance
        if not message and not frame_data:
            state = self.world.current_state()
            if state and state.pred_intent not in ('Internal', 'Plan'):
                message = (
                    "I've processed your request. Let me know if you need "
                    "anything else."
                )

        return {
            'message': message,
            'raw_utterance': utterance,
            'actions': [],
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
