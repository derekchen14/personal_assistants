from __future__ import annotations

import logging
from types import MappingProxyType

from backend.components.dialogue_state import DialogueState

log = logging.getLogger(__name__)
from backend.components.flow_stack import FlowStack, FlowEntry
from backend.components.context_coordinator import ContextCoordinator
from backend.components.prompt_engineer import PromptEngineer
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.memory_manager import MemoryManager
from backend.modules.pex import PEXResult
from schemas.ontology import Intent


class RES:

    def __init__(self, config: MappingProxyType, dialogue_state: DialogueState,
                 flow_stack: FlowStack, context: ContextCoordinator,
                 prompt_engineer: PromptEngineer, display: DisplayFrame,
                 ambiguity: AmbiguityHandler, memory: MemoryManager):
        self.config = config
        self.dialogue_state = dialogue_state
        self.flow_stack = flow_stack
        self.context = context
        self.prompt_engineer = prompt_engineer
        self.display = display
        self.ambiguity = ambiguity
        self.memory = memory

    def respond(self, pex_result: PEXResult) -> dict:
        completed_flows = self._start()

        if self.ambiguity.present():
            return self._clarify()

        intent = self.dialogue_state.intent or 'Converse'

        log.info('  res intent=%s  keep_going=%s  has_frame=%s',
                 intent, self.dialogue_state.keep_going,
                 self.display.has_content())

        if intent == Intent.INTERNAL.value:
            display_data = self._display('')
            response = self._build_response('', pex_result, display_data)
            self._finish(response)
            return response

        if intent == Intent.PLAN.value and self.dialogue_state.keep_going:
            display_data = self._display('')
            response = self._build_response('', pex_result, display_data)
            self._finish(response)
            return response

        text = self._generate(pex_result, completed_flows)
        display_data = self._display(text)
        response = self._build_response(text, pex_result, display_data)
        self._finish(response)

        if text:
            self.context.add_turn('Agent', text, turn_type='agent_response')

        return response

    # ── Pre-hook ──────────────────────────────────────────────────────

    def _start(self) -> list[FlowEntry]:
        popped = self.flow_stack.pop_completed_and_invalid()

        completed = [f for f in popped if f.result is not None]
        if len(completed) > 1:
            self.context.save_checkpoint(
                'multi_flow_completion',
                data={'completed_count': len(completed)},
            )

        return completed

    # ── Clarify ───────────────────────────────────────────────────────

    def _clarify(self) -> dict:
        level = self.ambiguity.level or 'general'
        metadata = self.ambiguity.metadata or {}
        observation = self.ambiguity.observation

        clarification_text = self.prompt_engineer.build_clarification_prompt(
            level, metadata, observation, self.context.compile_history(turns=3),
        )

        self.context.add_turn(
            'Agent', clarification_text, turn_type='clarification',
        )
        return {
            'message': clarification_text,
            'raw_utterance': clarification_text,
            'actions': [],
            'interaction': {'type': 'default', 'show': False, 'data': {}},
            'frame': None,
        }

    # ── Generate ──────────────────────────────────────────────────────

    def _generate(self, pex_result: PEXResult,
                  completed_flows: list[FlowEntry]) -> str:
        if not pex_result.message:
            return ''

        intent = self.dialogue_state.intent or 'Converse'
        flow_name = self.dialogue_state.flow_name or ''

        raw = self._template_fill(pex_result, intent, flow_name)

        tmpl_info = self.prompt_engineer.get_template(flow_name, intent)
        if tmpl_info.get('skip_naturalize'):
            return raw

        return self._naturalize(raw, pex_result.block_type)

    def _template_fill(self, pex_result: PEXResult, intent: str,
                       flow_name: str) -> str:
        tmpl_info = self.prompt_engineer.get_template(flow_name, intent)
        template = tmpl_info.get('template', '{message}')

        slot_summary = ''
        if self.dialogue_state.slots:
            parts = [f'{k}: {v}' for k, v in self.dialogue_state.slots.items()]
            slot_summary = ', '.join(parts)

        try:
            return template.format(
                message=pex_result.message,
                flow_name=flow_name or 'your request',
                slot_summary=slot_summary or 'the information',
            )
        except KeyError:
            return pex_result.message

    def _naturalize(self, raw_text: str, block_type: str | None) -> str:
        if not raw_text.strip():
            return raw_text

        if len(raw_text) < 80:
            return raw_text

        system, messages = self.prompt_engineer.build_naturalize_prompt(
            raw_text, self.context.compile_history(turns=3), block_type,
        )

        try:
            response = self.prompt_engineer.call(
                system=system,
                messages=messages,
                call_site='naturalize',
                max_tokens=2048,
            )
            text = ''
            for block in response.content:
                if block.type == 'text':
                    text += block.text
            return text.strip() if text.strip() else raw_text
        except Exception as e:
            print(f'RES naturalization error: {e}')
            return raw_text

    # ── Display ───────────────────────────────────────────────────────

    def _display(self, text: str) -> dict | None:
        if not self.display.has_content():
            return None

        if not self.display.data:
            self.display.clear()
            return None

        return {
            'type': self.display.block_type,
            'show': True,
            'data': self.display.data,
            'source': self.display.source,
            'display_name': self.display.display_name,
            'panel': self.display.panel,
        }

    # ── Response assembly ─────────────────────────────────────────────

    def _build_response(self, text: str, pex_result: PEXResult,
                        display_data: dict | None = None) -> dict:
        interaction = {
            'type': pex_result.block_type,
            'show': pex_result.block_type != 'default',
            'data': pex_result.block_data,
        }

        return {
            'message': text,
            'raw_utterance': pex_result.message,
            'actions': pex_result.actions,
            'interaction': interaction,
            'code_snippet': None,
            'frame': display_data,
        }

    # ── Post-hook ─────────────────────────────────────────────────────

    def _finish(self, response: dict):
        message = response.get('message', '')
        intent = self.dialogue_state.intent or 'Converse'

        if intent not in (Intent.INTERNAL.value, Intent.PLAN.value):
            if not message and not response.get('frame'):
                response['message'] = (
                    "I've processed your request. Let me know if you need "
                    "anything else."
                )

        if not message:
            if intent not in (Intent.INTERNAL.value, Intent.PLAN.value):
                if not self.dialogue_state.keep_going:
                    response['message'] = (
                        "I've completed the action. What would you like to "
                        "do next?"
                    )

        self.display.clear()
