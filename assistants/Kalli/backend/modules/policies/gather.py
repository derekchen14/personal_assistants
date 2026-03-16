from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.dialogue_state import DialogueState
    from backend.components.display_frame import DisplayFrame


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_1 = {'scope', 'persona', 'intent', 'entity'}
_BATCH_2 = {'teach', 'propose'}


class GatherPolicy:

    def __init__(self, components: dict):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.config = components['config']
        self._get_tools_fn = components['get_tools']

    def execute(self, flow_info: dict, state: 'DialogueState',
                context: 'ContextCoordinator',
                filled_slots: dict, tool_dispatcher) -> 'DisplayFrame':
        from backend.components.display_frame import DisplayFrame
        flow_name = flow_info['name']

        if flow_name in _BATCH_2:
            frame = DisplayFrame(self.config)
            frame.set_frame('default', {'content': "That feature is coming soon — stay tuned!"}, source=flow_name)
            return frame

        handler = getattr(self, f'_do_{flow_name}', None)
        if handler:
            return handler(flow_info, state, context, filled_slots, tool_dispatcher)

        return self._llm_execute(flow_info, state, context, filled_slots, tool_dispatcher)

    def _do_scope(self, flow_info, state, context, filled_slots, tool_dispatcher):
        return self._llm_execute(flow_info, state, context, filled_slots, tool_dispatcher)

    def _do_persona(self, flow_info, state, context, filled_slots, tool_dispatcher):
        return self._llm_execute(flow_info, state, context, filled_slots, tool_dispatcher)

    def _do_intent(self, flow_info, state, context, filled_slots, tool_dispatcher):
        return self._llm_execute(flow_info, state, context, filled_slots, tool_dispatcher)

    def _do_entity(self, flow_info, state, context, filled_slots, tool_dispatcher):
        return self._llm_execute(flow_info, state, context, filled_slots, tool_dispatcher)

    def _llm_execute(self, flow_info, state, context, filled_slots, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame
        flow_name = flow_info['name']

        skill_prompt = self._load_skill_template(flow_name)
        system, messages = self.engineer.build_skill_prompt(
            flow_name, flow_info, filled_slots,
            context.compile_history(look_back=5),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )
        tools = self._get_tools(flow_info)

        text, tool_log = self.engineer.call_with_tools(
            system, messages, tools, tool_dispatcher, call_site='skill',
        )

        frame = DisplayFrame(self.config)
        block_type = flow_info.get('output', 'form')
        block_data = {'flow_name': flow_name, 'content': text}
        for entry in tool_log:
            result = entry.get('result', {})
            if result.get('status') == 'success':
                result_data = result.get('result', {})
                if isinstance(result_data, dict):
                    block_data.update(result_data)
        frame.set_frame(block_type, block_data, source=flow_name)
        return frame

    def _load_skill_template(self, flow_name: str) -> str | None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None

    def _get_tools(self, flow_info: dict) -> list[dict]:
        return self._get_tools_fn(flow_info)
