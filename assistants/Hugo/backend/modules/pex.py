from __future__ import annotations

import json
from types import MappingProxyType

from backend.components.dialogue_state import DialogueState
from backend.components.flow_stack import FlowStack
from backend.components.context_coordinator import ContextCoordinator
from backend.components.prompt_engineer import PromptEngineer
from backend.components.memory_manager import MemoryManager
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.utilities.services import PostService, ContentService, PlatformService
from backend.modules.nlu import NLUResult
from backend.modules.policies import (
    ConversePolicy, ResearchPolicy, DraftPolicy, RevisePolicy,
    PublishPolicy, PlanPolicy, InternalPolicy,
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
        'chat': "Hey! What are we writing today?",
        'next': "What would you like to work on next?",
        'check': "You don't have any drafts yet. Want to start one?",
    }

    _UNSUPPORTED = {
        'tidy', 'suggest',
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

        self._post_service = PostService()
        self._content_service = ContentService()
        self._platform_service = PlatformService()

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
            Intent.CONVERSE.value: ConversePolicy(components),
            Intent.RESEARCH.value: ResearchPolicy(components),
            Intent.DRAFT.value: DraftPolicy(components),
            Intent.REVISE.value: RevisePolicy(components),
            Intent.PUBLISH.value: PublishPolicy(components),
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
            if tool_name == 'post_search':
                return self._post_service.search(
                    tool_input.get('query', ''),
                    tool_input.get('status'),
                    tool_input.get('category'),
                    tool_input.get('limit', 20),
                )
            elif tool_name == 'post_get':
                return self._post_service.get(tool_input.get('post_id', ''))
            elif tool_name == 'post_create':
                return self._post_service.create(
                    tool_input.get('title', 'Untitled'),
                    tool_input.get('topic'),
                    tool_input.get('category'),
                )
            elif tool_name == 'post_update':
                return self._post_service.update(
                    tool_input.get('post_id', ''),
                    tool_input.get('updates', {}),
                )
            elif tool_name == 'content_generate':
                return self._content_service.generate(
                    tool_input.get('content_type', 'prose'),
                    tool_input.get('topic'),
                    tool_input.get('source_text'),
                    tool_input.get('instructions'),
                )
            elif tool_name == 'content_format':
                return self._content_service.format(
                    tool_input.get('content', ''),
                    tool_input.get('platform', 'blog'),
                    tool_input.get('format_type', 'blog'),
                )
            elif tool_name == 'platform_publish':
                return self._platform_service.publish(
                    tool_input.get('post_id', ''),
                    tool_input.get('platform', 'blog'),
                    tool_input.get('action', 'publish'),
                    tool_input.get('scheduled_at'),
                )
            elif tool_name == 'platform_list':
                return self._platform_service.list_platforms()
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

        if intent_val in ('Research', 'Draft', 'Revise', 'Publish'):
            tools.append(self._tool_definitions.get('post_search'))
            tools.append(self._tool_definitions.get('post_get'))

        if intent_val in ('Draft',):
            tools.append(self._tool_definitions.get('post_create'))
            tools.append(self._tool_definitions.get('post_update'))
            tools.append(self._tool_definitions.get('content_generate'))

        if intent_val in ('Revise',):
            tools.append(self._tool_definitions.get('post_update'))
            tools.append(self._tool_definitions.get('content_generate'))
            tools.append(self._tool_definitions.get('content_format'))

        if intent_val in ('Publish',):
            tools.append(self._tool_definitions.get('platform_publish'))
            tools.append(self._tool_definitions.get('platform_list'))
            tools.append(self._tool_definitions.get('content_format'))

        if intent_val in ('Converse',):
            tools.append(self._tool_definitions.get('post_search'))

        if intent_val in ('Plan',):
            tools.append(self._tool_definitions.get('post_search'))
            tools.append(self._tool_definitions.get('post_get'))

        return [t for t in tools if t is not None]

    def _build_tool_definitions(self) -> dict[str, dict]:
        return {
            'post_search': {
                'name': 'post_search',
                'description': 'Search posts, drafts, and topics by keyword, status, or category',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'description': 'Search keyword'},
                        'status': {'type': 'string', 'enum': ['draft', 'published', 'archived']},
                        'category': {'type': 'string'},
                        'limit': {'type': 'integer', 'description': 'Max results'},
                    },
                },
            },
            'post_get': {
                'name': 'post_get',
                'description': 'Get a specific post or draft by ID',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'post_id': {'type': 'string', 'description': 'The post ID'},
                    },
                    'required': ['post_id'],
                },
            },
            'post_create': {
                'name': 'post_create',
                'description': 'Create a new draft post',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string', 'description': 'Post title'},
                        'topic': {'type': 'string', 'description': 'Post topic'},
                        'category': {'type': 'string'},
                    },
                    'required': ['title'],
                },
            },
            'post_update': {
                'name': 'post_update',
                'description': "Update a draft's content, outline, status, or metadata",
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'post_id': {'type': 'string'},
                        'updates': {
                            'type': 'object',
                            'description': 'Key-value pairs to update',
                        },
                    },
                    'required': ['post_id', 'updates'],
                },
            },
            'content_generate': {
                'name': 'content_generate',
                'description': 'Generate content: outlines, prose, revisions, brainstorming',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'content_type': {
                            'type': 'string',
                            'enum': ['outline', 'prose', 'revision', 'brainstorm', 'summary'],
                        },
                        'topic': {'type': 'string'},
                        'source_text': {'type': 'string'},
                        'instructions': {'type': 'string'},
                    },
                    'required': ['content_type'],
                },
            },
            'content_format': {
                'name': 'content_format',
                'description': (
                    'Format content for a specific platform. '
                    'Substack: HTML, Twitter: 280-char thread, LinkedIn: 3000-char text, MT1T: markdown/HTML'
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'content': {'type': 'string'},
                        'platform': {
                            'type': 'string',
                            'enum': ['substack', 'twitter', 'linkedin', 'mt1t'],
                        },
                        'format_type': {'type': 'string', 'enum': ['blog', 'social', 'newsletter']},
                    },
                    'required': ['content', 'platform'],
                },
            },
            'platform_publish': {
                'name': 'platform_publish',
                'description': (
                    'Publish, schedule, or unpublish a post on a platform. '
                    'Platforms: substack (newsletter), twitter (social/threads), '
                    'linkedin (social), mt1t (More Than One Turn blog)'
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'post_id': {'type': 'string'},
                        'platform': {
                            'type': 'string',
                            'enum': ['substack', 'twitter', 'linkedin', 'mt1t'],
                        },
                        'action': {'type': 'string', 'enum': ['publish', 'schedule', 'unpublish']},
                        'scheduled_at': {'type': 'string', 'description': 'ISO datetime for scheduling'},
                    },
                    'required': ['post_id', 'platform'],
                },
            },
            'platform_list': {
                'name': 'platform_list',
                'description': (
                    'List publishing platforms and connection status. '
                    'Configured: Substack, Twitter/X, LinkedIn, More Than One Turn'
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {},
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
