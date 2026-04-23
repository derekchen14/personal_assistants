from __future__ import annotations

import json
import logging
from dataclasses import dataclass
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


@dataclass
class FrameCheck:
    passed: bool
    reason: str = ''
    is_error_frame: bool = False  # Policy classified this as an error frame

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

        self.tools: dict[str, tuple[object, str]] = {
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
            # ContentService (11)
            'generate_outline':  (self._content_service, 'generate_outline'),
            'generate_section':  (self._content_service, 'generate_section'),
            'convert_to_prose':  (self._content_service, 'convert_to_prose'),
            'insert_section':    (self._content_service, 'insert_section'),
            'revise_content':    (self._content_service, 'revise_content'),
            'write_text':        (self._content_service, 'write_text'),
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

        # Phase-2 logging: post-policy frame snapshot, before RES.
        log.info(
            f'PEX-POST-POLICY: flow={active_flow.name()!r} '
            f'origin={frame.origin!r} '
            f'metadata_keys={sorted(frame.metadata.keys())} '
            f'block_types={[b.block_type for b in frame.blocks]} '
            f'thoughts_len={len(frame.thoughts or "")}'
        )

        check = self._validate_frame(frame, active_flow)
        if not check.passed:
            # Error frames are already classified by the policy — no
            # generic retry. Pass them straight to RES; the template keys
            # off metadata['violation'] and frame.thoughts.
            if check.is_error_frame:
                state.has_issues = True
                self.world.insert_frame(frame)
                self._verify(active_flow)
                return frame, False
            frame, escalated = self.recover(check, active_flow, context)
            if escalated:
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
                frame = DisplayFrame(flow.name())
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
        """Check whether a frame is good enough to show to the user. A frame with a 'violation' set
        is already recognized as an error frame, so it does NOT need Tier-1 retry.
        return passed=False + is_error_frame=True so the outer caller routes it directly to RES.
        """
        if self.ambiguity.present():
            return FrameCheck(passed=True)
        if 'violation' in frame.metadata:
            violation = frame.metadata['violation']
            return FrameCheck(passed=False, reason=f'violation:{violation}', is_error_frame=True)
        block_data, block_types = self._merge_block_data(frame)

        has_data = ('default' in block_types or block_data or frame.thoughts or frame.metadata)
        if not has_data:
            return FrameCheck(passed=False, reason='Frame has no data')
        last_user = self.world.context.last_user_text
        thoughts = frame.thoughts
        if last_user and thoughts.strip() == last_user.strip():
            return FrameCheck(passed=False, reason='Response echoes user input verbatim')
        if flow.name() in self.config['content_validation']:
            card_content = block_data.get('content', '')
            slot_text = "collected_slot_evidence(flow)"
            visible = '\n'.join(part for part in (thoughts, card_content, slot_text) if part)
            # return self._llm_quality_check(visible)
        return FrameCheck(passed=True)

    @staticmethod
    def _merge_block_data(frame:DisplayFrame) -> dict:
        merged = {}
        block_types = []
        for block in frame.blocks:
            merged.update(block.data)
            block_types.append(block.block_type)
        return merged, block_types

    def _llm_quality_check(self, content:str) -> FrameCheck:
        last_user = self.world.context.last_user_text
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
                context:'ContextCoordinator') -> tuple[DisplayFrame, bool]:
        """Attempt to recover from a failed frame validation.

        Returns (frame, escalated). escalated=True means the caller
        should flip state.has_issues and surface the ambiguity to the
        user; False means the retry succeeded.

        Only runs when `check.is_error_frame` is False — error frames
        bypass this path and go straight to RES.

        Tier 2 (retrieve-based context gather) and Tier 3 (NLU
        re-route) are intentionally not live: reviving them requires a
        concrete driving failure mode plus dedicated tests. Escalation
        is the terminal fallback.
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
            return retry_frame, False
        log.warning('recover: tier-1 failed: %s', retry_check.reason)

        # ── Tier 4: Escalate to user (ambiguity) ────────────────────
        log.info('recover: escalating to user')
        observation = (
            f'I had trouble completing this — {check.reason}. '
            f'Could you provide more details or try a different approach?'
        )
        self.ambiguity.declare('partial', observation=observation)
        frame = DisplayFrame(flow.name())
        return frame, True

    # -- Tool dispatch ----------------------------------------------------

    def _dispatch_tool(self, tool_name:str, tool_input:dict) -> dict:
        self.world.context.add_turn(
            'Agent', f'[tool:{tool_name}] {json.dumps(tool_input)[:200]}',
            turn_type='action',
        )
        try:
            if tool_name in self.tools:
                service, method_name = self.tools[tool_name]
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
            elif tool_name == 'call_flow_stack':
                return self._dispatch_flow_stack_tool(tool_input)
            elif tool_name == 'save_findings':
                return self._dispatch_save_findings_tool(tool_input)
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
        details = params.get('details')
        if action == 'read':
            if details == 'slots':
                return {'_success': True, 'slots': self.flow_stack.get_flow().slot_values_dict()}
            if details == 'flow_meta':
                return {'_success': True, 'flow': self.flow_stack.get_flow().to_dict()}
            if details == 'flows':
                return {'_success': True, 'flows': self.flow_stack.to_list()}
            return {'_success': False, '_error': 'invalid_input',
                    '_message': f"read details must be one of 'flows', 'slots', 'flow_meta'; got {details!r}"}
        if action == 'stackon':
            if not details:
                return {'_success': False, '_error': 'invalid_input',
                        '_message': 'stackon requires `details` naming the flow to push'}
            self.flow_stack.stackon(details)
            return {'_success': True, 'stacked': details}
        if action == 'fallback':
            if not details:
                return {'_success': False, '_error': 'invalid_input',
                        '_message': 'fallback requires `details` naming the flow to route to'}
            self.flow_stack.fallback(details)
            return {'_success': True, 'fell_back_to': details}
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

    def _dispatch_save_findings_tool(self, params:dict) -> dict:
        """Persist structured findings to the scratchpad under the active flow's name.

        Tool-call-shaped replacement for skills that would otherwise emit a
        JSON blob as their terminal text response. The policy reads the
        findings out of tool_log via `extract_tool_result`; downstream flows
        read them via `memory.read_scratchpad(<flow_name>)`.
        """
        findings = params.get('findings', [])
        summary = params.get('summary', '')
        references_used = params.get('references_used', [])
        flow = self.flow_stack.get_flow()
        key = flow.name() if flow else 'findings'
        self.memory.write_scratchpad(key, {
            'version': '1',
            'turn_number': self.world.context.turn_id,
            'used_count': 0,
            'summary': summary,
            'findings': findings,
            'references_used': references_used,
        })
        return {
            '_success': True,
            'findings': findings,
            'summary': summary,
            'references_used': references_used,
        }

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
                'description': (
                    "Raise an ambiguity flag back to the user when you truly cannot proceed. "
                    "Policies declare ambiguity directly; only call this tool when the skill "
                    "itself decides the user must clarify before you can act.\n\n"
                    "Pick `type` by level:\n"
                    "- `general`    — intent itself is unclear (the utterance doesn't map cleanly to the active flow).\n"
                    "- `partial`    — intent is clear but the primary entity is unresolved (post/section/channel).\n"
                    "- `specific`   — a named slot value is missing or invalid. Pass `metadata={'missing_slot': <name>}`.\n"
                    "- `confirmation` — you have a candidate and need user sign-off before acting. Pass the candidate in `metadata`.\n\n"
                    "Actions:\n"
                    "- `declare` — raise the flag. Requires `type`; `metadata` optional.\n"
                    "- `ask`     — retrieve the clarifying question string for the declared ambiguity.\n"
                    "- `resolve` — clear the flag after the user answers. Pass resolved values in `metadata`.\n\n"
                    "Do NOT use this tool for tool-call failures or skill output-contract violations "
                    "— those route through the violation-metadata DisplayFrame path, not the user."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['declare', 'ask', 'resolve']},
                        'type': {'type': 'string', 'enum': ['general', 'partial', 'specific', 'confirmation']},
                        'metadata': {'type': 'object'},
                    },
                    'required': ['action'],
                },
            },
            {
                'name': 'coordinate_context',
                'description': (
                    "Fetch additional conversation history beyond what the skill already has. "
                    "The 'Resolved entities' block and the recent conversation are already in your "
                    "system prompt — try those first before calling this tool.\n\n"
                    "Actions:\n"
                    "- `get_history`    — compile the last `turns` utterances as a formatted string. "
                    "Typical values: 3 (default, short span), 6 (whole session for ~6-turn flows), 10 (debug).\n"
                    "- `get_turn`       — fetch one specific turn by `turn_id` (int, 1-indexed).\n"
                    "- `get_checkpoint` — fetch a named checkpoint (e.g. `label='last_outline'`).\n\n"
                    "Reach for this tool only when you need text the resolved block doesn't carry — "
                    "e.g. a user correction from 4 turns ago, or a proposal you need to quote verbatim."
                ),
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
                'name': 'call_flow_stack',
                'description': (
                    "Interact with the flow stack. Three actions:\n"
                    "- read: inspect stack state. `details` picks what to read: "
                    "'flows' (the full stack of queued and active flows), "
                    "'slots' (the active flow's filled slot values), "
                    "or 'flow_meta' (the active flow's class-level metadata).\n"
                    "- stackon: push a prerequisite flow onto the stack. "
                    "`details` is the flow name to push.\n"
                    "- fallback: pop the current flow and route to a sibling "
                    "when the user's intent is better served elsewhere. "
                    "`details` is the flow name to route to."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['read', 'stackon', 'fallback']},
                        'details': {
                            'type': 'string',
                            'description': "For read: one of 'flows', 'slots', 'flow_meta'. For stackon or fallback: the target flow name.",
                        },
                    },
                    'required': ['action'],
                },
            },
            {
                'name': 'execution_error',
                'description': (
                    "Signal a systemic error from inside a skill. The policy "
                    "consumes this from the tool log and routes the resulting frame "
                    "to RES with metadata['violation'] set.\n\n"
                    "Pick `violation` from the 8-item vocabulary:\n"
                    "- failed_to_save: a persistence tool didn't run or had no effect\n"
                    "- scope_mismatch: the flow ran at the wrong granularity\n"
                    "- missing_reference: an entity referenced in a slot doesn't exist\n"
                    "- parse_failure: skill output couldn't be parsed into the expected shape\n"
                    "- empty_output: skill returned nothing when content was expected\n"
                    "- invalid_input: a tool rejected (or would reject) the arguments given\n"
                    "- conflict: two slot values contradict\n"
                    "- tool_error: a deterministic tool returned `_success=False`\n\n"
                    "Use after retries and alternatives have been exhausted. For "
                    "user-intent ambiguity, use handle_ambiguity instead."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'violation': {
                            'type': 'string',
                            'enum': [
                                'failed_to_save', 'scope_mismatch', 'missing_reference',
                                'parse_failure', 'empty_output', 'invalid_input',
                                'conflict', 'tool_error',
                            ],
                        },
                        'message': {'type': 'string'},
                        'failed_tool': {'type': 'string'},
                    },
                    'required': ['violation', 'message'],
                },
            },
            {
                'name': 'save_findings',
                'description': (
                    "Terminal action for skills that return a list of structured results "
                    "(audit, future web_search, etc.). Call this instead of emitting JSON "
                    "in your text response — the policy reads the findings from this tool "
                    "call directly. Writes the payload to the scratchpad under the active "
                    "flow's name so downstream flows (e.g. polish-informed reading audit) "
                    "can consume it."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'findings': {
                            'type': 'array',
                            'items': {'type': 'object'},
                            'description': "List of finding objects. Each item is flow-specific — audit uses {sec_id, issue, severity, note, reference_posts}.",
                        },
                        'summary': {
                            'type': 'string',
                            'description': "One short paragraph summarizing the findings overall.",
                        },
                        'references_used': {
                            'type': 'array',
                            'items': {'type': 'string'},
                            'description': "IDs of any reference artifacts used (e.g. other post_ids for audit).",
                        },
                    },
                    'required': ['findings'],
                },
            },
        ]

    # -- Post-hook --------------------------------------------------------

    def _verify(self, active_flow):
        state = self.world.current_state()
        if active_flow.intent not in ['Converse', 'Internal'] and not state.has_issues:
            self._verify_active_post(active_flow)
        return state.keep_going

