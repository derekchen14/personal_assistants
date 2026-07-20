import json
import logging
from dataclasses import dataclass
from types import MappingProxyType

from backend.components.task_artifact import TaskArtifact
from backend.components.flow_stack import FlowStack, flow_classes
from backend.components.session_scratchpad import SessionScratchpad

from backend.utilities.services import (
    PostService, ContentService, AnalysisService, PlatformService,
    OutlineValidationError, PostNotFoundError,
)
from backend.modules.policies import *
from schemas.ontology import Intent

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
# still goes through a flow via manage_flows, preserving policy invariants, grounding
# discipline, and completion entries.
READ_ONLY_DOMAIN_TOOLS = ('find_posts', 'read_metadata', 'read_section', 'search_notes',
                          'list_channels', 'channel_status')

def _block_summaries(artifact) -> list:
    """Compact view of the artifact blocks for execute()'s policy result, so the
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


def corrective(error:str, message:str) -> dict:
    """The corrective tool-error shape — handed back to the model to retry on, never raised."""
    return {'_success': False, '_error': error, '_message': message}


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


class PolicyExecutor:

    def __init__(self, config, engineer):
        self.config = config
        self.max_rounds = config['limits']['max_rounds']
        self.max_corrective = config['limits']['max_corrective']
        self.max_reads = config['limits']['max_reads']
        self.engineer = engineer

        self.flow_stack = FlowStack(config, flow_classes=flow_classes)
        self.session_scratchpad = SessionScratchpad()
        self._world = None  # set via the `world` property once the Assistant builds the World

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
            # PlatformService (4)
            'release_post':      (self._platform_service, 'release_post'),
            'cancel_release':    (self._platform_service, 'cancel_release'),
            'list_channels':     (self._platform_service, 'list_channels'),
            'channel_status':    (self._platform_service, 'channel_status'),
        }

        # Real prompt-token usage off the last agent-loop API response — MEM's compaction
        # check reads it in the turn wrap (MEM.recap).
        self.last_prompt_tokens = 0
        # Every flow popped during the current turn — Completed or Invalid (round 2.16). Reset
        # per prepare(), passed to MEM.recap (which stores only the Completed members) and read
        # by orchestrate()'s round-budget reset.
        self.recently_finished = []
        self._reads = 0  # per-turn count of successful read-only domain-tool calls; reset in prepare()
        self._turn_start = 0  # context.num_utterances at prepare() — scopes hook reads to this turn
        # PEX-Agent round state (round 2.16): one round per orchestrate() call, so the old loop
        # locals live here; prepare() resets them per turn.
        self.rounds = 0        # rounds since the last completion — a completion resets the budget
        self.finished = 0      # Completed members of recently_finished already counted
        self.errors = 0        # consecutive corrective tool failures
        self.nudged = False    # a thinking-only miss already nudged this turn
        self.last_call = None  # (name+args key, succeeded) — _guarded_call's dedupe memory
        # Orchestrator hot-path tools — wiring only; the implementations live in
        # DialogueState (state file), SessionScratchpad (scratchpad JSONL), and the policies.
        self._orchestrator_toolset = {
            'manage_flows':             self._manage_flows,
            'understand':               self._understand_user,
            'append_to_scratchpad':     self._append_scratchpad,
            'store_preference':         self._store_preference,
            'ask_clarification_question': self._ask_clarification,
        }
        self._policies: dict[str, object] = {}  # built when the world is attached (setter below)
        self.initialization()

    @property
    def world(self):
        return self._world

    @world.setter
    def world(self, world):
        """Assigning the world finishes the wiring: the one domain tool that reads a MEM
        component, and the policies (their scoped components dict carries world-bound references —
        sub-agents never see the whole world)."""
        self._world = world
        self.tools['search_documents'] = (world.knowledge, 'search_documents')
        components = {'engineer': self.engineer, 'config': self.config, 'ambiguity': world.ambiguity,
            'get_tools': self.get_tools_for_flow, 'flow_stack': self.flow_stack,
            'content_service': self._content_service, 'scratchpad': self.session_scratchpad,
        }
        self._policies = {
            Intent.CONVERSE: ConversePolicy(components),
            Intent.RESEARCH: ResearchPolicy(components),
            Intent.DRAFT: DraftPolicy(components),
            Intent.REVISE: RevisePolicy(components),
            Intent.PUBLISH: PublishPolicy(components),
        }

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
                self.world.ambiguity.recognize(
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
                    'prompt': self.world.ambiguity.ask(flow.name()),
                    'confirm_label': 'Approve',
                    'cancel_label': 'Cancel',
                }})
                return artifact

        return None

    # -- Validation -------------------------------------------------------

    def verify(self, artifact, flow):
        """Check whether a artifact is good enough to show to the user. A artifact with a 'violation'
        set is already recognized as an error artifact, so it does NOT need Tier-1 retry. Return
        passed=False + is_error_frame=True so the outer caller routes it directly to the error path."""
        if self.world.ambiguity.is_present:
            return ArtifactCheck(passed=True)
        if 'violation' in artifact.data:
            violation = artifact.data['violation']
            return ArtifactCheck(passed=False, reason=f'violation:{violation}', is_error_frame=True)
        block_data, block_types = self._merge_block_data(artifact)

        has_data = ('default' in block_types or block_data or artifact.thoughts or artifact.data)
        if not has_data:
            return ArtifactCheck(passed=False, reason='Frame has no data')
        user_utterance = self.world.context.last_user_utt
        thoughts = artifact.thoughts
        if user_utterance and thoughts.strip() == user_utterance.strip():
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
        context = self.world.context
        prompt = (
            f'Recent conversation:\n{context.compile_history()}\n\n'
            f'User request: {context.last_user_utt}\n\nAgent output:\n{content}'
        )
        try:
            raw_output = self.engineer(prompt, task='quality_check', tier='low', max_tokens=128)
            verdict = raw_output.strip().lower()
            if verdict.startswith('pass'):
                return ArtifactCheck(passed=True)
            reason = verdict.removeprefix('fail:').strip() or 'LLM quality check failed'
            return ArtifactCheck(passed=False, reason=reason)
        except Exception:
            return ArtifactCheck(passed=True)

    # -- The PEX Agent: prepare() + one round per orchestrate() call ------

    def prepare(self):
        """Hook point 1 — PEX's first step, called by take_turn before the round loop. Per-turn
        resets, the Plan/Clarify gate (the only intents that wait on NLU's settled thinking),
        then the prediction note: one kind-5 system turn handing round 1 the belief every
        predictor already wrote (`state.pred_flows`, mapped at prediction time — no lookup, no
        stackon; the agent stacks through manage_flows). An expired wait fails the turn loudly —
        the raise lands in take_turn's safety net."""
        self.recently_finished = []
        self._reads = 0
        self._turn_start = self.world.context.num_utterances
        self.rounds, self.finished, self.errors = 0, 0, 0
        self.nudged, self.last_call = False, None
        state = self.world.state
        state.keep_going = True
        if state.pred_intent in ('Plan', 'Clarify'):
            self.wait_for_nlu('hook point 1')
        pred_flow = state.pred_flows[0]['name']
        context = self.world.context
        user_turn = next(turn for turn in reversed(context.full_conversation(as_turns=True))
                         if turn.role == 'user')
        if user_turn.turn_type == 'action':   # golden dax — react() already stacked it; force it
            note = (f"[click] The user selected '{pred_flow}' directly. You MUST run it as your "
                    f"next step with manage_flows (update status='Active').")
        else:                                 # TypeSafe — a prediction the agent may override
            note = (f"[typesafe] intent={state.pred_intent} — the predicted flow is "
                    f"'{pred_flow}'. Stack and run it with manage_flows (op='stackon'), pick a "
                    f"different flow, or reply directly.")
        context.add_turn('system', {'text': note})   # kind 5 — round 1 sees the prediction

    def orchestrate(self, system_prompt) -> str:
        """One PEX-Agent round — the while-loop lives in take_turn (`state.keep_going`).
        Returns '' on mid-turn rounds and the reply text on the terminal round; the reply is
        PEX's return value, nothing else carries it. Tool calls route through _guarded_call →
        call_tool; NLU's mid-turn stack changes surface at the hook 3/5 reads. Two exits end
        the turn: the terminal no-tool text, or _final_emit() (nudged twice / caps)."""
        context, state = self.world.context, self.world.state
        self.rounds += 1
        catalog = self.get_tools_for_orchestrator()
        response = self.engineer(system_prompt, context.compile_messages(), family='claude',
                                 tier='high', tools=catalog, max_tokens=4096)
        self._track_usage(response)
        text_parts = [block.text for block in response.content if block.type == 'text']
        tool_uses = [block for block in response.content if block.type == 'tool_use']
        text = '\n'.join(part for part in text_parts if part).strip()

        if not tool_uses:
            if text:
                self.wait_for_nlu('hook point 5')   # post-LLM, no tools ran
                note = self._read_nlu_entry()
                if note:
                    context.add_turn('agent', {'text': text, 'tool_uses': [],
                                               'tool_results': []}, turn_type='action')
                    context.add_turn('system', {'text': note})
                    return ''                       # PEX 5: one more round to decide
                state.keep_going = False            # terminal round — the turn is worded
                return text
            if self.nudged:  # thinking-only twice → forced wrap-up (T14)
                state.keep_going = False
                return self._final_emit(system_prompt)
            self.nudged = True
            context.add_turn('system', {'text': _NUDGE_MESSAGE})
            return ''

        valid = {tool['name'] for tool in catalog}
        blocks = [{'type': 'tool_use', 'id': tu.id, 'name': tu.name,
                   'input': dict(tu.input or {})} for tu in tool_uses]
        results = []
        for tool_use in tool_uses:
            try:
                result, self.last_call = self._guarded_call(tool_use, valid, self.last_call)
            except TimeoutError:      # a hook-wait expiry fails the turn loudly (round 3.4)
                raise
            except Exception as ecp:  # noqa: BLE001 — convert to a corrective tool error
                log.exception('tool call crashed: %s', ecp)
                result = corrective('server_error', f'{type(ecp).__name__}: {ecp}')
                self.last_call = None
            self.errors = self.errors + 1 if not result['_success'] else 0
            log.info('  orch round=%d tool=%s ok=%s', self.rounds, tool_use.name,
                     result['_success'])
            results.append({'type': 'tool_result', 'tool_use_id': tool_use.id,
                            'content': json.dumps(result, default=str)})
        context.add_turn('agent', {'text': text, 'tool_uses': blocks,
                                   'tool_results': results}, turn_type='action')
        done = sum(1 for flow in self.recently_finished if flow.status == 'Completed')
        if done > self.finished:      # a completed flow resets the round budget —
            self.finished = done      # every plan step starts fresh
            self.rounds = 0
        if self.rounds >= self.max_rounds or self.errors >= self.max_corrective:
            state.keep_going = False
            return self._final_emit(system_prompt)
        return ''                     # mid-turn round — no reply yet

    def wait_for_nlu(self, hook:str):
        """Block until NLU's thinking settles (the hook 1/3/5 waits). Expiry raises — the turn
        fails loudly into take_turn's safety net."""
        if not self.world.nlu_done.wait(timeout=30):
            raise TimeoutError(f'NLU still thinking after 30s at {hook}')

    def _final_emit(self, system_prompt:str) -> str:
        """The one forced-terminal path (T14): round budget, corrective cap, or a second
        thinking-only miss — one last no-tools call forces a plain-text wrap-up, so completed
        work still gets a real reply. The canned fallback survives only as this method's own
        last resort."""
        context = self.world.context
        context.add_turn('system', {'text': _WRAP_UP_MESSAGE})
        response = self.engineer(system_prompt, context.compile_messages(), family='claude',
                                 tier='high', max_tokens=1024)
        self._track_usage(response)
        text_parts = [block.text for block in response.content if block.type == 'text']
        return '\n'.join(part for part in text_parts if part).strip() or _FALLBACK_MESSAGE

    def _guarded_call(self, tool_use, valid:set, last_call) -> tuple[dict, tuple]:
        """Guardrails around one tool call: hallucinated names and identical consecutive calls
        return corrective errors instead of calling the tool. Everything else routes through
        `_tool`, which already converts bad args into corrective tool errors the model
        can retry on. These guards are the legitimate exception to the no-defensive-code rule —
        LLM output is unpredictable input.

        `last_call` is (name+args key, succeeded). Dedupe only fires when the previous identical
        call SUCCEEDED — retrying the same call after a transient tool error (server_error from
        an overloaded LLM, a flaky channel API) is legitimate recovery, not a loop. A
        manage_flows key also carries the live stack (2.14.2): NLU fills slots and stacks flows
        mid-loop, so an identical retry after the stack changed is a new call — e.g. pressing
        the run button again once the fill landed."""
        # hook: pre-tool
        call = (tool_use.name, json.dumps(dict(tool_use.input or {}), sort_keys=True, default=str))
        if tool_use.name == 'manage_flows':
            call += (json.dumps(self.flow_stack.to_list(), sort_keys=True, default=str),)
        if tool_use.name not in valid:
            result = corrective('invalid_input',
                f'Unknown tool: {tool_use.name!r}. Use a tool from your tool list.')
        elif last_call and call == last_call[0] and last_call[1]:
            result = corrective('duplicate_call', 'Identical consecutive tool call skipped — '
                                'change the arguments or respond to the user.')
        elif tool_use.name in READ_ONLY_DOMAIN_TOOLS and self._reads >= self.max_reads:
            result = corrective('read_cap', f'Already used {self.max_reads} read-only lookups '
                                'this turn. Stack on and activate a flow, or respond to the user.')
        else:
            result = self.call_tool(tool_use.name, dict(tool_use.input or {}))
            if tool_use.name in READ_ONLY_DOMAIN_TOOLS and result['_success']:
                self._reads += 1
        return result, (call, result['_success'])

    def _track_usage(self, response):
        """Record real prompt-token usage off an agent-loop API response (MEM's compaction
        trigger reads it, never estimates). Cache reads/writes count toward the window."""
        usage = response.usage
        if usage:
            self.last_prompt_tokens = (usage.input_tokens
                                       + (usage.cache_creation_input_tokens or 0)
                                       + (usage.cache_read_input_tokens or 0))

    # -- Tool calls -------------------------------------------------------

    def call_tool(self, tool_name:str, tool_input:dict) -> dict:
        """The uniform call surface — every tool call from both loops routes through here
        (call_mcp, the MCP sibling, is designed-not-built: no server is wired). Bad calls come
        back as corrective errors, never exceptions — except a hook-wait TimeoutError, which
        fails the whole turn loudly."""
        try:
            if tool_name in self.tools:
                service, method_name = self.tools[tool_name]
                method = getattr(service, method_name)
                return method(**tool_input)
            elif tool_name == 'declare_ambiguity':
                return self._declare_ambiguity(tool_input)
            elif tool_name == 'coordinate_context':
                return self._context_tool(tool_input)
            elif tool_name == 'read_scratchpad':
                return self._read_from_scratchpad(tool_input)
            elif tool_name == 'read_flow_stack':
                return self._read_flow_stack(tool_input)
            elif tool_name == 'stackon_flow':
                return self._stackon_flow(tool_input)
            elif tool_name == 'fallback_flow':
                return self._fallback_flow(tool_input)
            elif tool_name == 'save_findings':
                return self._save_findings_tool(tool_input)
            elif tool_name in self._orchestrator_toolset:
                return self._orchestrator_toolset[tool_name](tool_input)
            else:
                return corrective('invalid_input', f'Unknown tool: {tool_name}')
        except TimeoutError:          # a hook-wait expiry fails the turn loudly (round 3.4)
            raise
        except OutlineValidationError as ecp:
            return corrective('validation', str(ecp))
        except PostNotFoundError as ecp:
            return corrective('not_found', str(ecp))
        except Exception as ecp:
            return corrective('server_error', f'{type(ecp).__name__}: {ecp}')

    def _context_tool(self, params:dict) -> dict:
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
        return corrective('invalid_input', f'Unknown action: {action}')

    def _read_flow_stack(self, params:dict) -> dict:
        details = params.get('details', 'flows')
        if details == 'slots':
            return {'_success': True, 'slots': self.flow_stack.get_flow().slot_values_dict()}
        if details == 'flow_meta':
            return {'_success': True, 'flow': self.flow_stack.get_flow().to_dict()}
        if details == 'flows':
            return {'_success': True, 'flows': self.flow_stack.to_list()}
        return corrective('invalid_input',
                          f"details must be 'flows', 'slots', or 'flow_meta'; got {details!r}")

    def _stackon_flow(self, params:dict) -> dict:
        self.flow_stack.stackon(params['flow'])
        return {'_success': True, 'stacked': params['flow']}

    def _fallback_flow(self, params:dict) -> dict:
        self.flow_stack.fallback(params['flow'])
        return {'_success': True, 'fell_back_to': params['flow']}

    def _declare_ambiguity(self, params:dict) -> dict:
        level, metadata = params['level'], params['metadata']
        err = _validate_ambig_metadata(level, metadata)
        if err:
            log.info('[ambig-trace] declare_ambiguity REJECTED level=%s metadata=%s err=%s',
                     level, metadata, err)
            return corrective('invalid_input', err)
        self.world.ambiguity.recognize(level, metadata=metadata, observation=params.get('observation', ''))
        return {'_success': True}

    def _save_findings_tool(self, params:dict) -> dict:
        """Persist structured findings to the scratchpad under the active flow's name.

        Tool-call-shaped replacement for skills that would otherwise emit a JSON blob as their
        terminal text response. The policy reads the findings out of tool_log via
        `extract_tool_result`; downstream flows read them via
        `scratchpad.read(<flow_name>)`."""
        findings = params.get('findings', [])
        summary = params.get('summary', '')
        references_used = params.get('references_used', [])
        flow = self.flow_stack.get_flow()
        origin = flow.name() if flow else 'findings'
        self.session_scratchpad.append_entry(origin, {
            'version': 1,
            'turn_number': self.world.context.num_utterances,
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

    # -- Orchestrator hot-path tools --------------------------------------
    # Thin wiring onto the state, memory, and NLU surfaces. Errors raised below (bad
    # write_state op, unknown flow, grounding violation) are caught by _tool's
    # try/except and returned as corrective tool errors for the orchestrator loop to retry on.

    def read_state(self, params:dict) -> dict:
        # The ONE stack is pex.flow_stack — attached to the document at read time, never
        # stored on the DialogueState.
        document = self.world.state.read_state()
        document['flow_stack'] = self.flow_stack.to_list()
        return {'_success': True, 'state': document}

    def _manage_flows(self, params:dict) -> dict:
        """The orchestrator's one flow tool — ops [update, stackon, fallback, pop].
        `update` changes a flow's status/stage in place at any depth (flow_name targets a
        buried flow; blank means the top flow) and `pop` clears Completed and Invalid flows
        from the top of the stack down to the first Pending or Active flow. Policy execution
        is runtime-owned: stackon (active defaults true), fallback, and a pop that surfaces a
        Pending flow call execute() — the only call sites the sub-agent loop has. Belief,
        grounding, and slots stay NLU's job — no op here touches them (T18: Continue is a
        pure status write)."""
        params = {**params, 'op': {'update': 'update_flow'}.get(params['op'], params['op'])}
        state = self.world.state
        kwargs = dict(params.get('fields', {}))
        if 'flow_name' in params:
            kwargs['flow_name'] = params['flow_name']
        if 'slots' in kwargs:  # T18: slot writes left the tool — NLU owns slot filling
            return corrective('invalid_input', 'slots are not writable through manage_flows — '
                              'NLU fills slots; update takes status/stage only')
        if 'status' in kwargs:
            kwargs['status'] = kwargs['status'].capitalize()
        promoted = None
        match params['op']:
            case 'stackon':
                # No slot hand-over while an ambiguity is open — the incomplete flow's values
                # are exactly what is in question (planner spec scenario 15 discussion).
                self.flow_stack.stackon(kwargs['flow_name'],
                                        transfer=not self.world.ambiguity.is_present,
                                        active=params.get('active', True))
            case 'fallback':
                self.flow_stack.fallback(kwargs['flow_name'])
            case 'update_flow':
                self.flow_stack.update_flow(**kwargs)
            case 'pop':
                popped, promoted = self.flow_stack.pop()
                self.recently_finished += popped   # every pop lands here — Completed or Invalid
            case _:
                raise ValueError(f'Unknown manage_flows op: {params["op"]!r}')
        document = state.read_state()
        document['flow_stack'] = self.flow_stack.to_list()
        # Stack events that run the top policy: stackon (active defaults true — active=false
        # stacks a plan step as Pending), fallback, a status write of 'Active' through update
        # (the manual run button, planner spec scenario 20), and a pop that PROMOTED a Pending
        # flow (2.13.2 — the op name is not a run signal: a pop that removed nothing, emptied
        # the stack, or left an already-Active flow on top has no newly runnable work).
        run = (params['op'] == 'fallback'
               or (params['op'] == 'pop' and promoted is not None)
               or (params['op'] == 'stackon' and params.get('active', True))
               or (params['op'] == 'update_flow' and kwargs.get('status') == 'Active'))
        if run:
            # A pop-run names the promoted flow so a different Active entry can never be
            # selected accidentally (2.13.2) — NLU may stack over it in the same window.
            return self.execute(start=promoted)
        return {'_success': True, 'state': document}

    def execute(self, start=None) -> dict:
        """Run policy sub-agents until the stack settles — called ONLY from a manage_flows op
        that surfaced runnable work (the run branch), never from the Assistant. Each pass:
        ground → security → call_policy → verify (hook point 6) → the hook-3 read — NLU may
        have re-stacked mid-run. A completion ends the pass: the pop has cleared the
        Completed/Invalid flows and the result carries `popped` plus the surfaced `next_flow`
        — the agent judges what runs next, usually op='update' status='Active' (Unresolved
        1a, 2026-07-17). A same-intent new flow surfaces the announcement to the agent (PEX 5
        decides); a different-intent flow re-runs in code (the re-route; the agent is never
        notified). Re-running a flow within a turn is legal — the loop stops when the live
        flow stops changing, not on a ledger of what ran. `start` pins the first flow to run
        (a pop's promoted flow); later iterations re-derive the live flow as always. execute()
        writes no turns — its output travels as the manage_flows tool result."""
        state, context = self.world.state, self.world.context
        result = None
        curr_flow = start or self.flow_stack.get_flow()
        while curr_flow and curr_flow.status in ('Pending', 'Active'):
            if curr_flow.name() == 'plan':   # a surfaced Plan Flow never runs (TODO: review pass)
                curr_flow.status = 'Completed'
                popped, _ = self.flow_stack.pop()
                self.recently_finished += popped
                state.has_plan = False
                curr_flow = self.flow_stack.get_flow()
                continue

            # The per-flow body: ground once at the choke point (2.14.3) — ground_flow only
            # fills EMPTY entity slots, so a flow NLU already filled is untouched.
            curr_flow.status = 'Active'
            state.ground_flow(curr_flow)
            approval = self._security_check(curr_flow)   # hook: pre-flow
            if approval:
                return corrective('approval_required', approval.blocks[0].data['prompt'])
            artifact, entry = self.call_policy(curr_flow)
            self.world.insert_artifact(artifact)
            check = self.verify(artifact, curr_flow)     # hook point 6 closes every sub-agent run
            curr_flow.is_newborn = False  # verification counts as touched, whatever the outcome
            if not check.passed:
                curr_flow.is_uncertain = True  # the policy hit an issue; cleared on resolution
                if check.is_error_frame:
                    result = {**corrective('execution_error', artifact.data['violation']),
                              'thoughts': artifact.thoughts}
                else:
                    result = corrective('validation', check.reason)
            else:
                curr_flow.is_uncertain = self.world.ambiguity.is_present
                blocks = _block_summaries(artifact)
                if curr_flow.status != 'Completed':
                    question = (self.world.ambiguity.ask(curr_flow.name())
                                if self.world.ambiguity.is_present else '')
                    result = {'_success': True, 'status': curr_flow.status, 'question': question,
                              'thoughts': artifact.thoughts, 'blocks': blocks}
                else:
                    if entry is None:  # completed without complete_flow — synthesize an entry
                        summary = artifact.thoughts or f'{curr_flow.name()} completed'
                        entry = {'version': 1, 'turn_number': context.num_utterances,
                                 'used_count': 0, 'summary': summary,
                                 'metadata': artifact.data or {}}
                        self.session_scratchpad.append_entry(curr_flow.name(), entry)
                        entry = {**entry, 'origin': curr_flow.name()}
                    popped, _ = self.flow_stack.pop()  # Completed and Invalid leave together
                    next_flow = self.flow_stack.get_flow()
                    if next_flow and next_flow.name() == 'plan':
                        # The Plan Flow oversees, it does not do the work: the pop that
                        # surfaces it removes it. TODO(review pass, future round): run its
                        # policy here instead — review the steps' work via the scratchpad.
                        next_flow.status = 'Completed'
                        more, _ = self.flow_stack.pop()
                        popped += more
                        next_flow = self.flow_stack.get_flow()
                    self.recently_finished += popped   # every popped flow — either status
                    if state.has_plan and not self.flow_stack.find_by_name('plan'):
                        state.has_plan = False  # the marker anchors the flag — it left the stack
                    if next_flow and next_flow.status != 'Active':  # hook 6 shape check (Derek)
                        result = corrective('invalid_stack',
                            f'{next_flow.name()!r} surfaced with status {next_flow.status!r} '
                            f'after the pop — set it Active with manage_flows or pop it')
                    else:
                        result = {'_success': True, 'status': curr_flow.status,
                                  'completion': entry, 'blocks': blocks,
                                  'popped': [done.name() for done in popped]}
                        if next_flow:  # the surfaced flow is the agent's call (Unresolved 1a)
                            result['next_flow'] = {'name': next_flow.name(),
                                                   'status': next_flow.status}

            self.wait_for_nlu('hook point 3')            # the post-tool read
            if curr_flow.status == 'Completed':
                # The S3/S5 window: NLU stacked a flow while this one was mid-run and it
                # completed in the same pass. The announcement still surfaces at hook 3 —
                # the completion result carries it, so the agent decides WITH NLU's
                # rationale instead of seeing only next_flow.
                note = self._read_nlu_entry()
                if note:
                    result['nlu_update'] = note
                break   # popped in code; the agent judges what runs next
            prev_flow, curr_flow = curr_flow, self.flow_stack.get_flow()
            if not curr_flow or curr_flow.flow_id == prev_flow.flow_id:
                break   # nothing changed — the stall stands; return it to the agent
            if curr_flow.intent == prev_flow.intent:
                note = self._read_nlu_entry()                   # same intent → PEX 5 decides
                if note:
                    result['nlu_update'] = note
                break
            # different intent → code re-routes (3.4.1); the loop continues on curr_flow
        if result is not None:
            return result
        document = state.read_state()
        document['flow_stack'] = self.flow_stack.to_list()
        return {'_success': True, 'state': document}

    def call_policy(self, flow) -> tuple:
        """The code wrapper around one policy sub-agent run: lookup, run, pop_completion.
        Returns (artifact, completion entry) — the entry is None unless the policy completed
        via complete_flow. Sub-agents receive plain call_tool as their `tools`; the
        orchestrator guards stay in _guarded_call."""
        policy = self._policies[flow.intent]
        artifact = policy.execute(self.world.state, self.world.context, self.call_tool)
        return artifact, policy.pop_completion()

    def _read_nlu_entry(self) -> str | None:
        """The hook 3/5 read: surface THIS turn's unconsumed NLU announcement, if any. The
        scratchpad's read() flips `is_newborn` on what it returns — reading IS consuming — and
        the returned dicts keep the pre-flip value, so the filter below still works. Entries
        are scoped by turn_number >= the turn's opening turn_id (tool-log turns advance the
        counter mid-loop, so equality would miss the announcement). The note renders from the
        LIVE stack at read time (2.14.2) so it never names a dead flow, and carries NLU's
        rationale instead of a decline recipe — the decision is the agent's."""
        entries = self.session_scratchpad.read(origin='nlu', keys=['new_flow'])
        entry = next((entry for entry in reversed(entries) if entry.get('is_newborn')
                      and entry['turn_number'] >= self._turn_start), None)
        if entry is None:
            return None
        stack = ' | '.join(f"{item['flow_name']}·{item['status']}"
                           for item in reversed(self.flow_stack.to_list()))
        note = f"[nlu] {entry['summary']}."
        if entry.get('rationale'):
            note += f" Rationale: {entry['rationale']}."
        return (f"{note} Live stack (top first): {stack}. Decide with manage_flows against "
                f"this stack — the flow NLU stacked carries the user's newest message, so it "
                f"usually wins.")

    def _understand_user(self, params:dict) -> dict:
        """The orchestrator's belief READ, plus the contemplate re-route request (3.4.7). Both
        ops wait on NLU settling — the same wait prepare owns at hook point 1. PEX never
        invokes the NLU module: on op='contemplate' the request is queued on the scratchpad
        for the Assistant, which calls nlu.contemplate() after this pass ends and re-enters
        the loop."""
        self.wait_for_nlu('understand')
        if params['op'] == 'contemplate':
            self.session_scratchpad.append_entry('orchestrator', {'version': 1,
                'turn_number': self.world.context.num_utterances, 'used_count': 0,
                'request': 'contemplate', 'summary': 'policy could not proceed — asking NLU to re-route'})
            return {'_success': True, '_message': 'Re-route queued. End your reply this round; '
                                                 'the re-detected flow runs on the next pass.'}
        return self.read_state(params)

    def _read_from_scratchpad(self, params:dict) -> dict:
        entries = self.session_scratchpad.read(origin=params.get('origin'), keys=params.get('keys'))
        return {'_success': True, 'entries': entries}

    def _append_scratchpad(self, params:dict) -> dict:
        if 'origin' not in params['entry']:
            return corrective('invalid_input', "entry needs a stable 'origin' to file it under.")
        # LLM-authored entry — code stamps the contract fields it can't be trusted with.
        entry = {'version': 1, **params['entry'],
                 'turn_number': self.world.context.num_utterances, 'used_count': 0}
        self.session_scratchpad.append_entry(entry.pop('origin'), entry)
        return {'_success': True, 'size': self.session_scratchpad.size}

    def _store_preference(self, params:dict) -> dict:
        """Persist a durable user preference to L2."""
        self.world.prefs.store_preference(params['key'], params['value'])
        return {'_success': True, 'key': params['key']}

    def _ask_clarification(self, params:dict) -> dict:
        """Generate the level-specific clarification question for the pending ambiguity — NLU
        authors it (wider view of the session than the orchestrator)."""
        if self.world.ambiguity.is_present:
            flow = self.flow_stack.get_flow()
            return {'_success': True, 'question': self.world.ambiguity.ask(flow.name() if flow else '')}
        return corrective('invalid_input', 'No pending ambiguity to ask about.')

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
                'name': 'declare_ambiguity',
                'description': (
                    "Raise an ambiguity flag back to the user when a slot is missing, an entity "
                    "can't be resolved, or something needs confirming and you truly cannot "
                    "proceed.\n\n"
                    "Per-level metadata shape (validated at call time — wrong shape returns invalid_input):\n"
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
                        'level':       {'type': 'string', 'enum': ['general', 'partial', 'specific', 'confirmation']},
                        'metadata':    {'type': 'object', 'description': 'shape required per level — see description'},
                        'observation': {'type': 'string', 'description': 'agent-authored clarification utterance (general/partial/specific only)'},
                    },
                    'required': ['level', 'metadata'],
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
                'name': 'read_scratchpad',
                'description': (
                    "Read session scratchpad entries, newest last. Optional filters: `origin` "
                    "(a flow name, 'orchestrator', or a topic like 'recovery') and `keys` (only "
                    "entries carrying every named key — e.g. ['summary', 'metadata'] selects "
                    "completion entries). Pick up prerequisites left by earlier flows here."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'origin': {'type': 'string'},
                        'keys': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': [],
                },
            },
            {
                'name': 'read_flow_stack',
                'description': (
                    "Inspect the flow stack. `details` picks what to read: "
                    "'flows' (the full stack of Pending and Active flows, the default), "
                    "'slots' (the active flow's filled slot values), "
                    "or 'flow_meta' (the active flow's class-level metadata)."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'details': {'type': 'string', 'enum': ['flows', 'slots', 'flow_meta']},
                    },
                    'required': [],
                },
            },
            {
                'name': 'stackon_flow',
                'description': (
                    "Push a prerequisite flow onto the stack — the current flow needs another "
                    "flow's output first. `flow` is the flow name to push."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {'flow': {'type': 'string'}},
                    'required': ['flow'],
                },
            },
            {
                'name': 'fallback_flow',
                'description': (
                    "Hand off to a sibling flow when the request belongs there — replaces the "
                    "current flow, transferring matching slot values. `flow` is the target flow name."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {'flow': {'type': 'string'}},
                    'required': ['flow'],
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
                    "user-intent ambiguity, use declare_ambiguity instead."
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
        """The orchestrator's tool list: hot-path dedicated tools, the borrowed component tools
        it shares with sub-agents (coordinate_context, read_scratchpad), and the read-only domain
        allowlist. The flow-stack tools are deliberately absent — their job lives in
        understand/manage_flows."""
        tools = self._orchestrator_tool_definitions()
        component = {tool['name']: tool for tool in self._component_tool_definitions()}
        tools += [component[name] for name in ('coordinate_context', 'read_scratchpad')]
        for tool_name in READ_ONLY_DOMAIN_TOOLS:
            tool_def = self._get_tool_def(tool_name)
            if tool_def:
                tools.append(tool_def)
        return tools

    def _orchestrator_tool_definitions(self) -> list[dict]:
        return [
            {
                'name': 'manage_flows',
                'description': (
                    "Possible Ops:\n"
                    "- `update`   — change a flow in place. `fields` may carry `stage` and "
                    "`status` (never slots — NLU fills slots). "
                    "Targets the top flow by default; pass `flow_name` to reach a buried flow "
                    "(e.g. cancelling a whole stack by marking each flow Invalid). Setting "
                    "`status: 'Active'` re-runs the flow's policy — this is how you CONTINUE the "
                    "Active flow after the user answers its question, and how you run a "
                    "surfaced `next_flow` after a completion.\n"
                    "- `stackon`  — push `flow_name` on top of the stack and run its policy "
                    "(`active` defaults to true; the flow beneath reverts to Pending and resumes "
                    "later). Matching slot values hand over from the prior flow automatically. "
                    "Pass `active: false` to stack a plan step as Pending WITHOUT running it — "
                    "stack a plan in reverse execution order with active=false, then push the "
                    "first step plain.\n"
                    "- `fallback` — replace the top flow with `flow_name`, transferring matching "
                    "slot values; the replacement policy runs immediately.\n"
                    "- `pop`      — clear Completed and Invalid flows from the top of the stack down "
                    "to the first Pending or Active flow. A surfaced Pending flow is promoted to "
                    "Active and its policy runs; a pop that removes nothing or leaves an "
                    "already-Active flow on top runs nothing and returns the state.\n"
                    "There is no `activate` op — stackon/fallback and a promoting pop run the top "
                    "policy themselves; inspect the returned policy result."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {
                        'op': {'type': 'string',
                               'enum': ['update', 'stackon', 'fallback', 'pop']},
                        'flow_name': {'type': 'string',
                                      'description': 'for stackon / fallback — the target flow; for update — optional deep target (defaults to the top flow)'},
                        'fields': {'type': 'object',
                                   'description': 'for update — the flow fields to set (stage / status)'},
                        'active': {'type': 'boolean',
                                   'description': 'for stackon — defaults true (push and run); false stacks a plan step as Pending without running it'},
                    },
                    'required': ['op'],
                },
            },
            {
                'name': 'understand',
                'description': (
                    "Your belief READ. op='read' returns the session's DialogueState: user "
                    "beliefs (intent, goal, confirmed/rejected, workflow_step), the grounding "
                    "block (the active post/sec/snip/chl entity), the flow stack, and flags — "
                    "cheap, call it whenever you need current state rather than guessing. An "
                    "incomplete flow returns a clarification `question` you can relay. "
                    "op='contemplate' queues a re-route request after a policy stalls: "
                    "NLU re-detects over the failed flow and stacks the replacement — end your "
                    "reply this round; the re-detected flow runs on the next pass."
                ),
                'input_schema': {
                    'type': 'object',
                    'properties': {'op': {'type': 'string', 'enum': ['read', 'contemplate']}},
                    'required': ['op'],
                },
            },
            {
                'name': 'append_to_scratchpad',
                'description': (
                    "Append one agent-belief entry to the session scratchpad (JSONL). `entry` is a "
                    "schema-free JSON object — intermediate findings, tool results worth keeping, "
                    "working notes — plus a stable `origin` (what the note is about) to file it "
                    "under. Reads go through the read_scratchpad tool."
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
                'name': 'ask_clarification_question',
                'description': (
                    "Turn the pending ambiguity into a clarification question for the user. NLU "
                    "authors it (wider view of the scratchpad, belief state, and other ambiguities "
                    "than you have), so rely on this rather than writing your own. No arguments — "
                    "returns `question`. Errors if no ambiguity is pending."
                ),
                'input_schema': {'type': 'object', 'properties': {}, 'required': []},
            },
        ]




# Module alias — the module is PEX; the class name spells it out.
PEX = PolicyExecutor
