from __future__ import annotations

import json
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.context_coordinator import ContextCoordinator
from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from backend.components.memory_manager import MemoryManager
from backend.utilities.services import (
    SpecService, ConfigService, GeneratorService, CodeService, LessonService,
)
from backend.modules.policies import (
    ExplorePolicy, GatherPolicy, PersonalizePolicy, DeliverPolicy,
    ConversePolicy, PlanPolicy, InternalPolicy,
)
from schemas.ontology import FLOW_CATALOG, Intent

if TYPE_CHECKING:
    from backend.components.world import World


_UNSUPPORTED = {
    'style', 'dismiss', 'recommend', 'compare',
    'remove', 'validate', 'package', 'test', 'deploy', 'secure', 'version',
    'finalize', 'redesign',
    'recap', 'recall', 'retrieve', 'search', 'peek', 'audit', 'emit',
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

        self._spec_service = SpecService()
        self._config_service = ConfigService()
        self._generator_service = GeneratorService(self._config_service)
        self._code_service = CodeService()
        self._lesson_service = LessonService()

        self._tool_definitions = self._build_tool_definitions()

        components = {
            'engineer': engineer,
            'memory': memory,
            'config': config,
            'get_tools': self.get_tools_for_flow,
            'flow_stack': self.world.flow_stack,
        }
        self._policies: dict[str, object] = {
            Intent.EXPLORE: ExplorePolicy(components),
            Intent.GATHER: GatherPolicy(components),
            Intent.PERSONALIZE: PersonalizePolicy(components),
            Intent.DELIVER: DeliverPolicy(components),
            Intent.CONVERSE: ConversePolicy(components),
            Intent.PLAN: PlanPolicy(components),
            Intent.INTERNAL: InternalPolicy(components),
        }

    def execute(self, state: DialogueState,
                context: ContextCoordinator) -> tuple[DisplayFrame, bool]:
        flow_name = state.flow_name
        flow_info = FLOW_CATALOG.get(flow_name)
        if not flow_info:
            frame = DisplayFrame(self.config)
            return frame, False

        flow_entry = self.world.flow_stack.get_active_flow()

        check_result = self._check(flow_entry, context)
        if check_result:
            return check_result, False

        if flow_name in _UNSUPPORTED:
            self.world.flow_stack.mark_complete(result={'unsupported': True})
            frame = self.world.latest_frame() or DisplayFrame(self.config)
            return frame, False

        # Policy keys are Intent enums; state.pred_intent is a string
        policy = None
        for key, val in self._policies.items():
            if key.value == state.pred_intent:
                policy = val
                break

        if policy:
            def tool_dispatcher(tool_name, tool_input):
                return self._dispatch_tool(tool_name, tool_input)

            filled_slots = flow_entry.slot_values_dict() if flow_entry else {}
            frame = policy.execute(
                flow_name, flow_info, state, context, filled_slots,
                tool_dispatcher,
            )
        else:
            frame = DisplayFrame(self.config)

        if state.pred_intent != Intent.PLAN.value:
            self.world.flow_stack.mark_complete(result={'flow_name': flow_name})
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

    # ── Pre-hook ─────────────────────────────────────────────────────

    def _check(self, flow_entry, context: ContextCoordinator) -> DisplayFrame | None:
        if not flow_entry:
            return None

        flow_name = flow_entry.flow_name if hasattr(flow_entry, 'flow_name') else ''
        if flow_name in _UNSUPPORTED:
            return None

        required_missing = []
        for slot_name, slot in (flow_entry.slots or {}).items():
            if hasattr(slot, 'priority') and slot.priority == 'required' and not slot.filled:
                required_missing.append(slot_name)

        if required_missing:
            for slot_name in list(required_missing):
                filled = self._fill_from_context(slot_name, context)
                if filled:
                    slot = flow_entry.slots[slot_name]
                    if hasattr(slot, 'add_one'):
                        slot.add_one(filled)
                    else:
                        slot.value = filled
                        slot.check_if_filled()
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
        return None

    def _fill_from_context(self, slot_name: str,
                           context: ContextCoordinator) -> str | None:
        scratchpad_val = self.memory.read_scratchpad(slot_name)
        if scratchpad_val:
            return scratchpad_val

        recent = context.recent_turns(3)
        for turn in reversed(recent):
            if turn.get('speaker') == 'User' and slot_name.lower() in turn.get('text', '').lower():
                return turn.get('text', '')
        return None

    # ── Tool dispatch ────────────────────────────────────────────────

    def _dispatch_tool(self, tool_name: str, tool_input: dict) -> dict:
        self.world.context.add_turn(
            'Agent', f'[tool:{tool_name}] {json.dumps(tool_input)[:200]}',
            turn_type='action',
        )
        try:
            if tool_name == 'spec_read':
                return self._spec_service.read(
                    tool_input.get('spec_name', ''),
                    tool_input.get('section'),
                )
            elif tool_name == 'config_read':
                return self._config_service.read(tool_input.get('section'))
            elif tool_name == 'config_write':
                return self._config_service.write(
                    tool_input['section'],
                    tool_input['data'],
                    tool_input.get('merge', True),
                )
            elif tool_name == 'ontology_generate':
                return self._generator_service.ontology(
                    tool_input.get('target_dir'),
                    tool_input.get('dry_run', False),
                )
            elif tool_name == 'yaml_generate':
                return self._generator_service.yaml(
                    tool_input.get('target_dir'),
                    tool_input.get('dry_run', False),
                )
            elif tool_name == 'python_execute':
                return self._code_service.execute(
                    tool_input.get('code', ''),
                    tool_input.get('timeout_ms', 30000),
                )
            elif tool_name == 'lesson_store':
                return self._lesson_service.store(
                    tool_input.get('content', ''),
                    tool_input.get('category'),
                    tool_input.get('tags'),
                )
            elif tool_name == 'lesson_search':
                return self._lesson_service.search(
                    tool_input.get('query', ''),
                    tool_input.get('category'),
                    tool_input.get('limit', 10),
                )
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
                return {'status': 'error', 'message': f'Unknown tool: {tool_name}'}
        except Exception as e:
            return {
                'status': 'error',
                'error_category': 'server_error',
                'message': f'{type(e).__name__}: {e}',
            }

    def _dispatch_context_tool(self, params: dict) -> dict:
        action = params.get('action', '')
        if action == 'get_history':
            look_back = params.get('turns', 3)
            history = self.world.context.compile_history(look_back=look_back)
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
            active = self.world.flow_stack.get_active_flow()
            if active:
                return {'status': 'success', 'result': active.slot_values_dict()}
            return {'status': 'success', 'result': {}}
        elif action == 'get_flow_meta':
            active = self.world.flow_stack.get_active_flow()
            if active:
                return {'status': 'success', 'result': active.to_dict()}
            return {'status': 'success', 'result': None}
        elif action == 'get_stack':
            return {'status': 'success', 'result': self.world.flow_stack.to_list()}
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    # ── Tool definitions ─────────────────────────────────────────────

    def get_tools_for_flow(self, flow_name: str, flow_info: dict) -> list[dict]:
        tools = []
        intent = flow_info.get('intent', Intent.CONVERSE)
        intent_val = intent.value

        tools.extend(self._component_tool_definitions())

        if intent_val in ('Explore', 'Gather', 'Personalize', 'Deliver'):
            tools.append(self._tool_definitions.get('spec_read'))
            tools.append(self._tool_definitions.get('config_read'))

        if intent_val in ('Gather', 'Personalize'):
            tools.append(self._tool_definitions.get('config_write'))

        if intent_val == 'Deliver':
            tools.append(self._tool_definitions.get('ontology_generate'))
            tools.append(self._tool_definitions.get('yaml_generate'))

        if intent_val in ('Explore', 'Gather'):
            tools.append(self._tool_definitions.get('lesson_store'))
            tools.append(self._tool_definitions.get('lesson_search'))

        if intent_val == 'Converse':
            tools.append(self._tool_definitions.get('spec_read'))
            tools.append(self._tool_definitions.get('lesson_search'))

        tools.append(self._tool_definitions.get('python_execute'))

        return [t for t in tools if t is not None]

    def _build_tool_definitions(self) -> dict[str, dict]:
        return {
            'spec_read': {
                'name': 'spec_read',
                'description': 'Read a spec file or section from the _specs/ directory',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'spec_name': {'type': 'string', 'description': 'Name of the spec file (without .md)'},
                        'section': {'type': 'string', 'description': 'Optional heading to extract'},
                    },
                    'required': ['spec_name'],
                },
            },
            'config_read': {
                'name': 'config_read',
                'description': 'Read the current partially-filled assistant config',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'section': {'type': 'string', 'description': 'Optional section to read'},
                    },
                },
            },
            'config_write': {
                'name': 'config_write',
                'description': 'Update a section of the assistant config being built',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'section': {'type': 'string', 'description': 'Config section to update'},
                        'data': {'type': 'object', 'description': 'Key-value pairs to set'},
                        'merge': {'type': 'boolean', 'description': 'Merge with existing (default true)'},
                    },
                    'required': ['section', 'data'],
                },
            },
            'ontology_generate': {
                'name': 'ontology_generate',
                'description': 'Generate ontology.py from current config state',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'target_dir': {'type': 'string', 'description': 'Directory to write file'},
                        'dry_run': {'type': 'boolean', 'description': 'Preview without writing'},
                    },
                },
            },
            'yaml_generate': {
                'name': 'yaml_generate',
                'description': 'Compose domain YAML config from gathered requirements',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'target_dir': {'type': 'string', 'description': 'Directory to write file'},
                        'dry_run': {'type': 'boolean', 'description': 'Preview without writing'},
                    },
                },
            },
            'python_execute': {
                'name': 'python_execute',
                'description': 'Run Python code via exec() for ad hoc generation',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'code': {'type': 'string', 'description': 'Python code to execute'},
                        'timeout_ms': {'type': 'integer', 'description': 'Timeout in ms'},
                    },
                    'required': ['code'],
                },
            },
            'lesson_store': {
                'name': 'lesson_store',
                'description': 'Store a learning or pattern to the lessons database',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'content': {'type': 'string', 'description': 'The lesson content'},
                        'category': {'type': 'string', 'enum': ['architecture', 'flow_design', 'prompt_engineering', 'domain_modeling', 'general']},
                        'tags': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': ['content'],
                },
            },
            'lesson_search': {
                'name': 'lesson_search',
                'description': 'Search stored lessons by keyword, category, or tags',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'description': 'Search query'},
                        'category': {'type': 'string'},
                        'limit': {'type': 'integer', 'description': 'Max results'},
                    },
                    'required': ['query'],
                },
            },
        }

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

    # ── Post-hook ────────────────────────────────────────────────────

    def _verify(self):
        state = self.world.current_state()
        if state and state.pred_intent and state.keep_going and not self.world.flow_stack.get_pending_flows():
            state.keep_going = False
