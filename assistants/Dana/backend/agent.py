from __future__ import annotations

import logging

from schemas.config import load_config
from backend.modules.nlu import NLU
from backend.modules.pex import PEX
from backend.modules.res import RES
from backend.components.dialogue_state import DialogueState
from backend.components.task_artifact import TaskArtifact
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

    def take_turn(self, user_text: str, user_actions: list | None = None,
                  gold_dax: str | None = None) -> dict:
        if user_actions and len(user_actions) > 0:
            for action in user_actions:
                gold_dax = action['dax'] if 'dax' in action else ''
                self.world.context.add_turn('User', user_text, turn_type='action')
        else:
            self.world.context.add_turn('User', user_text, turn_type='utterance')

        if self.ambiguity.present():
            if user_actions:
                self.ambiguity.resolve()
            else:
                self.ambiguity.resolve()

        state = self.nlu.understand(user_text, self.world.context, gold_dax)

        flow = self.world.flow_stack.get_active_flow()
        dax = flow.dax if flow else ''
        log.info(f"{state.pred_intent}: {state.flow_name} {{{dax}}}; "
                 f"Confidence: {state.confidence:.2f}")

        if not self._self_check(state):
            return self._fallback_response(
                "I'm having trouble understanding. Could you try rephrasing?"
            )

        artifact = None
        keep_going = True
        rounds = 0

        while keep_going and rounds < _MAX_KEEP_GOING:
            artifact, keep_going = self.pex.execute(state, self.world.context)
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

        if artifact and artifact.has_content():
            log.info('  artifact=%s  source=%s', artifact.block_type, artifact.source)

        utterance, artifact = self.res.respond(artifact)

        if self.memory.should_summarize(state.turn_count):
            self.world.context.save_checkpoint(
                'auto_summarize',
                data={'turn_count': state.turn_count},
            )

        return self._build_payload(utterance, artifact)

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
            'artifact': None,
        }

    def _build_payload(self, utterance: str, artifact: TaskArtifact) -> dict:
        frame_data = None
        if artifact and artifact.has_content():
            frame_data = {
                'type': artifact.block_type,
                'show': True,
                'data': artifact.data,
                'source': artifact.source,
                'display_name': artifact.display_name,
                'panel': artifact.panel,
            }

        state = self.world.current_state()
        interaction = {
            'type': artifact.block_type if artifact and artifact.has_content() else 'default',
            'show': artifact.block_type != 'default' if artifact else False,
            'data': artifact.data if artifact and artifact.has_content() else {},
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
            'artifact': frame_data,
        }

    # ── Session management ────────────────────────────────────────────

    def reset(self):
        self.world.reset()
        self.ambiguity.resolve()
        self.memory.clear_scratchpad()
        self.conversation_id = None

    def close(self):
        pass

    # Alias used by chat_service and tests
    def handle_turn(self, user_text: str, user_actions: list | None = None,
                    gold_dax: str | None = None) -> dict:
        return self.take_turn(user_text, user_actions, gold_dax)
