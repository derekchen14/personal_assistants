from __future__ import annotations

import json
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from backend.components.memory_manager import MemoryManager
from backend.utilities.services import (
    DatasetService, QueryService, ChartService, TransformService,
)
from backend.modules.policies import (
    ConversePolicy, CleanPolicy, TransformPolicy, AnalyzePolicy,
    ReportPolicy, PlanPolicy, InternalPolicy,
)
from schemas.ontology import Intent

if TYPE_CHECKING:
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.world import World


_UNSUPPORTED = {
    'think', 'context',
}


class PEX:

    def __init__(self, config: MappingProxyType, ambiguity: AmbiguityHandler,
                 engineer: PromptEngineer, memory: MemoryManager,
                 world: 'World'):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.memory = memory
        self.world = world
        self.flow_stack = world.flow_stack

        self._dataset_service = DatasetService()
        self._query_service = QueryService()
        self._chart_service = ChartService()
        self._transform_service = TransformService()

        self._tools: dict[str, tuple[object, str]] = {
            'dataset_load':    (self._dataset_service, 'load'),
            'sql_execute':     (self._query_service, 'execute_sql'),
            'python_execute':  (self._query_service, 'execute_python'),
            'column_analyze':  (self._query_service, 'analyze_column'),
            'chart_render':    (self._chart_service, 'render'),
            'formula_apply':   (self._transform_service, 'apply_formula'),
            'merge_run':       (self._transform_service, 'merge'),
            'pivot_run':       (self._transform_service, 'pivot'),
            'validate_check':  (self._transform_service, 'validate'),
            'export_run':      (self._transform_service, 'export'),
        }

        components = {
            'engineer': engineer,
            'memory': memory,
            'config': config,
            'get_tools': self.get_tools_for_flow,
        }
        plan_components = {**components, 'flow_stack': self.flow_stack}
        self._policies: dict[str, object] = {
            Intent.CONVERSE: ConversePolicy(components),
            Intent.CLEAN: CleanPolicy(components),
            Intent.TRANSFORM: TransformPolicy(components),
            Intent.ANALYZE: AnalyzePolicy(components),
            Intent.REPORT: ReportPolicy(components),
            Intent.PLAN: PlanPolicy(plan_components),
            Intent.INTERNAL: InternalPolicy(components),
        }

    def execute(self, state: DialogueState,
                context: 'ContextCoordinator') -> tuple[DisplayFrame, bool]:
        active_flow = self.flow_stack.get_active_flow()
        if not active_flow:
            frame = DisplayFrame(self.config)
            return frame, False

        flow_name = active_flow.name()

        check_result = self._check(active_flow, context)
        if check_result:
            return check_result, False

        if flow_name in _UNSUPPORTED:
            self.flow_stack.mark_complete(result={'unsupported': True})
            frame = self.world.latest_frame() or DisplayFrame(self.config)
            return frame, False

        policy = self._policies.get(active_flow.intent)
        if policy:
            frame = policy.execute(
                active_flow, state, context, self._dispatch_tool,
            )
        else:
            frame = DisplayFrame(self.config)

        if active_flow.intent != Intent.PLAN:
            self.flow_stack.mark_complete(result={'flow_name': flow_name})
        self.world.insert_frame(frame)

        if frame.has_content():
            text_summary = frame.data.get('content', '')
            if text_summary:
                self.memory.write_scratchpad(
                    f'flow:{flow_name}',
                    f'{flow_name}: {text_summary[:200]}',
                )

        self._verify()

        keep_going = state.keep_going
        return frame, keep_going

    # -- Pre-hook ---------------------------------------------------------

    def _check(self, flow,
               context: 'ContextCoordinator') -> DisplayFrame | None:
        if flow.name() in _UNSUPPORTED:
            return None

        required_missing = []
        for slot_name, slot in flow.slots.items():
            if slot.priority == 'required' and not slot.filled:
                required_missing.append(slot_name)

        if required_missing:
            for slot_name in list(required_missing):
                filled = self._fill_from_context(slot_name, context)
                if filled:
                    flow.fill_slot_values({slot_name: filled})
                    required_missing.remove(slot_name)

        if required_missing:
            self.ambiguity.declare(
                'specific',
                metadata={'missing_slots': required_missing},
                observation=f'I need the following to proceed: {", ".join(required_missing)}',
            )
            frame = DisplayFrame(self.config)
            frame.set_frame('default', {'message': self.ambiguity.ask()})
            return frame

        tools = self.get_tools_for_flow(flow)
        for tool in tools:
            caps = tool.get('capabilities', {})
            if (caps.get('accesses_private_data')
                    and caps.get('receives_untrusted_input')
                    and caps.get('communicates_externally')):
                self.ambiguity.declare(
                    'confirmation',
                    metadata={'tool': tool['name'], 'reason': 'lethal_trifecta'},
                    observation=(
                        f'This action requires your approval because '
                        f'"{tool["name"]}" accesses private data, accepts '
                        f'user input, and communicates externally.'
                    ),
                )
                frame = DisplayFrame(self.config)
                frame.set_frame('confirmation', {
                    'prompt': self.ambiguity.ask(),
                    'confirm_label': 'Approve',
                    'cancel_label': 'Cancel',
                })
                return frame

        return None

    def _fill_from_context(self, slot_name: str,
                           context: 'ContextCoordinator') -> str | None:
        if slot_name in ('dataset_id', 'source'):
            state = self.world.current_state()
            if state and state.active_dataset:
                return state.active_dataset

        scratchpad_val = self.memory.read_scratchpad(slot_name)
        if scratchpad_val:
            return scratchpad_val

        for turn in reversed(context.recent_turns(3)):
            if turn['speaker'] == 'User' and slot_name.lower() in turn['text'].lower():
                return turn['text']
        return None

    # -- Tool dispatch ----------------------------------------------------

    def _dispatch_tool(self, tool_name: str, tool_input: dict) -> dict:
        self.world.context.add_turn(
            'Agent', f'[tool:{tool_name}] {json.dumps(tool_input)[:200]}',
            turn_type='action',
        )
        try:
            if tool_name in self._tools:
                service, method_name = self._tools[tool_name]
                method = getattr(service, method_name)
                return method(**tool_input)
            elif tool_name == 'context_coordinator':
                return self._dispatch_context_tool(tool_input)
            elif tool_name == 'memory_manager':
                return self.memory.dispatch_tool(
                    tool_input.get('action', ''),
                    tool_input,
                )
            elif tool_name == 'flow_stack':
                return self._dispatch_flow_stack_tool(tool_input)
            else:
                return {
                    'status': 'error',
                    'error_category': 'invalid_input',
                    'message': f'Unknown tool: {tool_name}',
                    'retryable': False,
                }
        except Exception as e:
            return {
                'status': 'error',
                'error_category': 'server_error',
                'message': f'{type(e).__name__}: {e}',
                'retryable': False,
            }

    def _dispatch_context_tool(self, params: dict) -> dict:
        action = params.get('action', '')
        if action == 'get_history':
            turns = params.get('turns', 3)
            history = self.world.context.compile_history(look_back=turns)
            return {'status': 'success', 'result': history}
        elif action == 'get_turn':
            turn_id = params.get('turn_id', '')
            turn = self.world.context.get_turn(turn_id)
            return {'status': 'success', 'result': turn}
        elif action == 'get_checkpoint':
            label = params.get('label', '')
            cp = self.world.context.get_checkpoint(label)
            return {'status': 'success', 'result': cp}
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    def _dispatch_flow_stack_tool(self, params: dict) -> dict:
        action = params.get('action', '')
        if action == 'get_slots':
            flow = self.flow_stack.get_active_flow()
            if flow:
                return {'status': 'success', 'result': flow.slot_values_dict()}
            return {'status': 'success', 'result': {}}
        elif action == 'get_flow_meta':
            flow = self.flow_stack.get_active_flow()
            if flow:
                return {'status': 'success', 'result': flow.to_dict()}
            return {'status': 'success', 'result': None}
        elif action == 'get_stack':
            return {'status': 'success', 'result': self.flow_stack.to_list()}
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    # -- Tool definitions -------------------------------------------------

    @staticmethod
    def _thaw(obj):
        if isinstance(obj, MappingProxyType):
            return {k: PEX._thaw(v) for k, v in obj.items()}
        if isinstance(obj, tuple):
            return [PEX._thaw(item) for item in obj]
        return obj

    def _get_tool_def(self, tool_id: str) -> dict | None:
        tools = self.config.get('tools', {})
        tool = tools.get(tool_id)
        if not tool:
            return None
        return {
            'name': tool.get('tool_id', tool_id),
            'description': tool.get('description', ''),
            'input_schema': self._thaw(tool.get('input_schema', {})),
            'capabilities': self._thaw(tool.get('capabilities', {})),
        }

    def get_tools_for_flow(self, flow) -> list[dict]:
        tools = list(self._component_tool_definitions())
        for tool_name in flow.tools:
            tool_def = self._get_tool_def(tool_name)
            if tool_def:
                tools.append(tool_def)
        return tools

    def _component_tool_definitions(self) -> list[dict]:
        return [
            {
                'name': 'context_coordinator',
                'description': 'Access conversation history. Actions: get_history, get_turn, get_checkpoint',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['get_history', 'get_turn', 'get_checkpoint']},
                        'turns': {'type': 'integer'},
                        'turn_id': {'type': 'string'},
                        'label': {'type': 'string'},
                    },
                    'required': ['action'],
                },
            },
            {
                'name': 'memory_manager',
                'description': 'Read/write session scratchpad and user preferences. Actions: read_scratchpad, write_scratchpad, read_preferences',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['read_scratchpad', 'write_scratchpad', 'read_preferences']},
                        'key': {'type': 'string'},
                        'value': {'type': 'string'},
                    },
                    'required': ['action'],
                },
            },
            {
                'name': 'flow_stack',
                'description': 'Read flow stack state. Actions: get_slots, get_flow_meta, get_stack',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['get_slots', 'get_flow_meta', 'get_stack']},
                    },
                    'required': ['action'],
                },
            },
        ]

    # -- Post-hook --------------------------------------------------------

    def _verify(self):
        state = self.world.current_state()
        if state and state.keep_going and not self.flow_stack.get_pending_flows():
            state.keep_going = False
