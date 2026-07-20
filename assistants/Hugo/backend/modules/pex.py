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

        self.domain_tools: dict[str, tuple[object, str]] = {
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
        # Component tool inventory (round 5.2) — one dict, one naming rule: method = '_' +
        # exposed tool name. Which CALLERS see which tools (and which ops) lives in the
        # definitions, never here.
        self.component_tools = {
            'manage_flows':         self._manage_flows,
            'understand':           self._understand,
            'view_policies':        self._view_policies,
            'scratchpad':           self._scratchpad,
            'declare_ambiguity':    self._declare_ambiguity,
            'execution_error':      self._execution_error,
            'coordinate_context':   self._coordinate_context,
            'store_preference':     self._store_preference,
        }
        self._policies: dict[str, object] = {}  # built when the world is attached (setter below)
        for stale in self._content_service._snap_root.glob('snap_*.json'):   # wipe prior sessions
            stale.unlink()

    @property
    def world(self):
        return self._world

    @world.setter
    def world(self, world):
        """Assigning the world finishes the wiring: the one domain tool that reads a MEM
        component, and the policies (their scoped components dict carries world-bound references —
        sub-agents never see the whole world)."""
        self._world = world
        self.domain_tools['search_documents'] = (world.knowledge, 'search_documents')
        components = {'engineer': self.engineer, 'config': self.config, 'ambiguity': world.ambiguity,
            'get_tools': self.get_tools_for_flow, 'flow_stack': self.flow_stack,
            'content_service': self._content_service, 'scratchpad': self.session_scratchpad,
        }
        self._policies = {
            'Converse': ConversePolicy(components),
            'Research': ResearchPolicy(components),
            'Draft': DraftPolicy(components),
            'Revise': RevisePolicy(components),
            'Publish': PublishPolicy(components),
        }

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
        return ArtifactCheck(passed=True)

    @staticmethod
    def _merge_block_data(artifact):
        merged = {}
        block_types = []
        for block in artifact.blocks:
            merged.update(block.data)
            block_types.append(block.block_type)
        return merged, block_types

    # -- The PEX Agent: prepare() + one round per orchestrate() call ------

    def prepare(self):
        """Hook point 1 — PEX's first step, called by take_turn before the round loop. Per-turn
        resets, the Plan/Clarify gate (the only intents that wait on NLU's settled thinking),
        then the prediction note: one system utterance handing round 1 the belief every
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
        context = self.world.context
        user_turn = next(turn for turn in reversed(context.full_conversation(as_turns=True))
                         if turn.role == 'user')
        if user_turn.turn_type == 'action':   # golden dax — react() already stacked it; force it
            note = (f"[click] The user selected '{state.pred_flows[0]['name']}' directly. You "
                    f"MUST run it as your next step with manage_flows (update status='Active').")
        elif state.pred_flows:                # TypeSafe — a prediction the agent may override
            note = (f"[typesafe] intent={state.pred_intent} — the predicted flow is "
                    f"'{state.pred_flows[0]['name']}'. Stack and run it with manage_flows "
                    f"(op='stackon'), pick a different flow, or reply directly.")
        else:  # NLU abstained after the wait — embed the pending question directly (5.2.3)
            question = (self.world.ambiguity.ask('') if self.world.ambiguity.is_present else '')
            asked = (f'A clarification is pending — relay it in your own voice: "{question}" '
                     if question else '')
            note = (f"[typesafe] intent={state.pred_intent} — no flow was detected. {asked}"
                    f"Pick a flow yourself if the request is actually clear.")
        context.add_turn('system', {'text': note})   # system utterance — round 1 sees it

    def orchestrate(self, system_prompt) -> str:
        """One PEX-Agent round — the while-loop lives in take_turn (`state.keep_going`).
        Returns '' on mid-turn rounds and the reply text on the terminal round; the reply is
        PEX's return value, nothing else carries it. Tool calls route through _guarded_call →
        call_tool; NLU's mid-turn stack changes surface at the hook 3/5 reads. Two exits end
        the turn: the terminal no-tool text, or _final_emit() (nudged twice / caps)."""
        context, state = self.world.context, self.world.state
        self.rounds += 1
        catalog = self.get_tools_for_orchestrator()
        messages = context.compile_messages()
        messages.append({'role': 'user', 'content': self.refresh()})   # 5.2.5, ephemeral
        response = self.engineer(system_prompt, messages, family='claude',
                                 tier='high', tools=catalog, max_tokens=4096)
        self._track_usage(response)
        text_parts = [block.text for block in response.content if block.type == 'text']
        tool_uses = [block for block in response.content if block.type == 'tool_use']
        text = '\n'.join(part for part in text_parts if part).strip()

        if not tool_uses:
            if text:
                self.wait_for_nlu('hook point 5')   # post-LLM, no tools ran
                # PEX 5: an unseen 'new_flow' NLU stacked THIS turn earns one more round to decide
                # (ending on a fresh Pending top would strand it); the next refresh renders it.
                fresh = self.session_scratchpad.read(origin='nlu', keys=['new_flow'], consume=False)
                if any(e['used_count'] == 0 and e['turn_number'] >= self._turn_start for e in fresh):
                    context.add_turn('agent', {'text': text, 'tool_uses': [],
                                               'tool_results': []}, turn_type='action')
                    return ''                       # renders NLU's announcement
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
            if tool_name in self.domain_tools:
                service, method_name = self.domain_tools[tool_name]
                method = getattr(service, method_name)
                return method(**tool_input)
            elif tool_name in self.component_tools:
                return self.component_tools[tool_name](tool_input)
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

    def _coordinate_context(self, params:dict) -> dict:
        op = params.get('op', '')
        if op == 'get_history':
            turns = params.get('turns', 3)
            history = self.world.context.compile_history(look_back=turns)
            return {'_success': True, 'history': history}
        elif op == 'get_turn':
            turn_id = params.get('turn_id', 0)
            turn = self.world.context.get_turn(int(turn_id))
            return {'_success': True, 'turn': turn.utt(as_dict=True) if turn else None}
        elif op == 'get_checkpoint':
            label = params.get('label', '')
            cp = self.world.context.get_checkpoint(label)
            return {'_success': True, 'checkpoint': cp}
        return corrective('invalid_input', f'Unknown op: {op}')

    def _view_policies(self, params:dict) -> dict:
        """The sub-agent belief read (5.2.4) — flat, no arguments: the live stack plus the
        active flow's filled slot values."""
        flow = self.flow_stack.get_flow()
        return {'_success': True, 'flows': self.flow_stack.to_list(),
                'slots': flow.slot_values_dict() if flow else {}}

    def _execution_error(self, params:dict) -> dict:
        """Acknowledge a sub-agent's violation signal (5.2.3) — call_policy reads the traced
        call afterwards and stamps the artifact, routing it to the error path."""
        return {'_success': True, '_message': 'Violation recorded — wrap up your run.'}

    def _declare_ambiguity(self, params:dict) -> dict:
        level, metadata = params['level'], params['metadata']
        err = _validate_ambig_metadata(level, metadata)
        if err:
            log.info('[ambig-trace] declare_ambiguity REJECTED level=%s metadata=%s err=%s',
                     level, metadata, err)
            return corrective('invalid_input', err)
        self.world.ambiguity.recognize(level, metadata=metadata, observation=params.get('observation', ''))
        return {'_success': True}

    # -- Orchestrator hot-path tools --------------------------------------
    # Thin wiring onto the state, memory, and NLU surfaces. Errors raised below (bad
    # write_state op, unknown flow, grounding violation) are caught by call_tool's
    # try/except and returned as corrective tool errors for the orchestrator loop to retry on.

    def _manage_flows(self, params:dict) -> dict:
        """The ONE flow tool at both levels (5.2.1) — ops [update, stackon, fallback, pop].
        `update` changes a flow's status/stage in place at any depth (flow_name targets a
        buried flow; blank means the top flow) and `pop` clears Completed and Invalid flows
        from the top of the stack down to the first Pending or Active flow. Policy execution
        is runtime-owned: stackon (active defaults true), fallback, and a pop that surfaces a
        Pending flow call execute() — unless the call came from inside a policy run:
        call_policy injects `defer`, the sub-agent menu is stackon/fallback only, and the
        flow re-surfaces at the PEX layer instead of running inline (no fourth level).
        Belief, grounding, and slots stay NLU's job — no op here touches them (T18: Continue
        is a pure status write)."""
        defer = params.get('defer', False)
        params = {**params, 'op': {'update': 'update_flow'}.get(params['op'], params['op'])}
        if defer and params['op'] not in ('stackon', 'fallback'):
            return corrective('invalid_input', 'sub-agents may only stackon or fallback — '
                              'update and pop belong to the PEX layer')
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
        # Stack events that run the top policy: stackon (active defaults true — active=false
        # stacks a plan step as Pending), fallback, a status write of 'Active' through update
        # (the manual run button, planner spec scenario 20), and a pop that PROMOTED a Pending
        # flow (2.13.2 — the op name is not a run signal: a pop that removed nothing, emptied
        # the stack, or left an already-Active flow on top has no newly runnable work).
        run = (params['op'] == 'fallback'
               or (params['op'] == 'pop' and promoted is not None)
               or (params['op'] == 'stackon' and params.get('active', True))
               or (params['op'] == 'update_flow' and kwargs.get('status') == 'Active'))
        # From inside a policy run (5.2.1): the flow is on the stack now; it re-surfaces at the
        # PEX layer and the agent runs it on a later round — no inline execute() (no fourth level).
        if run and not defer:
            # A pop-run names the promoted flow so a different Active entry can never be
            # selected accidentally (2.13.2) — NLU may stack over it in the same window.
            return self.execute(start=promoted)
        return {'_success': True, '_error': ''}

    def execute(self, start=None) -> dict:
        """Run policy sub-agents until the stack settles — called ONLY from a manage_flows op
        that surfaced runnable work (the run branch), never from the Assistant. Each pass:
        ground → security → call_policy → verify (hook point 6) → the hook-3 read — NLU may
        have re-stacked mid-run. A completion ends the pass: the pop clears the Completed/Invalid
        flows in code and the surfaced next flow shows up in the round refresh (5.2.5) — the
        agent judges what runs next, usually op='update' status='Active'. A same-intent new flow
        ends the pass so the refresh surfaces the announcement (the agent decides); a
        different-intent flow re-runs in code (the re-route; the agent is never notified).
        Re-running a flow within a turn is legal — the loop stops when the live flow stops
        changing, not on a ledger of what ran. `start` pins the first flow to run (a pop's
        promoted flow); later iterations re-derive the live flow as always. Every exit returns
        the one three-key shape (5.2.5): `{_success, _error, artifact}` — the full artifact went
        to the World for display; the agent sees the compact projection."""
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
                self.world.artifacts.append(approval)
                return self._result(approval, error='approval_required')
            artifact, entry = self.call_policy(curr_flow)
            self.world.artifacts.append(artifact)
            check = self.verify(artifact, curr_flow)     # hook point 6 closes every sub-agent run
            curr_flow.is_newborn = False  # verification counts as touched, whatever the outcome
            if not check.passed:
                curr_flow.is_uncertain = True  # the policy hit an issue; cleared on resolution
                error = artifact.data['violation'] if check.is_error_frame else 'validation'
                result = self._result(artifact, error=error, note=check.reason)
            else:
                curr_flow.is_uncertain = self.world.ambiguity.is_present
                result = self._result(artifact)
                if curr_flow.status == 'Completed':
                    self._complete_pop(curr_flow, artifact, entry, context)

            self.wait_for_nlu('hook point 3')            # the post-tool read
            if curr_flow.status == 'Completed':
                break   # popped in code; the refresh surfaces the next flow, the agent decides
            prev_flow, curr_flow = curr_flow, self.flow_stack.get_flow()
            if not curr_flow or curr_flow.flow_id == prev_flow.flow_id:
                break   # nothing changed — the stall stands; return it to the agent
            if curr_flow.intent == prev_flow.intent:
                break   # same intent → the refresh surfaces NLU's announcement, the agent decides
            # different intent → code re-routes (3.4.1); the loop continues on curr_flow
        if result is not None:
            return result
        return {'_success': True, '_error': ''}          # a run that surfaced nothing new

    def _complete_pop(self, flow, artifact, entry, context):
        """The code-owned completion pop: a completed flow (and any Completed/Invalid flows
        under it) leaves the stack, and a surfaced plan marker is removed. Writes a synthesized
        completion entry when the policy completed without complete_flow, so the round refresh
        always has a summary to surface."""
        if entry is None:  # completed without complete_flow — synthesize an entry
            summary = artifact.thoughts or f'{flow.name()} completed'
            self.session_scratchpad.append_entry(flow.name(),
                {'turn_number': context.num_utterances, 'summary': summary,
                 'metadata': artifact.data or {}})
        popped, _ = self.flow_stack.pop()  # Completed and Invalid leave together
        next_flow = self.flow_stack.get_flow()
        if next_flow and next_flow.name() == 'plan':
            # The Plan Flow oversees, it does not do the work: the pop that surfaces it removes
            # it. TODO(review pass, future round): run its policy here — review via the scratchpad.
            next_flow.status = 'Completed'
            more, _ = self.flow_stack.pop()
            popped += more
        self.recently_finished += popped   # every popped flow — either status
        if self.world.state.has_plan and not self.flow_stack.find_by_name('plan'):
            self.world.state.has_plan = False  # the marker anchors the flag — it left the stack

    def _result(self, artifact, error:str='', note:str='') -> dict:
        """The one policy-run result shape (5.2.5): `{_success, _error, artifact}`. The artifact
        is a compact projection — origin, the sub-agent's thoughts, the block summaries, and the
        violation when the artifact carries one; `note` fills thoughts when the artifact has none
        (a validation reason, the approval prompt)."""
        view = {'origin': artifact.origin, 'thoughts': artifact.thoughts or note,
                'blocks': _block_summaries(artifact)}
        if 'violation' in artifact.data:
            view['violation'] = artifact.data['violation']
        return {'_success': not error, '_error': error, 'artifact': view}

    def call_policy(self, flow) -> tuple:
        """The code wrapper around one policy sub-agent run: lookup, run, pop_completion.
        Returns (artifact, completion entry) — the entry is None unless the policy completed
        via complete_flow. Sub-agents receive call_tool as their `tools` (traced below); the
        orchestrator guards stay in _guarded_call. Every run appends its trajectory to the
        session's subagents.jsonl — the sub-agent level of the observability traces."""
        policy = self._policies[flow.intent]
        calls = []

        def traced_tool(name, params):
            # A sub-agent's manage_flows defers (5.2.1): the flow lands on the stack and
            # re-surfaces at the PEX layer — never an inline run from inside a policy run.
            call_params = {**params, 'defer': True} if name == 'manage_flows' else params
            result = self.call_tool(name, call_params)
            calls.append({'tool': name, 'input': params, '_success': result['_success'],
                          '_error': result.get('_error', '')})
            return result

        artifact = policy.execute(self.world.state, self.world.context, traced_tool)
        # Wire the violation signal (5.2.3): a successful execution_error call stamps the
        # artifact so verify() routes it to the error path — one site, no per-policy edits.
        for call in calls:
            if call['tool'] == 'execution_error' and call['_success'] and 'violation' not in artifact.data:
                artifact.update_data(violation=call['input']['violation'])
                if not artifact.thoughts:
                    artifact.thoughts = call['input'].get('message', '')
                break
        record = {'turn_number': self.world.context.num_utterances, 'flow': flow.name(),
                  'status': flow.status, 'calls': calls, 'thoughts': artifact.thoughts}
        with open(self.world.session_dir() / 'subagents.jsonl', 'a', encoding='utf-8') as file:
            file.write(json.dumps(record, default=str) + '\n')
        return artifact, policy.pop_completion()

    def refresh(self) -> str:
        """The round refresh (5.2.5): the ephemeral message prepended to each PEX-Agent round,
        carrying (a) the live stack, top first; (b) a one-line digest of every scratchpad entry
        not yet seen (`used_count == 0`) — NLU announcements, completions, findings; (c) the
        pending clarification question. `used_count` is the seen-cursor: read() bumps it as the
        digests render, so each entry surfaces exactly once. Not persisted — only the current
        round's delta reaches the model, replacing the old per-hook nlu-note read; the agent
        queries nothing, the unseen work is pushed to it."""
        stack = ' | '.join(f"{item['flow_name']}·{item['status']}"
                           for item in reversed(self.flow_stack.to_list())) or '(empty)'
        lines = [f"[state] Live stack (top first): {stack}."]
        for entry in self.session_scratchpad.read():          # read bumps used_count → seen
            if entry['used_count'] != 0 or not entry.get('summary'):
                continue
            rationale = f" — {entry['rationale']}" if entry.get('rationale') else ''
            lines.append(f"- [{entry['origin']}] {entry['summary']}{rationale}")
        if self.world.ambiguity.is_present:
            question = self.world.ambiguity.ask(self.flow_stack.get_flow().name()
                                                if self.flow_stack.get_flow() else '')
            lines.append(f'[clarify] A question is pending — relay it in your own voice: "{question}"')
        return '\n'.join(lines)

    def _understand(self, params:dict) -> dict:
        """The PEX Agent's belief READ, plus the contemplate re-route request (3.4.7). Both ops
        wait on NLU settling — the same wait prepare owns at hook point 1. PEX never invokes the
        NLU module: on op='contemplate' the request is queued on the scratchpad for the
        Assistant, which calls nlu.contemplate() after this pass ends and re-enters the loop."""
        self.wait_for_nlu('understand')
        if params['op'] == 'contemplate':
            # used_count is the consumed marker — contemplation_requested's read bumps it, so
            # each re-route request fires exactly once (C5).
            self.session_scratchpad.append_entry('orchestrator',
                {'turn_number': self.world.context.num_utterances, 'request': 'contemplate',
                 'summary': 'policy could not proceed — asking NLU to re-route'})
            return {'_success': True, '_message': 'Re-route queued. End your reply this round; '
                                                 'the re-detected flow runs on the next pass.'}
        # The assembled belief view (5.2.4): the Dialogue State document with PEX's live FlowStack
        # attached — sibling components, the stack never stored on the state (state.json carries a
        # serialized copy only at save time).
        document = self.world.state.read_state()
        document['flow_stack'] = self.flow_stack.to_list()
        return {'_success': True, 'state': document}

    def _scratchpad(self, params:dict) -> dict:
        """The one scratchpad tool at both levels (5.2.2) — op='read' filters by origin/keys,
        op='append' files one entry. A sub-agent append that names no origin files under the
        active flow (the auto-origin save_findings used to provide). append_entry stamps the
        contract fields (version, used_count); turn_number is the caller's."""
        op = params['op']
        if op == 'read':
            entries = self.session_scratchpad.read(origin=params.get('origin'),
                                                   keys=params.get('keys'))
            return {'_success': True, 'entries': entries}
        if op == 'append':
            entry = dict(params['entry'])
            active = self.flow_stack.get_flow()
            origin = entry.pop('origin', None) or (active.name() if active else 'orchestrator')
            entry['turn_number'] = self.world.context.num_utterances
            self.session_scratchpad.append_entry(origin, entry)
            return {'_success': True, 'size': self.session_scratchpad.size}
        return corrective('invalid_input', f"scratchpad op must be 'read' or 'append'; got {op!r}")

    def _store_preference(self, params:dict) -> dict:
        """Persist a durable user preference to L2."""
        self.world.prefs.store_preference(params['key'], params['value'])
        return {'_success': True, 'key': params['key']}

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
        """The sub-agent's tool list (5.2): the shared component tools shaped for a policy run —
        manage_flows limited to stackon/fallback (update/pop belong to the PEX layer), the flat
        belief read (view_policies), scratchpad, declare_ambiguity, execution_error,
        coordinate_context — plus the flow's own domain tools."""
        tools = [self._def_manage_flows(sub_agent=True), self._def_view_policies(),
                 self._def_scratchpad(), self._def_declare_ambiguity(),
                 self._def_execution_error(), self._def_coordinate_context()]
        for tool_name in flow.tools:
            tool_def = self._get_tool_def(tool_name)
            if tool_def:
                tools.append(tool_def)
        return tools

    def get_tools_for_orchestrator(self) -> list[dict]:
        """The PEX Agent's tool list (5.2): manage_flows (all four ops), the belief read
        (understand), the shared scratchpad and coordinate_context, store_preference, and the
        read-only domain allowlist. The flat sub-agent reads (view_policies) and the sub-agent
        signals (declare_ambiguity, execution_error) are deliberately absent."""
        tools = [self._def_manage_flows(), self._def_understand(), self._def_scratchpad(),
                 self._def_coordinate_context(), self._def_store_preference()]
        for tool_name in READ_ONLY_DOMAIN_TOOLS:
            tool_def = self._get_tool_def(tool_name)
            if tool_def:
                tools.append(tool_def)
        return tools

    # -- Tool definition builders (one per tool; menus shaped per audience) -----

    def _def_manage_flows(self, sub_agent:bool=False) -> dict:
        if sub_agent:
            desc = (
                "Manage the flow stack from inside a policy run. TWO ops:\n"
                "- `stackon`  — push `flow_name` on top: the current flow needs another flow's "
                "output first. Matching slot values hand over automatically.\n"
                "- `fallback` — replace the current flow with `flow_name` when the request "
                "belongs there, transferring matching slot values.\n"
                "The pushed/replaced flow does NOT run inline — it lands on the stack and the PEX "
                "layer runs it on a later round. Emit your terminal JSON as usual; the stack "
                "change takes effect after your run."
            )
            enum = ['stackon', 'fallback']
            props = {'op': {'type': 'string', 'enum': enum},
                     'flow_name': {'type': 'string', 'description': 'the target flow to stack or fall back to'}}
        else:
            desc = (
                "Possible Ops:\n"
                "- `update`   — change a flow in place. `fields` may carry `stage` and "
                "`status` (never slots — NLU fills slots). "
                "Targets the top flow by default; pass `flow_name` to reach a buried flow "
                "(e.g. cancelling a whole stack by marking each flow Invalid). Setting "
                "`status: 'Active'` re-runs the flow's policy — this is how you CONTINUE the "
                "Active flow after the user answers its question, and how you run a flow that "
                "surfaced after a completion.\n"
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
                "already-Active flow on top runs nothing.\n"
                "There is no `activate` op — stackon/fallback and a promoting pop run the top "
                "policy themselves; the returned artifact is the policy result. A completed flow "
                "leaves the stack in code; the surfaced next flow and every completion appear in "
                "the next round's [state] refresh."
            )
            props = {
                'op': {'type': 'string', 'enum': ['update', 'stackon', 'fallback', 'pop']},
                'flow_name': {'type': 'string',
                              'description': 'for stackon / fallback — the target flow; for update — optional deep target (defaults to the top flow)'},
                'fields': {'type': 'object',
                           'description': 'for update — the flow fields to set (stage / status)'},
                'active': {'type': 'boolean',
                           'description': 'for stackon — defaults true (push and run); false stacks a plan step as Pending without running it'},
            }
        return {'name': 'manage_flows', 'description': desc,
                'input_schema': {'type': 'object', 'properties': props, 'required': ['op']}}

    def _def_understand(self) -> dict:
        return {
            'name': 'understand',
            'description': (
                "Your belief READ. op='read' returns the session's DialogueState: user "
                "beliefs (intent, goal, confirmed/rejected, workflow_step), the grounding "
                "block (the active post/sec/snip/chl entity), the flow stack, and flags — "
                "cheap, call it whenever you need current state rather than guessing. "
                "op='contemplate' queues a re-route request after a policy stalls: "
                "NLU re-detects over the failed flow and stacks the replacement — end your "
                "reply this round; the re-detected flow runs on the next pass."
            ),
            'input_schema': {
                'type': 'object',
                'properties': {'op': {'type': 'string', 'enum': ['read', 'contemplate']}},
                'required': ['op'],
            },
        }

    def _def_view_policies(self) -> dict:
        return {
            'name': 'view_policies',
            'description': (
                "Inspect the flow stack from inside a policy run — no arguments. Returns the "
                "live stack (every Pending and Active flow, top first) and the active flow's "
                "filled slot values. Use it to see what runs after you, or to confirm a slot "
                "value the resolved-entities block doesn't already carry."
            ),
            'input_schema': {'type': 'object', 'properties': {}, 'required': []},
        }

    def _def_scratchpad(self) -> dict:
        return {
            'name': 'scratchpad',
            'description': (
                "The session scratchpad — the cross-flow working ledger. TWO ops:\n"
                "- `read`   — entries newest last. Optional filters: `origin` (a flow name, "
                "'orchestrator', or a topic like 'recovery') and `keys` (only entries carrying "
                "every named key — e.g. ['summary', 'metadata'] selects completion entries). "
                "Pick up prerequisites left by earlier flows here.\n"
                "- `append` — file one entry: a schema-free `entry` object (findings, results "
                "worth keeping, working notes). Give it a stable `origin` to file it under; "
                "without one it files under the active flow. Code stamps the contract fields."
            ),
            'input_schema': {
                'type': 'object',
                'properties': {
                    'op': {'type': 'string', 'enum': ['read', 'append']},
                    'origin': {'type': 'string', 'description': 'read filter, or the append file'},
                    'keys': {'type': 'array', 'items': {'type': 'string'}, 'description': 'read filter'},
                    'entry': {'type': 'object', 'description': 'for append — the entry payload'},
                },
                'required': ['op'],
            },
        }

    def _def_declare_ambiguity(self) -> dict:
        return {
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
                "— those route through `execution_error`, not the user."
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
        }

    def _def_execution_error(self) -> dict:
        return {
            'name': 'execution_error',
            'description': (
                "Signal a systemic error from inside a skill. The run's artifact is routed to "
                "the error path with the violation set.\n\n"
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
        }

    def _def_coordinate_context(self) -> dict:
        return {
            'name': 'coordinate_context',
            'description': (
                "Fetch additional conversation history beyond what you already have. The recent "
                "conversation is already in your context — try that first before calling this "
                "tool.\n\n"
                "Ops:\n"
                "- `get_history`    — compile the last `turns` utterances as a formatted string. "
                "Typical values: 3 (default, short span), 6 (whole session for ~6-turn flows), 10 (debug).\n"
                "- `get_turn`       — fetch one specific turn by `turn_id` (int, 1-indexed).\n"
                "- `get_checkpoint` — fetch a named checkpoint (e.g. `label='last_outline'`).\n\n"
                "Reach for this tool only when you need text your context doesn't carry — "
                "e.g. a user correction from 4 turns ago, or a proposal you need to quote verbatim."
            ),
            'input_schema': {
                'type': 'object',
                'properties': {
                    'op': {'type': 'string', 'enum': ['get_history', 'get_turn', 'get_checkpoint']},
                    'turns': {'type': 'integer'},
                    'turn_id': {'type': 'integer'},
                    'label': {'type': 'string'},
                },
                'required': ['op'],
            },
        }

    def _def_store_preference(self) -> dict:
        return {
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
        }




# Module alias — the module is PEX; the class name spells it out.
PEX = PolicyExecutor
