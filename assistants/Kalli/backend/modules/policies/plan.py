from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from schemas.ontology import FLOW_CATALOG

if TYPE_CHECKING:
    from backend.modules.nlu import NLUResult
    from backend.modules.pex import PEXResult


_SKILL_DIR = Path(__file__).resolve().parents[2] / 'prompts' / 'skills'

_BATCH_1 = {'onboard'}
_BATCH_2 = {'research', 'expand'}


class PlanPolicy:

    def __init__(self, components: dict):
        self.prompt_engineer = components['prompt_engineer']
        self.context = components['context']
        self.memory = components['memory']
        self.display = components['display']
        self.dialogue_state = components['dialogue_state']
        self.flow_stack = components['flow_stack']
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

    def _do_onboard(self, flow_info, nlu_result, tool_dispatcher):
        from backend.modules.pex import PEXResult

        skill_prompt = self._load_skill_template('onboard')
        system, messages = self.prompt_engineer.build_skill_prompt(
            'onboard', flow_info, nlu_result.slots,
            self.context.compile_history(turns=5),
            self.memory.read_scratchpad(),
            skill_prompt=skill_prompt,
        )
        tools = self._get_tools('onboard', flow_info)

        text, tool_log = self.prompt_engineer.call_with_tools(
            system, messages, tools, tool_dispatcher, call_site='skill',
        )

        self.dialogue_state.update_flags(has_plan=True, keep_going=True)

        for edge_flow_name in flow_info.get('edge_flows', []):
            edge_flow = FLOW_CATALOG.get(edge_flow_name)
            if edge_flow:
                self.flow_stack.push(
                    edge_flow_name, edge_flow['dax'],
                    edge_flow['intent'].value,
                )

        return PEXResult(
            message=text, block_type='list',
            block_data={
                'title': f'Plan: {flow_info.get("description", "onboard")}',
                'items': flow_info.get('edge_flows', []),
            },
            tool_log=tool_log,
        )

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

        self.dialogue_state.update_flags(has_plan=True, keep_going=True)

        for edge_flow_name in flow_info.get('edge_flows', []):
            edge_flow = FLOW_CATALOG.get(edge_flow_name)
            if edge_flow:
                self.flow_stack.push(
                    edge_flow_name, edge_flow['dax'],
                    edge_flow['intent'].value,
                )

        return PEXResult(
            message=text, block_type='list',
            block_data={
                'title': f'Plan: {flow_name}',
                'items': flow_info.get('edge_flows', []),
            },
            tool_log=tool_log,
        )

    def _load_skill_template(self, flow_name: str) -> str | None:
        path = _SKILL_DIR / f'{flow_name}.md'
        if path.exists():
            return path.read_text(encoding='utf-8')
        return None

    def _get_tools(self, flow_name: str, flow_info: dict) -> list[dict]:
        return self._get_tools_fn(flow_name, flow_info)
