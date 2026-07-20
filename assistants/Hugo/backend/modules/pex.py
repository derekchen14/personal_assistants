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

# The orchestrator may call these read-only domain tools directly; every write still runs through a flow.
READ_ONLY_DOMAIN_TOOLS = ('find_posts', 'read_metadata', 'read_section', 'search_notes',
                          'list_channels', 'channel_status')

def _block_summaries(artifact) -> list:
    """Project artifact blocks for the orchestrator, evaluation harness, and logs without restating content.
    Each summary carries its type and data keys; selections and checklists also include option labels."""
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

        # MEM reads the latest agent-loop prompt-token usage when checking compaction.
        self.last_prompt_tokens = 0
        # Track every flow popped this turn; MEM stores Completed members and orchestrate resets their budgets.
        self.recently_finished = []
        self._reads = 0  # Successful read-only domain tool calls this turn; reset by prepare().
        self._turn_start = 0  # Context position captured by prepare() to scope reads to this turn.
        # PEX Agent state persists across orchestrate() calls and resets in prepare().
        self.rounds = 0        # rounds since the last completion — a completion resets the budget
        self.finished = 0      # Completed members of recently_finished already counted
        self.errors = 0        # consecutive corrective tool failures
        self.nudged = False    # a thinking-only miss already nudged this turn
        self.last_call = None  # (name+args key, succeeded) — _guarded_call's dedupe memory
        # Map exposed component tool names to underscored methods; tool definitions control caller access.
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
        """Finish wiring the MEM-backed domain tool and policies with their scoped World components."""
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
        """Validate an artifact for display and route a declared violation directly to the error path."""
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
        """Reset per-turn state, wait for NLU on Plan or Clarify, and append the initial prediction note.
        The note exposes `state.pred_flows`; the PEX Agent decides whether to stack a flow through manage_flows."""
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
        else:  # NLU abstained after the wait, so include any pending question directly.
            question = (self.world.ambiguity.ask('') if self.world.ambiguity.is_present else '')
            asked = (f'A clarification is pending — relay it in your own voice: "{question}" '
                     if question else '')
            note = (f"[typesafe] intent={state.pred_intent} — no flow was detected. {asked}"
                    f"Pick a flow yourself if the request is actually clear.")
        context.add_turn('system', {'text': note})   # The first PEX Agent round sees this system utterance.

    def orchestrate(self, system_prompt) -> str:
        """Run one PEX Agent round, returning an empty string mid-turn or reply text on the terminal round.
        Tool calls pass through `_guarded_call` and `call_tool`; NLU changes surface through hook 3/5 reads.
        Terminal plain text or `_final_emit()` after repeated misses or limits ends the turn."""
        context, state = self.world.context, self.world.state
        self.rounds += 1
        catalog = self.get_tools_for_orchestrator()
        messages = context.compile_messages()
        messages.append({'role': 'user', 'content': self.refresh()})   # Ephemeral round refresh.
        response = self.engineer(system_prompt, messages, family='claude',
                                 tier='high', tools=catalog, max_tokens=4096)
        self._track_usage(response)
        text_parts = [block.text for block in response.content if block.type == 'text']
        tool_uses = [block for block in response.content if block.type == 'tool_use']
        text = '\n'.join(part for part in text_parts if part).strip()

        if not tool_uses:
            if text:
                self.wait_for_nlu('hook point 5')   # post-LLM, no tools ran
                # Give an unseen `new_flow` one more round so the next refresh can surface it.
                fresh = self.session_scratchpad.read(origin='nlu', keys=['new_flow'], consume=False)
                if any(e['used_count'] == 0 and e['turn_number'] >= self._turn_start for e in fresh):
                    context.add_turn('agent', {'text': text, 'tool_uses': [],
                                               'tool_results': []}, turn_type='action')
                    return ''                       # renders NLU's announcement
                state.keep_going = False            # terminal round — the turn is worded
                return text
            if self.nudged:  # A second thinking-only response forces wrap-up.
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
            except TimeoutError:      # A hook timeout fails the turn loudly.
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
        """Block at hooks 1, 3, and 5 until NLU settles; raise on expiry for take_turn's safety net."""
        if not self.world.nlu_done.wait(timeout=30):
            raise TimeoutError(f'NLU still thinking after 30s at {hook}')

    def _final_emit(self, system_prompt:str) -> str:
        """Force a plain-text terminal reply after the round budget, corrective cap, or second empty response.
        Use the canned fallback only when the final model call still returns no text."""
        context = self.world.context
        context.add_turn('system', {'text': _WRAP_UP_MESSAGE})
        response = self.engineer(system_prompt, context.compile_messages(), family='claude',
                                 tier='high', max_tokens=1024)
        self._track_usage(response)
        text_parts = [block.text for block in response.content if block.type == 'text']
        return '\n'.join(part for part in text_parts if part).strip() or _FALLBACK_MESSAGE

    def _guarded_call(self, tool_use, valid:set, last_call) -> tuple[dict, tuple]:
        """Reject unknown tools and repeated successful calls, then route valid calls through `call_tool`.
        `last_call` stores the call key and success; failed calls remain retryable. A manage_flows key includes
        the live stack so identical arguments after an NLU stack change count as a new call."""
        # Pre-tool hook
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
        """Record actual agent-loop prompt-token usage, including cache reads and writes, for MEM compaction."""
        usage = response.usage
        if usage:
            self.last_prompt_tokens = (usage.input_tokens
                                       + (usage.cache_creation_input_tokens or 0)
                                       + (usage.cache_read_input_tokens or 0))

    # -- Tool calls -------------------------------------------------------

    def call_tool(self, tool_name:str, tool_input:dict) -> dict:
        """Route domain and component tool calls through one surface and convert failures to corrective errors.
        Preserve hook TimeoutError so the Assistant's safety net can fail the turn loudly."""
        try:
            if tool_name in self.domain_tools:
                service, method_name = self.domain_tools[tool_name]
                method = getattr(service, method_name)
                return method(**tool_input)
            elif tool_name in self.component_tools:
                return self.component_tools[tool_name](tool_input)
            else:
                return corrective('invalid_input', f'Unknown tool: {tool_name}')
        except TimeoutError:          # A hook timeout fails the turn loudly.
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
        """Return the live FlowStack and Active flow's filled slots to a policy sub-agent."""
        flow = self.flow_stack.get_flow()
        return {'_success': True, 'flows': self.flow_stack.to_list(),
                'slots': flow.slot_values_dict() if flow else {}}

    def _execution_error(self, params:dict) -> dict:
        """Acknowledge a violation so call_policy can stamp the artifact and route it to the error path."""
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
    # `call_tool` converts errors from these state, memory, and NLU surfaces into corrective results.

    def _manage_flows(self, params:dict) -> dict:
        """Apply update, stackon, fallback, or pop to the FlowStack and run newly runnable work.
        `update` changes status or stage at any depth; `pop` removes terminal tops and promotes Pending work.
        Policy sub-agents may defer stackon or fallback so the flow resurfaces for execution at the PEX layer.
        NLU retains ownership of belief, grounding, and slot filling."""
        defer = params.get('defer', False)
        params = {**params, 'op': {'update': 'update_flow'}.get(params['op'], params['op'])}
        if defer and params['op'] not in ('stackon', 'fallback'):
            return corrective('invalid_input', 'sub-agents may only stackon or fallback — '
                              'update and pop belong to the PEX layer')
        state = self.world.state
        kwargs = dict(params.get('fields', {}))
        if 'flow_name' in params:
            kwargs['flow_name'] = params['flow_name']
        if 'slots' in kwargs:  # NLU owns slot filling.
            return corrective('invalid_input', 'slots are not writable through manage_flows — '
                              'NLU fills slots; update takes status/stage only')
        if 'status' in kwargs:
            kwargs['status'] = kwargs['status'].capitalize()
        promoted = None
        match params['op']:
            case 'stackon':
                # Do not transfer slots while an ambiguity leaves the incomplete flow's values in question.
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
        # Run the top policy only when the operation makes a flow newly runnable.
        run = (params['op'] == 'fallback'
               or (params['op'] == 'pop' and promoted is not None)
               or (params['op'] == 'stackon' and params.get('active', True))
               or (params['op'] == 'update_flow' and kwargs.get('status') == 'Active'))
        # Deferred policy calls leave the flow on the stack for the PEX Agent to run on a later round.
        if run and not defer:
            # Pin a promoted flow because NLU may place another Active entry before execution begins.
            return self.execute(start=promoted)
        return {'_success': True, '_error': ''}

    def execute(self, start=None) -> dict:
        """Run policy sub-agents surfaced by manage_flows until the live FlowStack stops changing.
        Each pass grounds, checks security, runs and verifies the policy, then waits for NLU at hook 3.
        Completion pops terminal flows; same-intent changes return for an Agent decision, while different
        intents continue in code. `start` pins a promoted first flow. Return `{_success, _error, artifact}`
        with the full artifact stored in the World and a compact projection returned to the PEX Agent."""
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

            # Ground only empty entity slots at the shared execution point, preserving values NLU already filled.
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
            # A different intent continues in code with the replacement flow.
        if result is not None:
            return result
        return {'_success': True, '_error': ''}          # a run that surfaced nothing new

    def _complete_pop(self, flow, artifact, entry, context):
        """Pop terminal flows and a surfaced Plan marker, synthesizing a missing completion entry for refresh."""
        if entry is None:  # completed without complete_flow — synthesize an entry
            summary = artifact.thoughts or f'{flow.name()} completed'
            self.session_scratchpad.append_entry(flow.name(),
                {'turn_number': context.num_utterances, 'summary': summary,
                 'metadata': artifact.data or {}})
        popped, _ = self.flow_stack.pop()  # Completed and Invalid leave together
        next_flow = self.flow_stack.get_flow()
        if next_flow and next_flow.name() == 'plan':
            # A surfaced Plan marker has finished overseeing its steps and leaves with the terminal flows.
            next_flow.status = 'Completed'
            more, _ = self.flow_stack.pop()
            popped += more
        self.recently_finished += popped   # every popped flow — either status
        if self.world.state.has_plan and not self.flow_stack.find_by_name('plan'):
            self.world.state.has_plan = False  # the marker anchors the flag — it left the stack

    def _result(self, artifact, error:str='', note:str='') -> dict:
        """Return `{_success, _error, artifact}` with a compact artifact projection for the PEX Agent.
        The projection includes origin, thoughts, block summaries, and any violation; `note` fills empty thoughts."""
        view = {'origin': artifact.origin, 'thoughts': artifact.thoughts or note,
                'blocks': _block_summaries(artifact)}
        if 'violation' in artifact.data:
            view['violation'] = artifact.data['violation']
        return {'_success': not error, '_error': error, 'artifact': view}

    def call_policy(self, flow) -> tuple:
        """Look up and run one policy sub-agent, then return its artifact and optional completion entry.
        Trace each sub-agent tool call and append the run trajectory to the session's `subagents.jsonl`."""
        policy = self._policies[flow.intent]
        calls = []

        def traced_tool(name, params):
            # Defer a sub-agent's FlowStack change so the flow resurfaces for execution at the PEX layer.
            call_params = {**params, 'defer': True} if name == 'manage_flows' else params
            result = self.call_tool(name, call_params)
            calls.append({'tool': name, 'input': params, '_success': result['_success'],
                          '_error': result.get('_error', '')})
            return result

        artifact = policy.execute(self.world.state, self.world.context, traced_tool)
        # Stamp violations from successful execution_error calls so verify() selects the error path.
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
        """Build the ephemeral round message from the live stack, unseen scratchpad entries, and ambiguity.
        Scratchpad reads advance `used_count`, so each announcement, completion, or finding surfaces once."""
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
        """Read the assembled belief or queue a contemplate request after NLU settles.
        The Assistant consumes contemplate requests from the scratchpad, calls NLU, and re-enters the loop."""
        self.wait_for_nlu('understand')
        if params['op'] == 'contemplate':
            # The Assistant's consuming read advances used_count so each re-route request runs once.
            self.session_scratchpad.append_entry('orchestrator',
                {'turn_number': self.world.context.num_utterances, 'request': 'contemplate',
                 'summary': 'policy could not proceed — asking NLU to re-route'})
            return {'_success': True, '_message': 'Re-route queued. End your reply this round; '
                                                 'the re-detected flow runs on the next pass.'}
        # Assemble the Dialogue State with PEX's live FlowStack; state.json receives only a saved copy.
        document = self.world.state.read_state()
        document['flow_stack'] = self.flow_stack.to_list()
        return {'_success': True, 'state': document}

    def _scratchpad(self, params:dict) -> dict:
        """Read scratchpad entries by origin or keys, or append one under its origin or the Active flow.
        The caller supplies `turn_number`; append_entry stamps version and used_count."""
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
        """Build a policy sub-agent's component tools and append the flow's scoped domain tools.
        Its manage_flows surface includes stackon and fallback; update and pop remain at the PEX layer."""
        tools = [self._def_manage_flows(sub_agent=True), self._def_view_policies(),
                 self._def_scratchpad(), self._def_declare_ambiguity(),
                 self._def_execution_error(), self._def_coordinate_context()]
        for tool_name in flow.tools:
            tool_def = self._get_tool_def(tool_name)
            if tool_def:
                tools.append(tool_def)
        return tools

    def get_tools_for_orchestrator(self) -> list[dict]:
        """Build the PEX Agent's planner, belief, scratchpad, context, preference, and read-only domain tools."""
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
