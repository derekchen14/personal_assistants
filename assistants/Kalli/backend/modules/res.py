from __future__ import annotations

import logging
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.dialogue_state import DialogueState
from backend.components.task_artifact import TaskArtifact

log = logging.getLogger(__name__)
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from schemas.ontology import Intent

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

    def respond(self, artifact: TaskArtifact) -> tuple[str, TaskArtifact]:
        completed_flows = self._start()

        if self.ambiguity.present():
            text = self._clarify()
            return text, artifact

        state = self.world.current_state()
        intent = state.pred_intent if state else 'Converse'

        log.info('  res intent=%s  keep_going=%s  has_frame=%s',
                 intent, state.keep_going if state else False,
                 artifact.has_content())

        # Check if flow was unsupported (PEX returned carryover artifact)
        active = self.world.flow_stack.get_active_flow()
        if active and active.result and active.result.get('unsupported'):
            text = _UNSUPPORTED_MESSAGE
            self.world.context.add_turn('Agent', text, turn_type='agent_response')
            return text, artifact

        if intent == Intent.INTERNAL.value:
            self._finish('', artifact)
            return '', artifact

        if intent == Intent.PLAN.value and state and state.keep_going:
            self._finish('', artifact)
            return '', artifact

        text = self._generate(artifact, state, completed_flows)

        self._finish(text, artifact)

        if text:
            self.world.context.add_turn('Agent', text, turn_type='agent_response')

        return text, artifact

    # ── Pre-hook ──────────────────────────────────────────────────────

    def _start(self) -> list:
        popped = self.world.flow_stack.pop_completed_and_invalid()

        completed = [f for f in popped if f.result is not None]
        for flow in completed:
            if flow.intent == Intent.PLAN.value:
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

        history_text = self.world.context.compile_history(look_back=3)

        clarification_text = self.engineer.build_clarification_prompt(
            level, metadata, observation,
            history_text,
        )

        self.world.context.add_turn(
            'Agent', clarification_text, turn_type='clarification',
        )
        return clarification_text

    # ── Generate ──────────────────────────────────────────────────────

    def _generate(self, artifact: TaskArtifact, state: DialogueState | None,
                  completed_flows: list) -> str:
        content = artifact.data.get('content', '') if artifact.has_content() else ''
        if not content:
            return ''

        intent = state.pred_intent if state else 'Converse'
        flow_name = state.flow_name if state else ''

        raw = self._template_fill(content, state, intent, flow_name)

        tmpl_info = self.engineer.get_template(flow_name, intent)
        if tmpl_info.get('skip_naturalize'):
            return raw

        return self._naturalize(raw, artifact.block_type if artifact.has_content() else None)

    def _template_fill(self, message: str, state: DialogueState | None,
                       intent: str, flow_name: str) -> str:
        tmpl_info = self.engineer.get_template(flow_name, intent)
        template = tmpl_info.get('template', '{message}')

        active = self.world.flow_stack.get_active_flow()
        slot_summary = ''
        if active and active.slots:
            parts = [f'{k}: {v}' for k, v in active.slots.items()]
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

        history_text = self.world.context.compile_history(look_back=3)

        system, messages = self.engineer.build_naturalize_prompt(
            raw_text, history_text, block_type,
        )

        try:
            text = self.engineer.call_text(
                system=system, messages=messages,
                call_site='low', max_tokens=2048,
            )
            return text.strip() if text.strip() else raw_text
        except Exception as e:
            print(f'RES naturalization error: {e}')
            return raw_text

    # ── Post-hook ─────────────────────────────────────────────────────

    def _finish(self, text: str, artifact: TaskArtifact):
        state = self.world.current_state()
        intent = state.pred_intent if state else 'Converse'

        if intent not in (Intent.INTERNAL.value, Intent.PLAN.value):
            if not text and not artifact.has_content():
                pass  # orchestrator handles fallback

        # No display.clear() needed — frames are per-turn now
