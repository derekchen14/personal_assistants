from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.dialogue_state import DialogueState
    from backend.components.display_frame import DisplayFrame


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_1 = {'chat', 'next', 'feedback'}
_BATCH_2 = {'preference', 'endorse'}


class ConversePolicy:

    def __init__(self, components: dict):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.config = components['config']
        self._get_tools_fn = components['get_tools']

    def execute(self, flow_name: str, flow_info: dict,
                state: 'DialogueState', context: 'ContextCoordinator',
                filled_slots: dict, tool_dispatcher) -> 'DisplayFrame':
        from backend.components.display_frame import DisplayFrame

        if flow_name in _BATCH_2:
            frame = DisplayFrame(self.config)
            frame.set_frame('default', {'content': "That feature is coming soon — stay tuned!"}, source=flow_name)
            return frame

        handler = getattr(self, f'_do_{flow_name}', None)
        if handler:
            return handler(flow_info, state, context, filled_slots, tool_dispatcher)

        return self._llm_execute(flow_name, flow_info, state, context, filled_slots, tool_dispatcher)

    def _do_chat(self, flow_info, state, context, filled_slots, tool_dispatcher):
        return self._llm_execute('chat', flow_info, state, context, filled_slots, tool_dispatcher)

    def _do_next(self, flow_info, state, context, filled_slots, tool_dispatcher):
        return self._llm_execute('next', flow_info, state, context, filled_slots, tool_dispatcher)

    def _do_feedback(self, flow_info, state, context, filled_slots, tool_dispatcher):
        return self._llm_execute('feedback', flow_info, state, context, filled_slots, tool_dispatcher)

    def _llm_execute(self, flow_name, flow_info, state, context, filled_slots, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame

        skill_prompt = self._load_skill_template(flow_name)
        system, messages = self.engineer.build_skill_prompt(
            flow_name, flow_info, filled_slots,
            context.compile_history(look_back=5),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )
        tools = self._get_tools(flow_name, flow_info)

        text, tool_log = self.engineer.call_with_tools(
            system, messages, tools, tool_dispatcher, call_site='skill',
        )

        frame = DisplayFrame(self.config)
        frame.set_frame('default', {'content': text}, source=flow_name)
        return frame

    def _load_skill_template(self, flow_name: str) -> str | None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None

    def _get_tools(self, flow_name: str, flow_info: dict) -> list[dict]:
        return self._get_tools_fn(flow_name, flow_info)
