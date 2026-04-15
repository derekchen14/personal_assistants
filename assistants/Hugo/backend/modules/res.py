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
            return self._clarify(), frame

        state = self.world.current_state()
        flow = completed_flows[-1] if completed_flows else self.flow_stack.get_flow()

        if flow.intent == Intent.INTERNAL:
            return '', frame
        if flow.intent == Intent.PLAN and state.keep_going:
            self.finish('', frame, flow)
            return '', frame

        agent_utt = self.generate(frame, state, flow)
        frame = self.display(frame, flow)

        self.finish(agent_utt, frame, flow)
        return agent_utt, frame

    # ── Helpers ──────────────────────────────────────────────────────

    def build_payload_frame(self, frame:DisplayFrame, text:str) -> dict:
        data = frame.to_dict()
        has_text = bool(text and text.strip())
        has_blocks = bool(frame.blocks)
        if has_text and has_blocks:  data['panel'] = 'split'
        elif has_blocks:             data['panel'] = 'bottom'
        else:                        data['panel'] = 'top'
        return data

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

    def generate(self, frame:DisplayFrame, state:DialogueState, flow:BaseFlow) -> str:
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
            block_type = frame.block_type() if frame.blocks else None
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
            text = self.engineer.call(messages, system=system,
                task='naturalize', max_tokens=2048,
            )
            return text.strip() if text.strip() else raw_text
        except Exception as ecp:
            print(f'RES naturalization error: {ecp}')
            return raw_text

    def display(self, frame:DisplayFrame, flow:BaseFlow) -> DisplayFrame:
        """Append any RES-driven blocks (e.g. proposals selection) to the frame."""
        if hasattr(flow, 'stage') and flow.stage == 'propose':
            proposal_slot = flow.slots['proposals']
            if len(proposal_slot.options) > 0:                
                block_data = {
                    'type': 'selection',
                    'data': {'candidates': proposal_slot.options},
                }
                frame.add_block(block_data)
        return frame

    # ── Hooks ─────────────────────────────────────────────────────

    def start(self) -> list[BaseFlow]:
        popped = self.flow_stack.pop_completed_and_invalid()

        completed = [flow for flow in popped if flow.status == 'Completed']
        for flow in completed:
            if flow.intent == Intent.PLAN:
                state = self.world.current_state()
                state.update_flags(has_plan=False)
                state.structured_plan = {}

        if len(completed) > 1:
            self.world.context.save_checkpoint(
                'multi_flow_completion',
                data={'completed_count': len(completed)},
            )

        return completed

    def finish(self, text:str, frame:DisplayFrame, flow:BaseFlow):
        if flow.intent not in (Intent.INTERNAL, Intent.PLAN):
            if not text and not frame.blocks:
                pass  # orchestrator handles fallback