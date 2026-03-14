from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.components.dialogue_state import DialogueState
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.display_frame import DisplayFrame
    from backend.components.flow_stack.parents import BaseFlow


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_1 = {'plot', 'trend', 'export', 'summarize'}
_BATCH_2 = {'dashboard', 'style', 'design'}


class ReportPolicy:

    def __init__(self, components: dict):
        self.engineer = components['engineer']
        self.memory = components['memory']
        self.config = components['config']
        self._get_tools_fn = components['get_tools']

    def execute(self, flow: 'BaseFlow', state: 'DialogueState',
                context: 'ContextCoordinator', tools) -> 'DisplayFrame':
        from backend.components.display_frame import DisplayFrame

        if flow.name() in _BATCH_2:
            frame = DisplayFrame(self.config)
            frame.set_frame('default', {'content': "That feature is coming soon — stay tuned!"})
            return frame

        return self._llm_execute(flow, state, context, tools)

    def _llm_execute(self, flow, state, context, tools):
        from backend.components.display_frame import DisplayFrame
        from schemas.ontology import FLOW_CATALOG

        skill_prompt = self._load_skill_template(flow.name())
        system, messages = self.engineer.build_skill_prompt(
            flow.name(), flow, flow.slot_values_dict(),
            context.compile_history(look_back=5),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )
        tool_defs = self._get_tools_fn(flow)

        text, tool_log = self.engineer.call_with_tools(
            system, messages, tool_defs, tools, call_site='skill',
        )

        frame = DisplayFrame(self.config)
        flow_info = FLOW_CATALOG.get(flow.name(), {})
        block_type = flow_info.get('output', 'card')
        block_data = {'flow_name': flow.name(), 'content': text}
        for entry in tool_log:
            result = entry.get('result', {})
            if result.get('status') == 'success':
                result_data = result.get('result', {})
                if isinstance(result_data, dict):
                    block_data.update(result_data)
                elif isinstance(result_data, list):
                    block_data['items'] = result_data
        frame.set_frame(block_type, block_data, source=flow.name())
        return frame

    def _load_skill_template(self, flow_name: str) -> str | None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None
