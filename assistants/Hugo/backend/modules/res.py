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
from backend.modules.templates import *

if TYPE_CHECKING:
    from backend.components.world import World


class RES(object):

    def __init__(self, config:MappingProxyType, ambiguity:AmbiguityHandler,
                 engineer:PromptEngineer, world:'World'):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.world = world
        self.flow_stack = world.flow_stack

    def respond(self, frame:DisplayFrame) -> tuple[str, DisplayFrame]:
        completed_flows = self.start()

        if self.ambiguity.present():
            text = self._clarify()
            return text, frame

        state = self.world.current_state()
        intent = state.pred_intent if state else 'Converse'

        log.info('  res intent=%s  keep_going=%s  has_frame=%s',
                 intent, state.keep_going if state else False,
                 frame.has_content())

        if intent == Intent.INTERNAL:
            return '', frame
        if intent == Intent.PLAN and state and state.keep_going:
            self.finish('', frame)
            return '', frame

        text = self.generate(frame, state, completed_flows)
        self.display(frame, state, text)
        self.finish(text, frame)

        if text:
            self.world.context.add_turn('Agent', text, turn_type='agent_response')

        return text, frame

    # ── Pre-hook ──────────────────────────────────────────────────────

    def start(self) -> list[BaseFlow]:
        popped = self.flow_stack.pop_completed_and_invalid()

        completed = [flow for flow in popped if flow.status == 'Completed']
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

    def generate(self, frame:DisplayFrame, state:DialogueState, completed_flows:list[BaseFlow]) -> str:
        if len(completed_flows) > 0:
            # assume just a single flow for now
            flow = completed_flows[0]
        else:
            # we can't assume that there is an active flow since it may be completed, so we check there first
            flow = self.flow_stack.get_active_flow()

        template_info = self.engineer.get_template(flow.name(), flow.intent)
        template = template_info.get('template', '{message}')

        match flow.intent:
            case 'Research': filled = fill_research_template(template, flow, frame)
            case 'Draft': filled = fill_draft_template(template, flow, frame)
            case 'Revise': filled = fill_revise_template(template, flow, frame)
            case 'Publish': filled = fill_publish_template(template, flow, frame)
            case 'Converse': filled = fill_converse_template(template, flow, frame)
            case 'Plan': filled = fill_plan_template(template, flow, frame)

        if template_info.get('skip_naturalize'):
            response = filled
        else:
            block_type = frame.block_type if frame.has_content() else None
            response = self._naturalize(filled, block_type)
        return response

    def _naturalize(self, raw_text:str, block_type:str|None) -> str:
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
        except Exception as ecp:
            print(f'RES naturalization error: {ecp}')
            return raw_text

    # ── Display ───────────────────────────────────────────────────────

    def display(self, frame:DisplayFrame, state:DialogueState|None,
                text:str) -> dict | None:
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

    def finish(self, text:str, frame:DisplayFrame):
        state = self.world.current_state()
        intent = state.pred_intent if state else 'Converse'

        if intent not in (Intent.INTERNAL, Intent.PLAN):
            if not text and not frame.has_content():
                pass  # orchestrator handles fallback