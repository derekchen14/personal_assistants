from __future__ import annotations

import json
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from schemas.ontology import FLOW_CATALOG, Intent

if TYPE_CHECKING:
    from backend.components.world import World


class RES:

    def __init__(self, config: MappingProxyType, ambiguity: AmbiguityHandler,
                 engineer: PromptEngineer, world: 'World'):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.world = world
        self._response_cfg = config.get('response_constraints', {})
        self._debug = config.get('logging', {}).get('debug', False)

    def respond(self, state: DialogueState,
                frame: DisplayFrame) -> dict:
        self._start(state)

        if self.ambiguity.present():
            clarification = self._clarify()
            self._finish(state)
            return {
                'message': clarification,
                'display': None,
                'clarification': True,
            }

        raw_text = self._generate(state, frame)
        display_block = self.display(state, frame)
        self._finish(state)

        return {
            'message': raw_text,
            'display': display_block,
            'clarification': False,
        }

    # ── Start ────────────────────────────────────────────────────────

    def _start(self, state: DialogueState):
        popped = self.world.flow_stack.pop_completed_and_invalid()

        if state.has_plan and not state.structured_plan.get('sub_flows'):
            state.has_plan = False
            state.structured_plan = {}

        if popped:
            self.world.context.save_checkpoint(
                'flow_completed',
                data={'flow_names': [e.flow_name for e in popped]},
            )

    # ── Clarify ──────────────────────────────────────────────────────

    def _clarify(self) -> str:
        observation = self.ambiguity.observation
        if observation:
            return observation
        return self.ambiguity.ask()

    # ── Generate ─────────────────────────────────────────────────────

    def _generate(self, state: DialogueState,
                  frame: DisplayFrame) -> str:
        raw_text = self._template_fill(state, frame)
        text = self._naturalize(raw_text, state)
        return text

    def _template_fill(self, state: DialogueState,
                       frame: DisplayFrame) -> str:
        flow_name = state.flow_name
        intent = state.intent
        template_data = self.engineer.get_template(flow_name, intent)
        template = template_data.get('template', '{message}')

        frame_content = ''
        if frame.has_content():
            frame_content = frame.data.get('content', '')

        slot_summary = ''
        if state.slots:
            items = [f'{k}={v}' for k, v in state.slots.items()]
            slot_summary = ', '.join(items)

        filled = template.format(
            message=frame_content,
            slots=slot_summary,
            flow_name=flow_name,
            intent=intent,
        )
        return filled

    def _naturalize(self, raw_text: str, state: DialogueState) -> str:
        if self._debug:
            return raw_text

        if len(raw_text) < 30:
            return raw_text

        max_len = self._response_cfg.get('max_length', 500)
        history = self.world.context.compile_history(turns=3)
        system, messages = self.engineer.build_naturalize_prompt(
            raw_text, history, block_type=None,
        )

        try:
            response = self.engineer.call(
                system=system, messages=messages,
                call_site='naturalize', max_tokens=max_len,
            )
            text = ''
            for block in response.content:
                if block.type == 'text':
                    text += block.text
            return text.strip() if text.strip() else raw_text
        except Exception:
            return raw_text

    # ── Display ──────────────────────────────────────────────────────

    def display(self, state: DialogueState,
                frame: DisplayFrame) -> dict | None:
        if not frame.has_content():
            return None

        flow_name = state.flow_name
        flow_info = FLOW_CATALOG.get(flow_name, {})
        output_type = flow_info.get('output', 'card')

        template_data = self.engineer.get_template(flow_name, state.intent)
        block_hint = template_data.get('block_hint')
        if block_hint:
            output_type = block_hint

        content = frame.data.get('content', '')
        title = frame.data.get('title', flow_name)

        if output_type == 'form':
            fields = frame.data.get('fields', [])
            return frame.form(fields)
        elif output_type == 'confirmation':
            prompt = frame.data.get('prompt', content)
            return frame.confirmation(prompt)
        elif output_type == 'toast':
            return frame.toast(content)
        elif output_type == 'list':
            items = frame.data.get('items', [])
            return frame.listing(title, items)
        else:
            actions = frame.data.get('actions', [])
            return frame.card(title, content, actions)

    # ── Finish ───────────────────────────────────────────────────────

    def _finish(self, state: DialogueState):
        if self.ambiguity.present():
            self.ambiguity.resolve()
