import json
import logging
from dataclasses import dataclass
from types import MappingProxyType

from backend.components.task_artifact import TaskArtifact
from backend.components.dialogue_state import rehydrate_flow

from backend.utilities.services import (
    PostService, ContentService, AnalysisService, PlatformService,
    OutlineValidationError, PostNotFoundError,
)
from backend.modules.policies import *
from schemas.ontology import Intent
from utils.helper import dax2flow

log = logging.getLogger(__name__)

_FALLBACK_MESSAGE = "I wasn't able to finish that. Could you try rephrasing?"
_NUDGE_MESSAGE = ('Your last response had no visible text and no tool calls. Reply with your '
                  'final response to the user, or call a tool.')
_WRAP_UP_MESSAGE = ('Stop calling tools. Reply to the user now in 1-2 sentences of plain text: '
                    'summarize what was accomplished this turn, or ask what they need.')


@dataclass
class ArtifactCheck:
    passed: bool
    reason: str = ''
    is_error_frame: bool = False  # Policy classified this as an error artifact


_GENERAL_MISSING = {'intent', 'flow'}
_GENERAL_ERROR = {'misclassified', 'misdetected', 'user_error'}
_PARTIAL_MISSING = {'source', 'target', 'title', 'query'}
_PARTIAL_ENTITY = {'post', 'section', 'snippet', 'channel'}
_SPECIFIC_REASON = {'invalid_value', 'unclear_value', 'wrong_slot'}

# Read-only domain tools the orchestrator may call directly for trivial lookups. Every write
# still goes through a flow via activate_flow, preserving policy invariants, grounding
# discipline, and completion records.
READ_ONLY_DOMAIN_TOOLS = ('find_posts', 'read_metadata', 'read_section', 'search_notes',
                          'list_channels', 'channel_status')


def _block_summaries(artifact) -> list:
    """Compact view of the artifact blocks for the activate_flow tool result, so the
    orchestrator knows what the frontend will render (it must reference blocks, never
    restate them). Same card-shaped summary the e2e harness and agent logging use;
    selection blocks additionally carry their option labels."""
    summaries = []
    for block in artifact.blocks:
        data = block.data or {}
        summary = {'type': block.block_type, 'data_keys': sorted(data.keys())}
        if block.block_type in ('selection', 'checklist'):
            summary['options'] = [opt['label'] for opt in data['options']]
        if 'title' in data:  # e.g. a selection block's heading shown above its options
            summary['title'] = data['title']
        summaries.append(summary)
    return summaries


def _validate_ambig_metadata(level:str, metadata:dict) -> str | None:
    if 'missing' not in metadata:
        return f"metadata.missing is required for level={level!r}"
    missing = metadata['missing']
    if level == 'general':
        if missing not in _GENERAL_MISSING:
            return f"general.missing must be one of {sorted(_GENERAL_MISSING)}; got {missing!r}"
        if 'error' in metadata and metadata['error'] not in _GENERAL_ERROR:
            return f"general.error must be one of {sorted(_GENERAL_ERROR)}; got {metadata['error']!r}"
    elif level == 'partial':
        if missing not in _PARTIAL_MISSING:
            return f"partial.missing must be one of {sorted(_PARTIAL_MISSING)}; got {missing!r}"
        if 'entity' in metadata and metadata['entity'] not in _PARTIAL_ENTITY:
            return f"partial.entity must be one of {sorted(_PARTIAL_ENTITY)}; got {metadata['entity']!r}"
    elif level == 'specific':
        if 'reason' in metadata and metadata['reason'] not in _SPECIFIC_REASON:
            return f"specific.reason must be one of {sorted(_SPECIFIC_REASON)}; got {metadata['reason']!r}"
    elif level == 'confirmation':
        if 'question' not in metadata:
            return "confirmation.question is required (the clarification utterance shown to the user)"
    return None


class PEX:

    def __init__(self, config, ambiguity, engineer, memory, world):
        self.config = config
        self.max_rounds = config['limits']['max_rounds']
        self.max_corrective = config['limits']['max_corrective']
        self.ambiguity = ambiguity
        self.engineer = engineer
        self.memory = memory
        self.world = world
        self.flow_stack = world.flow_stack
        self.scratchpad = world.scratchpad

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
            # BusinessContext / FAQs (1)
            'search_faqs':       (self.memory.business, 'search_faqs'),
        }

        # Real prompt-token usage off the last acting-loop API response — Agent's compression
        # check reads it in the post-hook epilogue.
        self.last_prompt_tokens = 0
        # Flows that reached Completed during the current turn — reset per execute(), read by the
        # end-of-turn checkpoint.
        self._completed_this_turn = []
        self._nlu_thread = None  # this turn's parallel NLU think thread; joined+cleared by _settle_nlu
        # Orchestrator hot-path tools — wiring only; the implementations live in
        # DialogueState (state file), SessionScratchpad (scratchpad JSONL), and the policies.
        self._orchestrator_dispatch = {
            'read_state':           self._dispatch_read_state,
            'write_state':          self._dispatch_write_state,
            'activate_flow':        self.activate_flow,
            'append_to_scratchpad': self._dispatch_append_scratchpad,
            'read_scratchpad':      self._dispatch_read_scratchpad,
            'store_preference':     self._dispatch_store_preference,
        }

        components = {'engineer': engineer, 'memory': memory, 'config': config, 'ambiguity': ambiguity,
            'get_tools': self.get_tools_for_flow, 'flow_stack': self.flow_stack,
            'content_service': self._content_service, 'state_file': self.world.state_file,
            'scratchpad': self.scratchpad,
        }
        self._policies: dict[str, object] = {
            Intent.CONVERSE: ConversePolicy(components),
            Intent.RESEARCH: ResearchPolicy(components),
            Intent.DRAFT: DraftPolicy(components),
            Intent.REVISE: RevisePolicy(components),
            Intent.PUBLISH: PublishPolicy(components),
        }
        self.initialization()

    def initialization(self):
        # Wipe snapshot history from prior sessions
        for stale in self._content_service._snap_root.glob('snap_*.json'):
            stale.unlink()

    # -- Pre-hook ---------------------------------------------------------

    def _security_check(self, flow):
        """Check for lethal trifecta tool capability violations."""
        tools = self.get_tools_for_flow(flow)
        for tool in tools:
            caps = tool.get('capabilities', {})
            if (caps.get('accesses_private_data')
                    and caps.get('receives_untrusted_input')
                    and caps.get('communicates_externally')):
                self.ambiguity.declare(
                    'confirmation',
                    metadata={
                        'missing': 'tool_approval',
                        'question': (
                            f'This action requires your approval because '
                            f'"{tool["name"]}" accesses private data, accepts '
                            f'user input, and communicates externally.'
                        ),
                        'tool': tool['name'],
                        'risk_type': 'lethal_trifecta',
                    },
                )
                artifact = TaskArtifact(flow.name())
                artifact.add_block({'type': 'confirmation', 'data': {
                    'prompt': self.ambiguity.ask(flow.name()),
                    'confirm_label': 'Approve',
                    'cancel_label': 'Cancel',
                }})
                return artifact

        return None

    def _settle_nlu(self, wait:bool=True):
        # Join this turn's parallel NLU think thread so belief reads see THIS turn's detection,
        # then clear it — later calls are no-ops. Plan/Clarify turns are REQUIRED to wait (their
        # read_state blocks); flow execution passes wait=False and continues if NLU is still
        # running — it only reaps a finished thread so belief reads pick up a landed detection.
        if self._nlu_thread is None:
            return
        if not wait and self._nlu_thread.is_alive():
            return
        self._nlu_thread.join()
        self._nlu_thread = None

    # -- Validation -------------------------------------------------------

    def _validate_artifact(self, artifact, flow):
        """Check whether a artifact is good enough to show to the user. A artifact with a 'violation'
        set is already recognized as an error artifact, so it does NOT need Tier-1 retry. Return
        passed=False + is_error_frame=True so the outer caller routes it directly to the error path."""
        if self.ambiguity.present():
            return ArtifactCheck(passed=True)
        if 'violation' in artifact.data:
            violation = artifact.data['violation']
            return ArtifactCheck(passed=False, reason=f'violation:{violation}', is_error_frame=True)
        block_data, block_types = self._merge_block_data(artifact)

        has_data = ('default' in block_types or block_data or artifact.thoughts or artifact.data)
        if not has_data:
            return ArtifactCheck(passed=False, reason='Frame has no data')
        last_user = self.world.context.last_user_text
        thoughts = artifact.thoughts
        if last_user and thoughts.strip() == last_user.strip():
            return ArtifactCheck(passed=False, reason='Response echoes user input verbatim')
        if flow.name() in self.config['content_validation']:
            card_content = block_data.get('content', '')
            slot_text = "collected_slot_evidence(flow)"
            visible = '\n'.join(part for part in (thoughts, card_content, slot_text) if part)
            # return self._llm_quality_check(visible)
        return ArtifactCheck(passed=True)

    @staticmethod
    def _merge_block_data(artifact):
        merged = {}
        block_types = []
        for block in artifact.blocks:
            merged.update(block.data)
            block_types.append(block.block_type)
        return merged, block_types

    def _llm_quality_check(self, content:str):
        last_user = self.world.context.last_user_text
        convo = self.world.context.compile_history(look_back=4)
        prompt = (
            f'Recent conversation:\n{convo}\n\n'
            f'User request: {last_user}\n\nAgent output:\n{content}'
        )
        try:
            raw_output = self.engineer(prompt, 'quality_check', model='low', max_tokens=128)
            verdict = raw_output.strip().lower()
            if verdict.startswith('pass'):
                return ArtifactCheck(passed=True)
            reason = verdict.removeprefix('fail:').strip() or 'LLM quality check failed'
            return ArtifactCheck(passed=False, reason=reason)
        except Exception:
            return ArtifactCheck(passed=True)

    # -- Acting loop (the Assistant's single PEX entry) -------------------

    def execute(self, state, context, system_prompt, *, dax=None, payload=None, text='', nlu_thread=None) -> str:
        """The acting loop the Assistant calls once per turn, after NLU has written belief. A
        pure click (dax, no text) is resolved deterministically — no LLM. Otherwise the bounded
        orchestrator loop reads belief (read_state) and decides by intent per the system prompt,
        dispatching tool calls through `_dispatch_tool`. Returns the spoken utterance."""
        self._nlu_thread = nlu_thread
        self._completed_this_turn = []
        if dax and not text.strip():
            utterance = self._execute_click(state, context, dax, payload or {})
        else:
            message = text
            if dax:  # action + text: inject the resolved flow as context, then run the loop
                flow_name = dax2flow(dax)
                message = (f'[action] This turn arrived with a resolved flow: {flow_name!r} '
                           f'(dax {dax}, payload {json.dumps(payload or {}, default=str)}). '
                           f'Do not re-decide the click — build on it.\n{text}')
            context.append_message({'role': 'user', 'content': message})
            utterance = self._run_loop(system_prompt)
        self._record_checkpoint(state, context)
        return utterance

    def _record_checkpoint(self, state, context):
        """Backward-looking end-of-turn snapshot recorded as a 'System' turn in the Context:
        which flows completed this turn, which flow is still active, and the grounded entity. A
        record of what just happened — distinct from the forward-looking active-flow pointer."""
        active = self.flow_stack.get_flow(status='Active')
        parts = [f"completed: {', '.join(self._completed_this_turn) or 'none'}",
                 f"active: {active.name() if active else 'none'}"]
        if state.grounding['post']:
            parts.append(f"post: {state.grounding['post']}")
        context.add_turn('System', f"[checkpoint] {' | '.join(parts)}", turn_type='checkpoint')

    def _execute_click(self, state, context, dax:str, payload:dict) -> str:
        """Pure click: the dax names the flow and NLU.react already filled belief. Stack the
        flow, apply the react-filled slots from belief, activate it — the artifact thoughts ARE
        the reply (no LLM loop)."""
        flow_name = dax2flow(dax)
        context.append_message({'role': 'user', 'content':
            f'[click] dax={dax} flow={flow_name} payload={json.dumps(payload, default=str)}'})
        flow = self.flow_stack.find_by_name(flow_name) or self.flow_stack.stackon(flow_name)
        if state.pred_slots:
            flow.fill_slot_values(state.pred_slots)
            flow.is_filled()
        result = self.activate_flow({'flow_name': flow_name})
        artifact = self.world.latest_artifact()
        utterance = result.get('question') or artifact.thoughts or _FALLBACK_MESSAGE
        context.append_message({'role': 'assistant', 'content': utterance})
        return utterance

    def _run_loop(self, system_prompt:str) -> str:
        """The bounded acting loop: call the LLM with the frozen system prompt + persistent
        message list + orchestrator tool catalog; dispatch tool calls through `_dispatch_tool`;
        append results. A plain-text response with no tool calls ends the turn and IS the
        utterance, verbatim."""
        context = self.world.context
        tools = self.get_tools_for_orchestrator()
        valid = {tool['name'] for tool in tools}
        model_id = self.config['models']['overrides']['orchestrator']['model_id']

        nudged = False
        errors = 0
        last_call = None
        for round_idx in range(self.max_rounds):
            response = self.engineer._call_claude(system_prompt, context.messages,
                                                  model_id, tools=tools, max_tokens=4096)
            self._track_usage(response)
            text_parts = [block.text for block in response.content if block.type == 'text']
            tool_uses = [block for block in response.content if block.type == 'tool_use']
            text = '\n'.join(part for part in text_parts if part).strip()

            if not tool_uses:
                if text:
                    context.append_message({'role': 'assistant', 'content': text})
                    return text
                if nudged:  # thinking-only twice → canned fallback
                    context.append_message({'role': 'assistant', 'content': _FALLBACK_MESSAGE})
                    return _FALLBACK_MESSAGE
                nudged = True
                context.append_message({'role': 'user', 'content': _NUDGE_MESSAGE})
                continue

            blocks = [{'type': 'text', 'text': part} for part in text_parts if part]
            blocks += [{'type': 'tool_use', 'id': tu.id, 'name': tu.name,
                        'input': dict(tu.input or {})} for tu in tool_uses]
            context.append_message({'role': 'assistant', 'content': blocks})

            results = []
            for tool_use in tool_uses:
                # Pairing invariant: every appended tool_use MUST get a tool_result in the next
                # message, even if the dispatch path itself crashes — a dangling tool_use poisons
                # messages.jsonl for every later turn of the session.
                try:
                    result, last_call = self._guarded_call(tool_use, valid, last_call)
                except Exception as ecp:  # noqa: BLE001 — convert to a corrective tool error
                    log.exception('tool dispatch crashed: %s', ecp)
                    result = {'_success': False, '_error': 'server_error',
                              '_message': f'{type(ecp).__name__}: {ecp}'}
                    last_call = None
                # hook: post-tool
                errors = errors + 1 if not result['_success'] else 0
                log.info('  orch round=%d tool=%s ok=%s', round_idx + 1, tool_use.name,
                         result['_success'])
                results.append({'type': 'tool_result', 'tool_use_id': tool_use.id,
                                'content': json.dumps(result, default=str)})
            context.append_message({'role': 'user', 'content': results})
            if errors >= self.max_corrective:
                break  # the model keeps failing tool calls — stop burning rounds
        return self._final_emit(system_prompt, model_id)

    def _final_emit(self, system_prompt:str, model_id:str) -> str:
        """Round budget or corrective cap exhausted: one last no-tools call forces a plain-text
        wrap-up (the terminal emit), so completed work still gets a real reply instead of the
        canned fallback. Falls back only if even that produces nothing."""
        context = self.world.context
        context.append_message({'role': 'user', 'content': _WRAP_UP_MESSAGE})
        response = self.engineer._call_claude(system_prompt, context.messages,
                                              model_id, max_tokens=1024)
        self._track_usage(response)
        text_parts = [block.text for block in response.content if block.type == 'text']
        utterance = '\n'.join(part for part in text_parts if part).strip() or _FALLBACK_MESSAGE
        context.append_message({'role': 'assistant', 'content': utterance})
        return utterance

    def _guarded_call(self, tool_use, valid:set, last_call) -> tuple[dict, tuple]:
        """Guardrails around one tool call: hallucinated names and identical consecutive calls
        return corrective errors instead of dispatching. Everything else routes through
        `_dispatch_tool`, which already converts bad args into corrective tool errors the model
        can retry on. These guards are the legitimate exception to the no-defensive-code rule —
        LLM output is genuinely unpredictable input.

        `last_call` is (name+args key, succeeded). Dedupe only fires when the previous identical
        call SUCCEEDED — retrying the same call after a transient tool error (server_error from
        an overloaded LLM, a flaky channel API) is legitimate recovery, not a loop."""
        # hook: pre-tool
        call = (tool_use.name, json.dumps(dict(tool_use.input or {}), sort_keys=True, default=str))
        if tool_use.name not in valid:
            result = {'_success': False, '_error': 'invalid_input',
                      '_message': f'Unknown tool: {tool_use.name!r}. Use a tool from your tool list.'}
        elif last_call and call == last_call[0] and last_call[1]:
            result = {'_success': False, '_error': 'duplicate_call',
                      '_message': 'Identical consecutive tool call skipped — change the '
                                  'arguments or respond to the user.'}
        else:
            result = self._dispatch_tool(tool_use.name, dict(tool_use.input or {}))
            if '_success' not in result:  # manage_memory keeps its old {'status': ...} contract
                result['_success'] = result.get('status') == 'success'
        return result, (call, result['_success'])

    def _track_usage(self, response):
        """Record real prompt-token usage off an acting-loop API response (Agent's compression
        trigger reads it, never estimates). Cache reads/writes count toward the window."""
        usage = response.usage
        if usage:
            self.last_prompt_tokens = (usage.input_tokens
                                       + (usage.cache_creation_input_tokens or 0)
                                       + (usage.cache_read_input_tokens or 0))

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
                return self._dispatch_manage_memory(tool_input)
            elif tool_name == 'call_flow_stack':
                return self._dispatch_flow_stack_tool(tool_input)
            elif tool_name == 'save_findings':
                return self._dispatch_save_findings_tool(tool_input)
            elif tool_name in self._orchestrator_dispatch:
                return self._orchestrator_dispatch[tool_name](tool_input)
            else:
                return {
                    '_success': False, '_error': 'invalid_input',
                    '_message': f'Unknown tool: {tool_name}',
                }
        except OutlineValidationError as ecp:
            return {'_success': False, '_error': 'validation', '_message': str(ecp)}
        except PostNotFoundError as ecp:
            return {'_success': False, '_error': 'not_found', '_message': str(ecp)}
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
        action = params['action']
        if action == 'present':
            return {'_success': True, 'present': self.ambiguity.present(),
                    'level': self.ambiguity.level}
        if action == 'declare':
            if 'level' not in params or 'metadata' not in params:
                return {'_success': False, '_error': 'invalid_input',
                        '_message': "declare requires both 'level' and 'metadata'"}
            level, metadata = params['level'], params['metadata']
            err = _validate_ambig_metadata(level, metadata)
            if err:
                log.info('[ambig-trace] dispatch declare REJECTED level=%s metadata=%s err=%s',
                         level, metadata, err)
                return {'_success': False, '_error': 'invalid_input', '_message': err}
            self.ambiguity.declare(level, metadata=metadata, observation=params.get('observation', ''))
            return {'_success': True}
        return {'_success': False, '_error': 'invalid_input', '_message': f'Unknown action: {action}'}

    def _dispatch_save_findings_tool(self, params:dict) -> dict:
        """Persist structured findings to the scratchpad under the active flow's name.

        Tool-call-shaped replacement for skills that would otherwise emit a JSON blob as their
        terminal text response. The policy reads the findings out of tool_log via
        `extract_tool_result`; downstream flows read them via
        `scratchpad.read(<flow_name>)`."""
        findings = params.get('findings', [])
        summary = params.get('summary', '')
        references_used = params.get('references_used', [])
        flow = self.flow_stack.get_flow()
        key = flow.name() if flow else 'findings'
        self.scratchpad.write(key, {
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

    # -- Orchestrator hot-path dispatch -----------------------------------
    # Thin wiring onto the state, memory, and NLU surfaces. Errors raised below (bad
    # write_state op, unknown flow, grounding violation) are caught by _dispatch_tool's
    # try/except and returned as corrective tool errors for the orchestrator loop to retry on.

    def _dispatch_read_state(self, params:dict) -> dict:
        self._settle_nlu()
        return {'_success': True, 'state': self.world.current_state().read_state()}

    def _dispatch_write_state(self, params:dict) -> dict:
        state = self.world.current_state()
        kwargs = dict(params.get('fields', {}))
        for key in ('flow_name', 'plan_id'):
            if key in params:
                kwargs[key] = params[key]
        if params['op'] == 'update_flow' and 'slots' in kwargs:
            top = rehydrate_flow(state.flow_stack[-1])
            unknown = [name for name in kwargs['slots'] if name not in top.slots]
            if unknown:  # corrective error — fill_slot_values would drop these silently
                return {'_success': False, '_error': 'invalid_input',
                        '_message': f'flow {top.name()!r} has no slot(s) {unknown}; '
                                    f'valid slots: {list(top.slots)}'}
        document = state.write_state(self.world.state_file(), params['op'], **kwargs)
        if params['op'] == 'pop_completed':
            # Mirror the pop onto the live stack: activate_flow's epilogue re-syncs
            # state.flow_stack from it, so a stale live entry would resurrect popped flows.
            self.flow_stack.pop_completed()
        if params['op'] == 'stackon' and params.get('active'):
            # Single-call staging (Derek 2026-07-03): stackon handed over matching slots; fold
            # in belief's pred_slots, then run the policy — no update_flow / activate_flow calls.
            self._settle_nlu(wait=False)  # reap a landed detection so the fold reads fresh belief
            self._apply_belief_slots(state, params['flow_name'])
            return self.activate_flow({'flow_name': params['flow_name']})
        return {'_success': True, 'state': document}

    def _apply_belief_slots(self, state, flow_name:str):
        """Fold belief's `pred_slots` into the just-stacked flow entry when NLU's detection is
        this same flow — the code-side replacement for the recipe's update_flow step."""
        if not state.pred_flows or state.pred_flows[0]['flow_name'] != flow_name:
            return
        top = rehydrate_flow(state.flow_stack[-1])
        slots = {name: value for name, value in state.pred_slots.items()
                 if name in top.slots and value}
        if slots:
            state.write_state(self.world.state_file(), 'update_flow', slots=slots)

    def prestage(self, state) -> bool:
        """Fix 1 Option B: stage NLU's confident single-flow detection in code, so the loop
        starts with the flow staged and its first useful move is activate_flow. Callers invoke
        this ONLY where belief is fresh (the awaited think path — the parallel-think path
        reaches PEX before this turn's detection lands). Plan / Converse turns stay the
        orchestrator's call, and a low-confidence detection has already declared ambiguity."""
        if self.ambiguity.present() or not state.pred_flows:
            return False
        if state.pred_intent not in ('Research', 'Draft', 'Revise', 'Publish'):
            return False
        flow_name = state.pred_flows[0]['flow_name']
        state.write_state(self.world.state_file(), 'stackon', flow_name=flow_name)
        self._apply_belief_slots(state, flow_name)
        return True

    def activate_flow(self, params:dict) -> dict:
        """Run the named flow's policy inline — the delegate_task analogue. Grounding comes
        from the state file's grounding block; _security_check and _validate_artifact re-attach
        around the policy run. On completion the flow's completion record is written to the
        session scratchpad and returned as the tool result. State-file persistence stays with
        write_state (the orchestrator epilogue)."""
        self._settle_nlu(wait=False)  # flow execution never blocks on NLU — only Plan/Clarify wait
        state = self.world.current_state()
        flow = self._stage_flow(state, params['flow_name'])

        # hook: pre-flow
        approval = self._security_check(flow)
        if approval:
            return {'_success': False, '_error': 'approval_required',
                    '_message': approval.blocks[0].data['prompt']}

        if state.grounding['post']:
            state.active_post = state.grounding['post']
        policy = self._policies[flow.intent]
        artifact = policy.execute(state, self.world.context, self._dispatch_tool)
        record = policy.pop_completion()  # set when the policy completed via complete_flow
        self.world.insert_artifact(artifact)
        if state.active_post:  # the grounding block stays authoritative
            state.grounding['post'] = state.active_post

        # hook: post-flow
        check = self._validate_artifact(artifact, flow)
        if not check.passed:
            if check.is_error_frame:
                return {'_success': False, '_error': 'execution_error',
                        '_message': artifact.data['violation'], 'thoughts': artifact.thoughts}
            return {'_success': False, '_error': 'validation', '_message': check.reason}

        state.flow_stack = self.flow_stack.to_list()
        blocks = _block_summaries(artifact)
        if flow.status != 'Completed':
            question = self.ambiguity.ask(flow.name()) if self.ambiguity.present() else ''
            return {'_success': True, 'status': flow.status, 'thoughts': artifact.thoughts,
                    'question': question, 'blocks': blocks}
        self._completed_this_turn.append(flow.name())  # for the end-of-turn checkpoint
        if record is None:  # policy completed without calling complete_flow — synthesize a record
            summary = artifact.thoughts or f'{flow.name()} completed'
            record = self.scratchpad.write_completion(flow.name(), summary, metadata=artifact.data)
        return {'_success': True, 'status': flow.status, 'completion': record, 'blocks': blocks}

    def _stage_flow(self, state, flow_name:str):
        """Make the named flow the live top-of-stack for the policy run, rehydrating it
        from the state file's flow_stack block when an entry exists.
        A live flow staged on an earlier turn gets the entry's slot fills layered on —
        write_state slot fills land in the state file, so the entry is authoritative for
        slots while the live flow keeps policy-side attributes the file does not carry."""
        live = self.flow_stack.find_by_name(flow_name)
        if live and live.status in ('Completed', 'Invalid'):
            # A finished run of this flow is history, never a staging target: refilling it
            # would APPEND this turn's entity onto last turn's SourceSlot values and the
            # policy would ground on the stale first entry (the grounding-switch bug).
            live = None
        entry = next((item for item in reversed(state.flow_stack)
                      if item['flow_name'] == flow_name
                      and item['status'] not in ('Completed', 'Invalid')), None)
        if live:
            if entry:
                live.fill_slot_values(entry['slots'])
                live.is_filled()
            return live
        if entry is None:
            return self.flow_stack.stackon(flow_name)
        flow = rehydrate_flow(entry)
        flow.status = 'Active'
        self.flow_stack._stack.append(flow)
        return flow

    def _dispatch_append_scratchpad(self, params:dict) -> dict:
        self.scratchpad.write(params['entry'])  # `writer` stamped by code
        return {'_success': True, 'size': self.scratchpad.size}

    def _dispatch_read_scratchpad(self, params:dict) -> dict:
        entries = self.scratchpad.read(writer=params.get('writer'), keys=params.get('keys'))
        return {'_success': True, 'entries': entries}

    def _dispatch_store_preference(self, params:dict) -> dict:
        """Persist a durable user preference to L2."""
        self.memory.preferences.store_preference(params['key'], params['value'])
        return {'_success': True, 'key': params['key']}

    def _dispatch_manage_memory(self, params:dict) -> dict:
        """The combined memory tool: scratchpad read/write + preference read. Keeps the legacy
        {'status': ...} result contract."""
        action = params.get('action', '')
        if action == 'read_scratchpad':
            return {'status': 'success', 'result': self.scratchpad.read(params.get('key'))}
        if action == 'write_scratchpad':
            key = params.get('key', '')
            if not key:
                return {'status': 'error', 'message': 'key is required'}
            self.scratchpad.write(key, params.get('value', ''))
            return {'status': 'success', 'result': 'written'}
        if action == 'read_preferences':
            return {'status': 'success', 'result': self.memory.preferences.read()}
        return {'status': 'error', 'message': f'Unknown action: {action}'}

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
                    "Actions:\n"
                    "- `declare` — raise the flag. Requires `level` and `metadata`; `observation` is optional except at `confirmation` level (which uses `metadata.question` instead).\n"
                    "- `present` — return whether an ambiguity is already pending and at what level. Use to avoid overwriting a prior declaration.\n\n"
                    "Per-level metadata shape (validated at dispatch — wrong shape returns invalid_input):\n"
                    "- `general`      → metadata.missing ∈ {intent, flow}; metadata.error ∈ {misclassified, misdetected, user_error} (optional).\n"
                    "- `partial`      → metadata.missing ∈ {source, target, title, query}; metadata.entity ∈ {post, section, snippet, channel} (optional).\n"
                    "- `specific`     → metadata.missing = <slot name>; metadata.reason ∈ {invalid_value, unclear_value, wrong_slot} (optional).\n"
                    "- `confirmation` → metadata.missing = <description>; metadata.question = <clarification utterance> (REQUIRED); metadata.candidates: list[str] (optional).\n\n"
                    "`observation` (top-level) is the agent-authored clarification utterance for general/partial/specific. "
                    "Confirmation-level uses `metadata.question` instead — `observation` is ignored at that level.\n\n"
                    "General-level ambiguity is only authored by `rework`, `refine`, `explain`. Other skills should declare specific/partial.\n\n"
                    "Do NOT use this tool for tool-call failures or skill output-contract violations "
                    "— those route through the violation-metadata TaskArtifact path via `execution_error`, not the user."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'action':      {'type': 'string', 'enum': ['declare', 'present']},
                        'level':       {'type': 'string', 'enum': ['general', 'partial', 'specific', 'confirmation']},
                        'metadata':    {'type': 'object', 'description': 'shape required per level — see description'},
                        'observation': {'type': 'string', 'description': 'agent-authored clarification utterance (general/partial/specific only)'},
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
                    "consumes this from the tool log and routes the resulting artifact "
                    "to the error path with metadata['violation'] set.\n\n"
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
                    "flow's name so downstream flows (e.g. an audit-informed write) "
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

    def get_tools_for_orchestrator(self) -> list[dict]:
        """The orchestrator's tool list: hot-path dedicated tools, the three long-tail
        component dispatch tools, and the read-only domain allowlist. call_flow_stack is
        deliberately absent — its job lives in read_state/write_state."""
        tools = self._orchestrator_tool_definitions()
        component = {tool['name']: tool for tool in self._component_tool_definitions()}
        tools += [component[name] for name in ('handle_ambiguity', 'coordinate_context',
                                               'manage_memory')]
        for tool_name in READ_ONLY_DOMAIN_TOOLS:
            tool_def = self._get_tool_def(tool_name)
            if tool_def:
                tools.append(tool_def)
        return tools

    def _orchestrator_tool_definitions(self) -> list[dict]:
        return [
            {
                'name': 'read_state',
                'description': (
                    "Read the session's DialogueState file: user beliefs (intent, goal, "
                    "confirmed/rejected, workflow_step), the grounding block (the active "
                    "post/sec/snip/chl entity), the flow stack, and flags. Cheap read — call it "
                    "whenever you need current state rather than guessing."
                ),
                'input_schema': {'type': 'object', 'properties': {}, 'required': []},
            },
            {
                'name': 'write_state',
                'description': (
                    "Mutate the DialogueState file — the ONLY writer of state.json. Ops:\n"
                    "- `update`        — set user-belief / grounding / flag fields. Pass them in "
                    "`fields`, e.g. {goal: ..., workflow_step: 3, grounding: {post: ...}}.\n"
                    "- `update_flow`   — mutate the top stack flow. `fields` may carry `slots` "
                    "(slot-name → value, in the exact shapes belief's `pred_slots` carries: "
                    "strings for single-value slots, lists for multi-value slots), `stage`, and "
                    "`status`. An entity-grounded flow cannot reach status=Completed while "
                    "grounding.post is empty.\n"
                    "- `stackon`       — push `flow_name` (optional `plan_id`) on top of the "
                    "stack; matching slot values hand over from the prior flow automatically. "
                    "Pass `active: true` to also fold in belief's `pred_slots` and run the "
                    "policy immediately — the one-call way to dispatch a flow.\n"
                    "- `fallback`      — replace the top flow with `flow_name`, transferring "
                    "matching slot values.\n"
                    "- `pop_completed` — remove Completed/Invalid flows, activating the next "
                    "Pending one.\n"
                    "Returns the full state document after the write."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'op': {'type': 'string', 'enum': ['update', 'update_flow', 'stackon',
                                                          'fallback', 'pop_completed']},
                        'fields': {'type': 'object',
                                   'description': 'for update / update_flow — the fields to set'},
                        'flow_name': {'type': 'string',
                                      'description': 'for stackon / fallback — the target flow'},
                        'plan_id': {'type': 'string', 'description': 'for stackon under a Plan'},
                        'active': {'type': 'boolean',
                                   'description': 'for stackon — stage and run the flow in one call'},
                    },
                    'required': ['op'],
                },
            },
            {
                'name': 'activate_flow',
                'description': (
                    "Run the named flow's policy inline as a sub-agent (skill prompt + domain "
                    "tools). Slots come from the flow's stack entry; grounding from the state "
                    "file. On completion you get the completion record {flow, summary, metadata} "
                    "— also appended to the scratchpad. A non-completed run returns the flow "
                    "status plus any pending clarification question. `blocks` summarizes the UI "
                    "artifact (cards, selection options) the frontend renders alongside your "
                    "reply — reference it briefly, never restate its contents. ALL domain "
                    "writes go through this tool, never through domain tools directly."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'flow_name': {'type': 'string',
                                      'description': 'catalog name of the flow to run'},
                    },
                    'required': ['flow_name'],
                },
            },
            {
                'name': 'append_to_scratchpad',
                'description': (
                    "Append one agent-belief entry to the session scratchpad (JSONL). `entry` is "
                    "a schema-free JSON object — intermediate findings, tool results worth "
                    "keeping, working notes. The `writer` stamp is added by code; do not include "
                    "a writer key yourself."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {'entry': {'type': 'object'}},
                    'required': ['entry'],
                },
            },
            {
                'name': 'store_preference',
                'description': (
                    "Persist a durable user preference to L2 memory — preferred tone, default "
                    "post length, heading style, Oxford-comma usage, channel defaults. Survives "
                    "the session. Pass the preference `key` and its `value`."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'key': {'type': 'string'},
                        'value': {'type': 'string'},
                    },
                    'required': ['key', 'value'],
                },
            },
            {
                'name': 'read_scratchpad',
                'description': (
                    "Read session scratchpad entries, newest last. Optional filters: `writer` "
                    "('orchestrator' or a flow name) and `keys` (only entries carrying every "
                    "named key — e.g. ['flow', 'summary'] selects completion records)."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'writer': {'type': 'string'},
                        'keys': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': [],
                },
            },
        ]


