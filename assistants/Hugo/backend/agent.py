from __future__ import annotations

import json
import logging
import os

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
        try:
            return self._take_turn(text, dax, payload)
        except Exception as ecp:  # noqa: BLE001 — top-level safety net
            log.exception('take_turn crashed: %s', ecp)
            return self._fallback_response(
                "Something went wrong on my end. Please try again."
            )

    def _take_turn(self, text:str, dax:str|None=None, payload:dict|None=None) -> dict:
        turn_type = 'action' if dax else 'utterance'
        self.world.context.add_turn('User', text, turn_type=turn_type)
        log.info('USER (%s): %s', turn_type, text)

        if self.ambiguity.present():
            self.ambiguity.resolve()

        state = self.nlu.understand(text, self.world.context, dax, payload)
        flow = self.world.flow_stack.get_flow()
        log.info('pred = %s {%s}  score=%.2f   slots=%s',
                 flow.name(True), flow.dax, state.confidence, flow.slot_values_dict())

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
            
            flow = self.world.flow_stack.get_flow('Active')
            if not flow:
                keep_going = False

            if keep_going:
                new_state = DialogueState(self.config)
                new_state.update(pred_intent=flow.intent,
                    flow_name=flow.name(), confidence=1.0)
                new_state.has_plan = state.has_plan
                new_state.active_post = state.active_post
                # One-shot for stack-on; Plans keep keep_going alive across sub-flows.
                new_state.keep_going = state.has_plan
                self.world.insert_state(new_state)
                state = new_state

        agent_utt, frame = self.res.respond(frame)
        if agent_utt:
            self.world.context.add_turn('Agent', agent_utt, turn_type='utterance')

        if self.memory.should_summarize(state.turn_count):
            turn_data = {'turn_count': state.turn_count}
            self.world.context.save_checkpoint('auto_summarize', data=turn_data)

        log.info(f'AGENT: {agent_utt[:256]}')
        # Phase-2 logging: rich frame dump so the CLI↔UI gap is visible. frame.metadata + block
        # summary surface the data shape that RES emits — diff this against what the frontend
        # console.log shows for "[frame] received" to find serialization gaps.
        block_summary = [
            {'type': b.block_type, 'data_keys': sorted((b.data or {}).keys()), 'location': b.location}
            for b in frame.blocks
        ]
        log.info(
            f'AGENT-FRAME: origin={frame.origin!r} '
            f'metadata={dict(frame.metadata)!r} '
            f'thoughts={(frame.thoughts or "")[:120]!r} '
            f'blocks={block_summary}'
        )
        # Opt-in full frame dump. Set HUGO_DEBUG_FRAMES=1 to enable.
        if os.environ.get('HUGO_DEBUG_FRAMES'):
            log.info(f'AGENT-FRAME-FULL: {json.dumps(frame.to_dict(), indent=2, default=str)}')
        return self._build_payload(agent_utt, frame)

    def _self_check(self, state: DialogueState) -> bool:
        if state.confidence < 0.1:
            return False
        if not state.flow_name:
            return False
        return True

    def _fallback_response(self, message: str) -> dict:
        self.world.context.add_turn('Agent', message, turn_type='agent_response')
        payload = {'message': message, 'actions': [], 'frame': None, 'block': 'default'}
        return payload

    def _build_payload(self, utterance: str, frame: DisplayFrame) -> dict:       
        frame_data = frame.to_dict()
        payload = {'message': utterance, 'actions': [], 'frame': frame_data}

        # Add a panel key when we aren't just using a 'default' block type
        if len(frame_data['blocks']) > 0:
            block_type = frame_data['blocks'][-1]['type']
            panel = 'top' if block_type in ('form', 'confirmation', 'toast') else 'bottom'
            payload['panel'] = panel   # top / bottom / split

        return payload

    # ── Session management ────────────────────────────────────────────

    def reset(self):
        self.world.reset()
        self.ambiguity.resolve()
        self.memory.clear_scratchpad()
        self.conversation_id = None

    def close(self):
        pass
