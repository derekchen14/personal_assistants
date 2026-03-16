from __future__ import annotations

import logging
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame

log = logging.getLogger(__name__)
from backend.components.flow_stack.parents import BaseFlow
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from schemas.ontology import Intent
from utils.helper import output_for_flow

if TYPE_CHECKING:
    from backend.components.world import World

_UNSUPPORTED_MESSAGE = (
    "That feature isn't supported yet, but it's on the roadmap. "
    "Is there something else I can help with?"
)


class RES:

    def __init__(self, config: MappingProxyType, ambiguity: AmbiguityHandler,
                 engineer: PromptEngineer, world: 'World'):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.world = world
        self.flow_stack = world.flow_stack

    def respond(self, frame: DisplayFrame) -> tuple[str, DisplayFrame]:
        completed_flows = self._start()

        if self.ambiguity.present():
            text = self._clarify()
            return text, frame

        state = self.world.current_state()
        intent = state.pred_intent if state else 'Converse'

        log.info('  res intent=%s  keep_going=%s  has_frame=%s',
                 intent, state.keep_going if state else False,
                 frame.has_content())

        flow = self.flow_stack.get_active_flow()
        if flow and flow.result and flow.result.get('unsupported'):
            text = _UNSUPPORTED_MESSAGE
            self.world.context.add_turn('Agent', text, turn_type='agent_response')
            return text, frame

        if intent == Intent.INTERNAL:
            self._finish('', frame)
            return '', frame

        if intent == Intent.PLAN and state and state.keep_going:
            self._finish('', frame)
            return '', frame

        text = self._generate(frame, state, completed_flows)

        block = self.display(frame, state, text)
        if block:
            frame.data['_rendered_block'] = block

        self._finish(text, frame)

        if text:
            self.world.context.add_turn('Agent', text, turn_type='agent_response')

        return text, frame

    # ── Pre-hook ──────────────────────────────────────────────────────

    def _start(self) -> list[BaseFlow]:
        popped = self.flow_stack.pop_completed_and_invalid()

        completed = [f for f in popped if f.result is not None]
        for flow in completed:
            if flow.intent == Intent.PLAN:
                state = self.world.current_state()
                if state:
                    state.update_flags(has_plan=False)
                    state.structured_plan = {}

        if len(completed) > 1:
            self.world.context.save_checkpoint(
                'multi_flow_completion',
                data={'completed_count': len(completed)},
            )

        return completed

    # ── Clarify ───────────────────────────────────────────────────────

    def _clarify(self) -> str:
        level = self.ambiguity.level or 'general'
        metadata = self.ambiguity.metadata or {}
        observation = self.ambiguity.observation

        clarification_text = self.engineer.build_clarification_prompt(
            level, metadata, observation,
        )

        self.world.context.add_turn(
            'Agent', clarification_text, turn_type='clarification',
        )
        return clarification_text

    # ── Generate ──────────────────────────────────────────────────────

    def _generate(self, frame: DisplayFrame, state: DialogueState | None,
                  completed_flows: list[BaseFlow]) -> str:
        if state and state.flow_name == 'view' and frame.has_content():
            title = frame.data.get('title', 'the post')
            return f'Here\'s "{title}".'

        content = frame.data.get('content', '') if frame and frame.data else ''
        if not content:
            return ''

        intent = state.pred_intent if state else 'Converse'
        flow_name = state.flow_name if state else ''

        raw = self._template_fill(content, state, intent, flow_name)

        tmpl_info = self.engineer.get_template(flow_name, intent)
        if tmpl_info.get('skip_naturalize'):
            return raw

        return self._naturalize(raw, frame.block_type if frame.has_content() else None)

    def _template_fill(self, message: str, state: DialogueState | None,
                       intent: str, flow_name: str) -> str:
        tmpl_info = self.engineer.get_template(flow_name, intent)
        template = tmpl_info.get('template', '{message}')

        slot_summary = ''
        flow = self.flow_stack.find_by_name(flow_name) if flow_name else None
        if flow:
            sv = flow.slot_values_dict()
            if sv:
                parts = [f'{k}: {v}' for k, v in sv.items()]
                slot_summary = ', '.join(parts)

        try:
            return template.format(
                message=message,
                flow_name=flow_name or 'your request',
                slot_summary=slot_summary or 'the information',
            )
        except KeyError:
            return message

    def _naturalize(self, raw_text: str, block_type: str | None) -> str:
        if self.config.get('debug', False):
            return raw_text

        if not raw_text.strip():
            return raw_text

        if len(raw_text) < 80:
            return raw_text

        convo_history = self.world.context.compile_history(look_back=3)
        system, messages = self.engineer.build_naturalize_prompt(raw_text, convo_history, block_type)

        try:
            text = self.engineer.call(
                messages, system=system,
                task='naturalize', max_tokens=2048,
            )
            return text.strip() if text.strip() else raw_text
        except Exception as e:
            print(f'RES naturalization error: {e}')
            return raw_text

    # ── Display ───────────────────────────────────────────────────────

    def display(self, frame: DisplayFrame, state: DialogueState | None,
                text: str) -> dict | None:
        if not frame or not frame.has_content():
            return None
        if not frame.data or frame.block_type == 'default':
            return None

        flow_name = state.flow_name if state else ''
        block_hint = output_for_flow(flow_name) if flow_name else frame.block_type
        block_type = block_hint if block_hint != '(internal)' else frame.block_type

        block = frame.compose(block_type, dict(frame.data))
        block['panel'] = frame.panel
        block['location'] = ['top', 'bottom']
        block['display_name'] = frame.display_name
        block['source'] = frame.source
        if frame.code:
            block['code'] = frame.code

        has_text = bool(text and text.strip())
        has_frame = frame.has_content()
        if has_text and has_frame:
            block['display_panel'] = 'split'
        elif has_frame:
            block['display_panel'] = 'bottom'
        else:
            block['display_panel'] = 'top'

        if not block.get('data'):
            return None
        return block

    # ── Post-hook ─────────────────────────────────────────────────────

    def _finish(self, text: str, frame: DisplayFrame):
        state = self.world.current_state()
        intent = state.pred_intent if state else 'Converse'

        if intent not in (Intent.INTERNAL, Intent.PLAN):
            if not text and not frame.has_content():
                pass  # orchestrator handles fallback
