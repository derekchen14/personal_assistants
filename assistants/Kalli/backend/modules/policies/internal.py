from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.display_frame import DisplayFrame


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_2 = {'study'}


class InternalPolicy:

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
            frame.set_frame('default', {'content': ''}, source=flow_name)
            return frame

        skill_prompt = self._load_skill_template(flow_name)
        system, messages = self.engineer.build_skill_prompt(
            flow_name, flow_info, state.slots,
            self.world.context.compile_history(turns=3),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )

        text, tool_log = self.engineer.call_with_tools(
            system, messages, [], tool_dispatcher, call_site='skill',
        )
        if text:
            self.memory.write_scratchpad(f'internal:{flow_name}', text[:500])

        frame = DisplayFrame(self.world.config)
        frame.set_frame('default', {'content': ''}, source=flow_name)
        return frame

    def _load_skill_template(self, flow_name: str) -> str | None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None
