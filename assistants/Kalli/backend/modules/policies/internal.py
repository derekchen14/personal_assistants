from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.modules.nlu import NLUResult
    from backend.modules.pex import PEXResult


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_2 = {'read_spec'}


class InternalPolicy:

    def __init__(self, components: dict):
        self.prompt_engineer = components['prompt_engineer']
        self.context = components['context']
        self.memory = components['memory']
        self._get_tools_fn = components['get_tools']

    def execute(self, flow_name: str, flow_info: dict,
                nlu_result: 'NLUResult', tool_dispatcher) -> 'PEXResult':
        from backend.modules.pex import PEXResult

        if flow_name in _BATCH_2:
            return PEXResult(message='', block_type='default')

        skill_prompt = self._load_skill_template(flow_name)
        system, messages = self.prompt_engineer.build_skill_prompt(
            flow_name, flow_info, nlu_result.slots,
            self.context.compile_history(turns=3),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )

        text, tool_log = self.prompt_engineer.call_with_tools(
            system, messages, [], tool_dispatcher, call_site='skill',
        )
        if text:
            self.memory.write_scratchpad(f'internal:{flow_name}', text[:500])

        return PEXResult(message='', block_type='default', tool_log=tool_log)

    def _load_skill_template(self, flow_name: str) -> str | None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None
