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
from backend.prompts.for_res import get_naturalize_prompt, build_clarification
from schemas.ontology import Intent
from utils.helper import output_for_flow
from backend.modules.templates import *
from backend.modules.templates import get_template as _get_template

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

        self.finish(agent_utt, frame, flow)
        return agent_utt, frame

    # ── Helpers ──────────────────────────────────────────────────────

    def _clarify(self) -> str:
        level = self.ambiguity.level or 'general'
        metadata = self.ambiguity.metadata or {}
        observation = self.ambiguity.observation

        clarification_text = build_clarification(level, metadata, observation)

        self.world.context.add_turn(
            'Agent', clarification_text, turn_type='clarification',
        )
        return clarification_text

    def generate(self, frame:DisplayFrame, state:DialogueState, flow:BaseFlow) -> str:
        template_info = _get_template(flow.name(), flow.intent)
        template = template_info.get('template', '{message}')

        match flow.intent:
            case 'Research': filled = fill_research_template(template, flow, frame)
            case 'Draft': filled = fill_draft_template(template, flow, frame)
            case 'Revise': filled = fill_revise_template(template, flow, frame)
            case 'Publish': filled = fill_publish_template(template, flow, frame)
            case 'Converse': filled = fill_converse_template(template, flow, frame)
            case 'Plan': filled = fill_plan_template(template, flow, frame)

        response = filled if template_info.get('skip_naturalize') else self.naturalize(filled, frame)
        return response

    def naturalize(self, raw_text:str, frame:DisplayFrame) -> str:
        if self.config.get('debug', False):
            return raw_text
        if not raw_text.strip():
            return raw_text
        if len(raw_text) < 80:
            return raw_text

        block_desc = ', '.join([block.block_type for block in frame.blocks])
        convo_history = self.world.context.compile_history(look_back=3)
        prompt = get_naturalize_prompt(raw_text, convo_history, block_desc)

        try:
            raw_output = self.engineer(prompt, 'naturalize', max_tokens=2048)
            return raw_output.strip() if raw_output.strip() else raw_text
        except Exception as ecp:
            print(f'RES naturalization error: {ecp}')
            return raw_text

    # ── Hooks ─────────────────────────────────────────────────────

    def start(self) -> list[BaseFlow]:
        popped = self.flow_stack.pop_completed()

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