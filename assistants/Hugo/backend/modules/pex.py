from __future__ import annotations

import json
from types import MappingProxyType
from typing import TYPE_CHECKING

from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.prompt_engineer import PromptEngineer
from backend.components.memory_manager import MemoryManager

from backend.utilities.services import PostService, ContentService, AnalysisService, PlatformService
from backend.modules.policies import *
from schemas.ontology import Intent

if TYPE_CHECKING:
    from backend.components.context_coordinator import ContextCoordinator
    from backend.components.world import World

class PEX:

    def __init__(self, config:MappingProxyType, ambiguity:AmbiguityHandler,
                 engineer:PromptEngineer, memory:MemoryManager, world:'World'):
        self.config = config
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.memory = memory
        self.world = world
        self.flow_stack = world.flow_stack

        self._post_service = PostService()
        self._content_service = ContentService()
        self._analysis_service = AnalysisService()
        self._platform_service = PlatformService()

        self._tools: dict[str, tuple[object, str]] = {
            # PostService (9)
            'find_posts':        (self._post_service, 'find_posts'),
            'search_notes':      (self._post_service, 'search_notes'),
            'read_metadata':     (self._post_service, 'read_metadata'),
            'read_section':      (self._post_service, 'read_section'),
            'create_post':       (self._post_service, 'create_post'),
            'update_post':       (self._post_service, 'update_post'),
            'delete_post':       (self._post_service, 'delete_post'),
            'summarize_text':    (self._post_service, 'summarize_text'),
            'rollback_post':     (self._post_service, 'rollback_post'),
            # ContentService (12)
            'generate_outline':  (self._content_service, 'generate_outline'),
            'convert_to_prose':  (self._content_service, 'convert_to_prose'),
            'insert_section':    (self._content_service, 'insert_section'),
            'insert_content':    (self._content_service, 'insert_content'),
            'revise_content':    (self._content_service, 'revise_content'),
            'write_text':        (self._content_service, 'write_text'),
            'find_and_replace':  (self._content_service, 'find_and_replace'),
            'remove_content':    (self._content_service, 'remove_content'),
            'cut_and_paste':     (self._content_service, 'cut_and_paste'),
            'diff_section':      (self._content_service, 'diff_section'),
            'insert_media':      (self._content_service, 'insert_media'),
            'web_search':        (self._content_service, 'web_search'),
            # AnalysisService (8)
            'brainstorm_ideas':  (self._analysis_service, 'brainstorm_ideas'),
            'inspect_post':      (self._analysis_service, 'inspect_post'),
            'check_readability': (self._analysis_service, 'check_readability'),
            'check_links':       (self._analysis_service, 'check_links'),
            'compare_style':     (self._analysis_service, 'compare_style'),
            'editor_review':     (self._analysis_service, 'editor_review'),
            'explain_action':    (self._analysis_service, 'explain_action'),
            'analyze_seo':       (self._analysis_service, 'analyze_seo'),
            # PlatformService (5)
            'release_post':      (self._platform_service, 'release_post'),
            'promote_post':      (self._platform_service, 'promote_post'),
            'cancel_release':    (self._platform_service, 'cancel_release'),
            'list_channels':     (self._platform_service, 'list_channels'),
            'channel_status':    (self._platform_service, 'channel_status'),
        }

        components = {'engineer': engineer, 'memory': memory, 'config': config, 'ambiguity': ambiguity,
            'get_tools': self.get_tools_for_flow, 'flow_stack': self.flow_stack
        }
        self._policies: dict[str, object] = {
            Intent.CONVERSE: ConversePolicy(components),
            Intent.RESEARCH: ResearchPolicy(components),
            Intent.DRAFT: DraftPolicy(components),
            Intent.REVISE: RevisePolicy(components),
            Intent.PUBLISH: PublishPolicy(components),
            Intent.PLAN: PlanPolicy(components),
            Intent.INTERNAL: InternalPolicy(components),
        }

    def execute(self, state:DialogueState, context:'ContextCoordinator') -> tuple[DisplayFrame, bool]:
        active_flow = self.flow_stack.get_active_flow()
        if not active_flow:
            frame = DisplayFrame(self.config)
            return frame, False

        check_result = self._security_check(active_flow)
        if check_result:
            return check_result, False

        policy = self._policies.get(active_flow.intent)
        frame = policy.execute(state, context, self._dispatch_tool)

        self.world.insert_frame(frame)
        keep_going = self._verify(active_flow)
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
        """Update dialogue state's active_post from the flow's entity slot."""
        ent_slot = flow.slots.get(flow.entity_slot)
        if ent_slot and ent_slot.filled:
            state = self.world.current_state()
            if state:
                state.active_post = ent_slot.values[0]['post']

    # -- Tool dispatch ----------------------------------------------------

    def _dispatch_tool(self, tool_name:str, tool_input:dict) -> dict:
        self.world.context.add_turn(
            'Agent', f'[tool:{tool_name}] {json.dumps(tool_input)[:200]}',
            turn_type='action',
        )
        try:
            if tool_name in self._tools:
                service, method_name = self._tools[tool_name]
                method = getattr(service, method_name)
                return method(**tool_input)
            elif tool_name == 'handle_ambiguity':
                return self._dispatch_ambiguity_tool(tool_input)
            elif tool_name == 'coordinate_context':
                return self._dispatch_context_tool(tool_input)
            elif tool_name == 'manage_memory':
                return self.memory.dispatch_tool(
                    tool_input.get('action', ''),
                    tool_input,
                )
            elif tool_name == 'read_flow_stack':
                return self._dispatch_flow_stack_tool(tool_input)
            else:
                return {
                    '_success': False, '_error': 'invalid_input',
                    '_message': f'Unknown tool: {tool_name}',
                }
        except Exception as ecp:
            return {
                '_success': False, '_error': 'server_error',
                '_message': f'{type(ecp).__name__}: {ecp}',
            }

    def _dispatch_context_tool(self, params:dict) -> dict:
        action = params.get('action', '')
        if action == 'get_history':
            turns = params.get('turns', 3)
            history = self.world.context.compile_history(look_back=turns)
            return {'_success': True, 'history': history}
        elif action == 'get_turn':
            turn_id = params.get('turn_id', 0)
            turn = self.world.context.get_turn(int(turn_id))
            return {'_success': True, 'turn': turn.utt(as_dict=True) if turn else None}
        elif action == 'get_checkpoint':
            label = params.get('label', '')
            cp = self.world.context.get_checkpoint(label)
            return {'_success': True, 'checkpoint': cp}
        return {'_success': False, '_error': 'invalid_input', '_message': f'Unknown action: {action}'}

    def _dispatch_flow_stack_tool(self, params:dict) -> dict:
        action = params.get('action', '')
        if action == 'get_slots':
            flow = self.flow_stack.get_active_flow()
            if flow:
                return {'_success': True, 'slots': flow.slot_values_dict()}
            return {'_success': True, 'slots': {}}
        elif action == 'get_flow_meta':
            flow = self.flow_stack.get_active_flow()
            if flow:
                return {'_success': True, 'flow': flow.to_dict()}
            return {'_success': True, 'flow': None}
        elif action == 'get_stack':
            return {'_success': True, 'stack': self.flow_stack.to_list()}
        return {'_success': False, '_error': 'invalid_input', '_message': f'Unknown action: {action}'}

    def _dispatch_ambiguity_tool(self, params:dict) -> dict:
        action = params.get('action', '')
        if action == 'declare':
            self.ambiguity.declare(
                params.get('type', ''),
                metadata=params.get('metadata'),
            )
            return {'_success': True}
        elif action == 'ask':
            return {'_success': True, 'prompt': self.ambiguity.ask()}
        elif action == 'resolve':
            self.ambiguity.resolve(params.get('metadata', {}))
            return {'_success': True}
        return {'_success': False, '_error': 'invalid_input', '_message': f'Unknown action: {action}'}

    # -- Tool definitions -------------------------------------------------

    @staticmethod
    def _thaw(obj):
        if isinstance(obj, MappingProxyType):
            return {key: PEX._thaw(val) for key, val in obj.items()}
        if isinstance(obj, tuple):
            return [PEX._thaw(item) for item in obj]
        return obj

    def _get_tool_def(self, tool_id:str) -> dict | None:
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
                'name': 'handle_ambiguity',
                'description': 'Manage ambiguity lifecycle. Actions: declare, ask, resolve',
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['declare', 'ask', 'resolve']},
                        'type': {'type': 'string'},
                        'metadata': {'type': 'object'},
                    },
                    'required': ['action'],
                },
            },
            {
                'name': 'coordinate_context',
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
                'name': 'manage_memory',
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
                'name': 'read_flow_stack',
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

    def _verify(self, active_flow):
        state = self.world.current_state()
        if state and state.keep_going and not self.flow_stack.get_pending_flows():
            state.keep_going = False

        if active_flow.intent in ['Research', 'Draft', 'Revise', 'Publish']:
            self._update_active_post(active_flow)
        
        return state.keep_going

