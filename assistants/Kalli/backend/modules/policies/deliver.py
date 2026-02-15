from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.nlu import NLUResult
    from backend.modules.pex import PEXResult


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_1 = {'generate'}
_BATCH_2 = {'confirm_export', 'preview', 'ontology'}


class DeliverPolicy:

    def __init__(self, components: dict):
        self.prompt_engineer = components['prompt_engineer']
        self.context = components['context']
        self.memory = components['memory']
        self.display = components['display']
        self._get_tools_fn = components['get_tools']

    def execute(self, flow_name: str, flow_info: dict,
                nlu_result: 'NLUResult', tool_dispatcher) -> 'PEXResult':
        from backend.modules.pex import PEXResult

        if flow_name in _BATCH_2:
            return PEXResult(
                message="That feature is coming soon — stay tuned!",
                block_type='default',
            )

        handler = getattr(self, f'_do_{flow_name}', None)
        if handler:
            return handler(flow_info, nlu_result, tool_dispatcher)

        return self._llm_execute(flow_name, flow_info, nlu_result, tool_dispatcher)

    def _do_generate(self, flow_info, nlu_result, tool_dispatcher):
        return self._llm_execute('generate', flow_info, nlu_result, tool_dispatcher)

    def _llm_execute(self, flow_name, flow_info, nlu_result, tool_dispatcher):
        from backend.modules.pex import PEXResult

        skill_prompt = self._load_skill_template(flow_name)
        system, messages = self.prompt_engineer.build_skill_prompt(
            flow_name, flow_info, nlu_result.slots,
            self.context.compile_history(turns=5),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )
        tools = self._get_tools(flow_name, flow_info)

        text, tool_log = self.prompt_engineer.call_with_tools(
            system, messages, tools, tool_dispatcher, call_site='skill',
        )

        block_type = flow_info.get('output', 'list')
        block_data = {'flow_name': flow_name}
        for entry in tool_log:
            result = entry.get('result', {})
            if result.get('status') == 'success':
                result_data = result.get('result', {})
                if isinstance(result_data, dict):
                    block_data.update(result_data)
                elif isinstance(result_data, list):
                    block_data['items'] = result_data
        self.display.set_frame(block_type, block_data, source=flow_name)

        return PEXResult(
            message=text, block_type=block_type,
            block_data=block_data, tool_log=tool_log,
        )

    def _load_skill_template(self, flow_name: str) -> str | None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None

    def _get_tools(self, flow_name: str, flow_info: dict) -> list[dict]:
        return self._get_tools_fn(flow_name, flow_info)
