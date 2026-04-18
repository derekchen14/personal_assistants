from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from enum import Enum
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

log = logging.getLogger(__name__)


class RecoveryAction(Enum):
    RETRY = 'retry'
    GATHER_CONTEXT = 'gather'    # future
    REROUTE = 'reroute'          # future
    ESCALATE = 'escalate'


@dataclass
class FrameCheck:
    passed: bool
    reason: str = ''

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
        active_flow = self.flow_stack.get_flow()

        check_result = self._security_check(active_flow)
        if check_result:
            return check_result, False

        policy = self._policies[active_flow.intent]
        frame = policy.execute(state, context, self._dispatch_tool)

        check = self._validate_frame(frame, active_flow)
        if not check.passed:
            frame, action = self.recover(check, active_flow, context)
            if action == RecoveryAction.ESCALATE:
                state.has_issues = True
                self.world.insert_frame(frame)
                self._verify(active_flow)
                return frame, False

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
                frame.add_block({'type': 'confirmation', 'data': {
                    'prompt': self.ambiguity.ask(),
                    'confirm_label': 'Approve',
                    'cancel_label': 'Cancel',
                }})
                return frame

        return None

    def _verify_active_post(self, flow):
        """Read-only check: if the flow is grounded on a post/section/channel,
        state.active_post must be set by the policy. Topic-grounded flows skip this."""
        state = self.world.current_state()
        ent_slot = flow.slots[flow.entity_slot]
        if ent_slot.slot_type in ['source', 'target', 'removal', 'channel'] and not state.active_post:
            state.has_issues = True

    # -- Validation -------------------------------------------------------

    def _validate_frame(self, frame:DisplayFrame, flow) -> FrameCheck:
        """Check whether a frame is good enough to show to the user."""
        if self.ambiguity.present():
            return FrameCheck(passed=True)
        block_data, block_types = self._merge_block_data(frame)

        has_data = (
            'default' in block_types
            or block_data
            or frame.thoughts
            or frame.metadata
        )
        if not has_data:
            return FrameCheck(passed=False, reason='Frame has no data')
        if 'error' in block_data and block_data.get('status') == 'error':
            return FrameCheck(passed=False, reason=f'Tool error: {block_data["error"]}')
        last_user = self.world.context.last_user_text
        thoughts = frame.thoughts
        if last_user and thoughts.strip() == last_user.strip():
            return FrameCheck(passed=False, reason='Response echoes user input verbatim')
        if self._should_llm_validate(flow):
            card_content = block_data.get('content', '')
            slot_text = self._collect_slot_evidence(flow)
            visible = '\n'.join(part for part in (thoughts, card_content, slot_text) if part)
            return self._llm_quality_check(visible)
        return FrameCheck(passed=True)

    @staticmethod
    def _merge_block_data(frame:DisplayFrame) -> dict:
        merged = {}
        block_types = []
        for block in frame.blocks:
            merged.update(block.data)
            block_types.append(block.block_type)
        return merged, block_types

    @staticmethod
    def _collect_slot_evidence(flow) -> str:
        """Aggregate slot data that represents user-visible work (proposals, etc)."""
        slot = flow.slots.get('proposals')
        if not slot or not slot.options:
            return ''
        parts = []
        for idx, option in enumerate(slot.options, start=1):
            if isinstance(option, list):
                sec_lines = [f"## {sec['name']}\n{sec.get('description', '')}"
                             for sec in option]
                parts.append(f"### Option {idx}\n" + '\n'.join(sec_lines))
            else:
                parts.append(f"### Option {idx}\n{option}")
        return '\n\n'.join(parts)

    def _should_llm_validate(self, flow) -> bool:
        flows = self.config.get('recovery', {}).get('llm_validate_flows', [])
        return flow.name() in flows

    def _llm_quality_check(self, content:str) -> FrameCheck:
        last_user = self.world.context.last_user_text
        if not last_user:
            return FrameCheck(passed=True)
        convo = self.world.context.compile_history(look_back=4)
        prompt = (
            f'Recent conversation:\n{convo}\n\n'
            f'User request: {last_user}\n\nAgent output:\n{content}'
        )
        try:
            raw_output = self.engineer(prompt, 'quality_check', model='haiku', max_tokens=128)
            verdict = raw_output.strip().lower()
            if verdict.startswith('pass'):
                return FrameCheck(passed=True)
            reason = verdict.removeprefix('fail:').strip() or 'LLM quality check failed'
            return FrameCheck(passed=False, reason=reason)
        except Exception:
            return FrameCheck(passed=True)

    # -- Recovery ---------------------------------------------------------

    def recover(self, check:FrameCheck, flow,
                context:'ContextCoordinator') -> tuple[DisplayFrame, RecoveryAction]:
        """Attempt to recover from a failed frame validation.

        Tries strategies in escalating order. Returns the best frame
        achievable and an action for the Agent.
        """
        log.warning('recover: %s (flow=%s)', check.reason, flow.name())

        # ── Tier 1: Retry skill with error feedback ─────────────────
        repair_msg = (
            f'[Recovery] Your previous output was rejected: {check.reason}. '
            f'Please try again, addressing this issue.'
        )
        self.memory.write_scratchpad('repair', check.reason)
        context.add_turn('System', repair_msg, turn_type='system')

        policy = self._policies[flow.intent]
        retry_frame = policy.execute(
            self.world.current_state(), context, self._dispatch_tool,
        )
        retry_check = self._validate_frame(retry_frame, flow)
        if retry_check.passed:
            log.info('recover: tier-1 retry succeeded')
            return retry_frame, RecoveryAction.RETRY
        log.warning('recover: tier-1 failed: %s', retry_check.reason)

        # ── Tier 2: Gather more context from BusinessContext ─────────
        #
        # Retrieve relevant business context from MemoryManager to enrich
        # the retry. Push Internal/retrieve flow onto stack, execute it
        # to populate scratchpad, then retry original policy.
        #
        # self.memory.write_scratchpad('recovery_query', check.reason)
        # retrieve_flow = self.flow_stack.stackon('retrieve')
        # internal = self._policies.get(Intent.INTERNAL)
        # if internal:
        #     internal.execute(self.world.current_state(), context, self._dispatch_tool)
        # retrieve_flow.status = 'Completed'
        # retry_frame = policy.execute(self.world.current_state(), context, self._dispatch_tool)
        # retry_check = self._validate_frame(retry_frame, flow)
        # if retry_check.passed:
        #     return retry_frame, RecoveryAction.GATHER_CONTEXT

        # ── Tier 3: Re-route via NLU contemplate() ──────────────────
        #
        # Record failure in scratchpad, set ambiguity observation so
        # contemplate() sees why the flow failed, then signal Agent
        # to call nlu.contemplate() for a fallback flow.
        #
        # self.memory.write_scratchpad('reroute_reason', check.reason)
        # self.ambiguity.declare(
        #     'reroute',
        #     metadata={'flow': flow.name(), 'failure_reason': check.reason},
        #     observation=f'Flow {flow.name()} failed: {check.reason}',
        # )
        # frame = DisplayFrame(self.config)
        # return frame, RecoveryAction.REROUTE

        # ── Tier 4: Escalate to user ────────────────────────────────
        log.info('recover: escalating to user')
        self.ambiguity.declare(
            'partial',
            metadata={'flow': flow.name(), 'failure_reason': check.reason},
            observation=(
                f'I had trouble completing this — {check.reason}. '
                f'Could you provide more details or try a different approach?'
            ),
        )
        frame = DisplayFrame(self.config)
        return frame, RecoveryAction.ESCALATE

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
            return {'_success': True, 'slots': self.flow_stack.get_flow().slot_values_dict()}
        elif action == 'get_flow_meta':
            return {'_success': True, 'flow': self.flow_stack.get_flow().to_dict()}
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
        if active_flow.intent not in ['Converse', 'Internal'] and not state.has_issues:
            self._verify_active_post(active_flow)
        return state.keep_going

