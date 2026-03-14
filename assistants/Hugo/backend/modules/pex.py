from __future__ import annotations

import json
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from backend.components.memory_manager import MemoryManager
from backend.utilities.services import PostService, ContentService, PlatformService as ChannelService
from backend.modules.policies import (
    ConversePolicy, ResearchPolicy, DraftPolicy, RevisePolicy,
    PublishPolicy, PlanPolicy, InternalPolicy,
)
from schemas.ontology import Intent

if TYPE_CHECKING:
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.world import World
_UNSUPPORTED: set[str] = set()
_POST_INTENTS = {Intent.RESEARCH, Intent.DRAFT, Intent.REVISE, Intent.PUBLISH}


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

        self._post_service = PostService()
        self._content_service = ContentService()
        self._channel_service = ChannelService()

        self._tools: dict[str, tuple[object, str]] = {
            'post_search':       (self._post_service, 'search'),
            'post_get':          (self._post_service, 'get'),
            'post_create':       (self._post_service, 'create'),
            'post_update':       (self._post_service, 'update'),
            'post_delete':       (self._post_service, 'delete'),
            'content_generate':  (self._content_service, 'generate'),
            'content_format':    (self._content_service, 'format'),
            'channel_publish':   (self._channel_service, 'publish'),
            'channel_list':      (self._channel_service, 'list_platforms'),
            'channel_status':    (self._channel_service, 'get_status'),
        }

        components = {
            'engineer': engineer,
            'memory': memory,
            'config': config,
            'ambiguity': ambiguity,
            'get_tools': self.get_tools_for_flow,
        }
        plan_components = {**components, 'flow_stack': self.flow_stack}
        self._policies: dict[str, object] = {
            Intent.CONVERSE: ConversePolicy(components),
            Intent.RESEARCH: ResearchPolicy(components),
            Intent.DRAFT: DraftPolicy(components),
            Intent.REVISE: RevisePolicy(components),
            Intent.PUBLISH: PublishPolicy(components),
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

        check_result = self._security_check(active_flow)
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

        if active_flow.intent in _POST_INTENTS:
            self._update_active_post(active_flow)

        self._verify()

        keep_going = state.keep_going
        return frame, keep_going

    # -- Pre-hook ---------------------------------------------------------

    def _security_check(self, flow) -> DisplayFrame | None:
        """Check for lethal trifecta tool capability violations."""
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

    def _update_active_post(self, flow):
        """Update dialogue state's active_post from the flow's source slot."""
        source_slot = flow.slots.get('source')
        if source_slot and source_slot.filled:
            val = source_slot.to_dict()
            post = val[0].get('post', '') if isinstance(val, list) and val else str(val)
            if post:
                state = self.world.current_state()
                if state:
                    state.active_post = post

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
            turn_id = params.get('turn_id', 0)
            turn = self.world.context.get_turn(int(turn_id))
            return {'status': 'success', 'result': turn.utt(as_dict=True) if turn else None}
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
                        'turn_id': {'type': 'integer'},
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
