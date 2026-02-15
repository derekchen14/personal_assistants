from __future__ import annotations

import json
from types import MappingProxyType
from pathlib import Path

from backend.components.dialogue_state import DialogueState
from backend.components.flow_stack import FlowStack
from backend.components.context_coordinator import ContextCoordinator
from backend.components.prompt_engineer import PromptEngineer
from backend.components.memory_manager import MemoryManager
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.utilities.services import (
    SpecService, ConfigService, GeneratorService, CodeService, LessonService,
)
from backend.modules.nlu import NLUResult
from backend.modules.policies import (
    ExplorePolicy, ProvidePolicy, DesignPolicy, DeliverPolicy,
    ConversePolicy, PlanPolicy, InternalPolicy,
)
from schemas.ontology import FLOW_CATALOG, Intent


class PEXResult:

    def __init__(self, message: str, block_type: str = 'default',
                 block_data: dict | None = None, actions: list | None = None,
                 tool_log: list | None = None):
        self.message = message
        self.block_type = block_type
        self.block_data = block_data or {}
        self.actions = actions or []
        self.tool_log = tool_log or []

    def __repr__(self):
        return f'<PEXResult block={self.block_type} actions={len(self.actions)}>'


class PEX:

    _CANNED: dict[str, str] = {
        'chat': "Hey! What assistant are we building?",
        'next_step': "What should we work on next?",
        'status': "Let me check where we are.",
    }

    _UNSUPPORTED = {
        'style', 'dismiss', 'recommend', 'compare',
        'log', 'remove', 'validate', 'report', 'package',
        'finalize', 'redesign',
        'recap', 'remember', 'recall', 'auto_validate', 'auto_generate',
    }

    def __init__(self, config: MappingProxyType, dialogue_state: DialogueState,
                 flow_stack: FlowStack, context: ContextCoordinator,
                 prompt_engineer: PromptEngineer, memory: MemoryManager,
                 display: DisplayFrame, ambiguity: AmbiguityHandler):
        self.config = config
        self.dialogue_state = dialogue_state
        self.flow_stack = flow_stack
        self.context = context
        self.prompt_engineer = prompt_engineer
        self.memory = memory
        self.display = display
        self.ambiguity = ambiguity

        self._spec_service = SpecService()
        self._config_service = ConfigService()
        self._generator_service = GeneratorService(self._config_service)
        self._code_service = CodeService()
        self._lesson_service = LessonService()

        self._tool_definitions = self._build_tool_definitions()

        components = {
            'prompt_engineer': prompt_engineer,
            'context': context,
            'memory': memory,
            'display': display,
            'dialogue_state': dialogue_state,
            'flow_stack': flow_stack,
            'get_tools': self.get_tools_for_flow,
        }
        self._policies: dict[str, object] = {
            Intent.EXPLORE.value: ExplorePolicy(components),
            Intent.PROVIDE.value: ProvidePolicy(components),
            Intent.DESIGN.value: DesignPolicy(components),
            Intent.DELIVER.value: DeliverPolicy(components),
            Intent.CONVERSE.value: ConversePolicy(components),
            Intent.PLAN.value: PlanPolicy(components),
            Intent.INTERNAL.value: InternalPolicy(components),
        }

    def execute(self, nlu_result: NLUResult) -> tuple[PEXResult, bool]:
        flow_name = nlu_result.flow_name
        flow_info = FLOW_CATALOG.get(flow_name)
        if not flow_info:
            return PEXResult(
                message="I'm not sure how to handle that. Could you rephrase?",
                block_type='default',
            ), False

        check_result = self._check(nlu_result, flow_info)
        if check_result:
            return check_result, False

        existing = self.flow_stack.find_by_name(flow_name)
        if existing:
            flow_entry = existing
        else:
            flow_entry = self.flow_stack.push(
                flow_name, nlu_result.dax, nlu_result.intent,
                slots=nlu_result.slots,
            )

        if flow_name in self._CANNED:
            result = PEXResult(
                message=self._CANNED[flow_name], block_type='default',
            )
        elif flow_name in self._UNSUPPORTED:
            result = PEXResult(
                message=(
                    "That feature isn't supported yet, but it's on the roadmap. "
                    "Is there something else I can help with?"
                ),
                block_type='default',
            )
        else:
            intent_val = nlu_result.intent
            if hasattr(intent_val, 'value'):
                intent_val = intent_val.value
            policy = self._policies.get(intent_val)
            if policy:
                result = policy.execute(
                    flow_name, flow_info, nlu_result, self._dispatch_tool,
                )
            else:
                result = PEXResult(
                    message="I'm not sure how to handle that. Could you rephrase?",
                    block_type='default',
                )

        self.flow_stack.mark_complete(result={'message': result.message})

        if result.message:
            self.memory.write_scratchpad(
                f'flow:{flow_name}',
                f'{flow_name}: {result.message[:200]}',
            )

        self._verify()

        keep_going = self.dialogue_state.keep_going
        return result, keep_going

    # ── Pre-hook ─────────────────────────────────────────────────────

    def _check(self, nlu_result: NLUResult, flow_info: dict) -> PEXResult | None:
        if nlu_result.flow_name in self._CANNED:
            return None
        if nlu_result.flow_name in self._UNSUPPORTED:
            return None

        required_missing = []
        for slot_name, slot_info in flow_info.get('slots', {}).items():
            if slot_info.get('priority') == 'required':
                if slot_name not in nlu_result.slots or not nlu_result.slots[slot_name]:
                    required_missing.append(slot_name)

        if required_missing:
            for slot_name in list(required_missing):
                filled = self._fill_from_context(slot_name, flow_info)
                if filled:
                    nlu_result.slots[slot_name] = filled
                    required_missing.remove(slot_name)

        if required_missing:
            self.ambiguity.declare(
                'specific',
                metadata={'missing_slots': required_missing},
                observation=f'I need the following to proceed: {", ".join(required_missing)}',
            )
            return PEXResult(
                message=self.ambiguity.ask(),
                block_type='default',
            )
        return None

    def _fill_from_context(self, slot_name: str, flow_info: dict) -> str | None:
        scratchpad_val = self.memory.read_scratchpad(slot_name)
        if scratchpad_val:
            return scratchpad_val

        recent = self.context.compile_history(turns=3)
        for turn in reversed(recent):
            if turn['speaker'] == 'User' and slot_name.lower() in turn['text'].lower():
                return turn['text']
        return None

    # ── Tool dispatch ────────────────────────────────────────────────

    def _dispatch_tool(self, tool_name: str, tool_input: dict) -> dict:
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
            turns = params.get('turns', 3)
            history = self.context.compile_history(turns=turns)
            return {'status': 'success', 'result': history}
        elif action == 'get_turn':
            turn_id = params.get('turn_id', '')
            turn = self.context.get_turn(turn_id)
            return {'status': 'success', 'result': turn}
        elif action == 'get_checkpoint':
            label = params.get('label', '')
            cp = self.context.get_checkpoint(label)
            return {'status': 'success', 'result': cp}
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    def _dispatch_flow_stack_tool(self, params: dict) -> dict:
        action = params.get('action', '')
        if action == 'get_slots':
            active = self.flow_stack.get_active_flow()
            if active:
                return {'status': 'success', 'result': active.slots}
            return {'status': 'success', 'result': {}}
        elif action == 'get_flow_meta':
            active = self.flow_stack.get_active_flow()
            if active:
                return {'status': 'success', 'result': active.to_dict()}
            return {'status': 'success', 'result': None}
        elif action == 'get_stack':
            return {'status': 'success', 'result': self.flow_stack.to_list()}
        return {'status': 'error', 'message': f'Unknown action: {action}'}

    # ── Tool definitions ─────────────────────────────────────────────

    def get_tools_for_flow(self, flow_name: str, flow_info: dict) -> list[dict]:
        tools = []
        intent = flow_info.get('intent', Intent.CONVERSE)
        intent_val = intent.value if hasattr(intent, 'value') else str(intent)

        tools.extend(self._component_tool_definitions())

        if intent_val in ('Explore', 'Provide', 'Design', 'Deliver'):
            tools.append(self._tool_definitions.get('spec_read'))
            tools.append(self._tool_definitions.get('config_read'))

        if intent_val in ('Provide', 'Design'):
            tools.append(self._tool_definitions.get('config_write'))

        if intent_val == 'Deliver':
            tools.append(self._tool_definitions.get('ontology_generate'))
            tools.append(self._tool_definitions.get('yaml_generate'))

        if intent_val in ('Explore', 'Provide'):
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
        active = self.flow_stack.get_active_flow()
        if self.dialogue_state.keep_going and not self.flow_stack.get_pending_flows():
            self.dialogue_state.keep_going = False
