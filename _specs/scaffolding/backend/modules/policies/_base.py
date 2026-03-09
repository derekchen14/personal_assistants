from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.display_frame import DisplayFrame


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_1: set[str] = set()   # Domain-specific: flows implemented in batch 1
_BATCH_2: set[str] = set()   # Domain-specific: flows deferred to batch 2


class BasePolicy:

    def __init__(self, components: dict):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.world = components['world']
        self._get_tools_fn = components['get_tools']

    def execute(self, flow_name: str, flow_info: dict,
                state: 'DialogueState', tool_dispatcher) -> 'DisplayFrame':
        from backend.components.display_frame import DisplayFrame

        if flow_name in _BATCH_2:
            frame = DisplayFrame(self.world.config)
            frame.set_frame('default', {'content': "That feature is coming soon — stay tuned!"})
            return frame

        return self._llm_execute(flow_name, flow_info, state, tool_dispatcher)

    def _llm_execute(self, flow_name, flow_info, state, tool_dispatcher):
        from backend.components.display_frame import DisplayFrame

        skill_prompt = self._load_skill_template(flow_name)
        system, messages = self.engineer.build_skill_prompt(
            flow_name, flow_info, state.slots,
            self.world.context.compile_history(turns=5),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )
        tools = self._get_tools_fn(flow_name, flow_info)

        text, tool_log = self.engineer.call_with_tools(
            system, messages, tools, tool_dispatcher, call_site='skill',
        )

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': text})
        return frame

    def _load_skill_template(self, flow_name: str) -> str | None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None
