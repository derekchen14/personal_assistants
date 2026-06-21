from __future__ import annotations

import json
import logging
import os
from datetime import datetime

from schemas.config import load_config
from backend.modules.nlu import NLU
from backend.modules.pex import PEX
from backend.components.task_artifact import TaskArtifact
from backend.components.prompt_engineer import PromptEngineer
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.memory_manager import MemoryManager
from backend.components.world import World
from backend.prompts.for_compressor import build_compression_prompt
from backend.prompts.for_orchestrator import build_orchestrator_prompt
from utils.helper import dax2flow

log = logging.getLogger(__name__)

# Orchestrator loop bounds (changes.md §3.1/§3.3); the exact value is tuned with Phase 3 latency
# data. _MAX_CORRECTIVE bounds consecutive failed tool calls before the loop stops burning rounds.
_MAX_ROUNDS = 8
_MAX_CORRECTIVE = 3
_FALLBACK_MESSAGE = "I wasn't able to finish that. Could you try rephrasing?"
_NUDGE_MESSAGE = ('Your last response had no visible text and no tool calls. Reply with your '
                  'final response to the user, or call a tool.')
_WRAP_UP_MESSAGE = ('Stop calling tools. Reply to the user now in 1-2 sentences of plain text: '
                    'summarize what was accomplished this turn, or ask what they need.')

class Agent:

    def __init__(self, username: str):
        self.username = username
        self.config = load_config()
        self.conversation_id: str | None = None
        # Orchestrator system prompt — built once per session, then frozen (decision 8).
        self.system_prompt: str | None = None
        # Real prompt-token usage off the last orchestrator API response — the compression
        # trigger reads it in the post-hook epilogue (changes.md §5.6).
        self.last_prompt_tokens = 0

        self.world = World(self.config)
        self.engineer = PromptEngineer(self.config)
        self.ambiguity = AmbiguityHandler(self.config, engineer=self.engineer)
        self.memory = MemoryManager(self.config)

        self.nlu = NLU(self.config, self.ambiguity, self.engineer, self.world)
        self.pex = PEX(self.config, self.ambiguity, self.engineer, self.memory, self.world)
        # Orchestrator tool wiring (changes.md §4.1): PEX dispatches detect_and_fill into NLU.
        self.pex.nlu = self.nlu

    def take_turn(self, text:str, dax:str|None=None, payload:dict|None=None) -> dict:
        try:
            return self._orchestrate(text, dax, payload)
        except Exception as ecp:  # noqa: BLE001 — top-level safety net
            log.exception('take_turn crashed: %s', ecp)
            return self._fallback_response("Something went wrong on my end. Please try again.")

    # ── Orchestrator path (changes.md §3, decisions 3, 6, 13) ────────────

    def _orchestrate(self, text:str, dax:str|None, payload:dict|None) -> dict:
        """One user turn through the orchestrator (changes.md §3.1): deterministic
        PRE-HOOK, the bounded LLM loop on the persistent message list, deterministic
        POST-HOOK. Pure clicks bypass the loop entirely (decision 13)."""
        self._ensure_session()
        turn_type = 'action' if dax else 'utterance'
        self.world.context.add_turn('User', text, turn_type=turn_type)
        log.info('USER (%s): %s', turn_type, text)
        # A new user turn answers or supersedes last turn's pending question — clear it so a
        # stale ambiguity can't leak into this turn's dispatches (mirrors NLU.understand).
        if self.ambiguity.present():
            self.ambiguity.resolve()

        if dax and not text.strip():
            utterance = self._click_bypass(dax, payload or {})
        else:
            message = text
            if dax:  # action + text: the loop runs with the resolved flow injected as context
                flow_name = dax2flow(dax)
                message = (f'[action] This turn arrived with a resolved flow: {flow_name!r} '
                           f'(dax {dax}, payload {json.dumps(payload or {}, default=str)}). '
                           f'Do not re-decide the click — build on it.\n{text}')
            self.world.context.append_message({'role': 'user', 'content': message})
            utterance = self._run_loop()
        return self._epilogue(utterance)

    def _ensure_session(self):
        """Orchestrator session start (changes.md §3.1 SESSION START). Runs once per
        session: bind a session dir when none is open (decision 11 — the dir IS the
        persistence format), point L1 at the session's scratchpad.jsonl (§5.3, so
        activate_flow completion records land on disk), then build and FREEZE the
        three-tier system prompt (decision 8)."""
        if self.system_prompt is not None:
            return
        if self.world.conversation_id is None:
            self.world.open_session(datetime.now().strftime(f'{self.username}_%Y%m%d_%H%M%S'))
        # Constructor-time wiring of the file-backed L1 lands at cutover; until then the
        # shared MemoryManager (policies hold references to it) is re-pointed in place.
        self.memory._scratchpad_path = self.world.session_dir() / 'scratchpad.jsonl'
        state = self.world.current_state()
        state.conversation_id = self.world.conversation_id
        state.username = self.username
        self.system_prompt = build_orchestrator_prompt(
            self.engineer, self.memory, self.world.conversation_id, self.username,
            datetime.now().strftime('%Y-%m-%d'))

    def _click_bypass(self, dax:str, payload:dict) -> str:
        """Pure click (decision 13): the dax already names the flow, so nothing is
        re-decided — resolve deterministically, dispatch the flow, and the dispatched flow's
        artifact thoughts ARE the reply (PEX composes directly; no RES). Mirrors NLU.react
        minus the per-turn state insert: the orchestrator path keeps one session state, so
        react's _build_state would clobber it."""
        flow_name = dax2flow(dax)
        _, filtered = self.nlu._fill_slices(self.world.current_state(), payload)
        flow = self.nlu._push_or_get(flow_name)
        self.nlu._fill_slots(flow, filtered)
        self.world.context.append_message({'role': 'user', 'content':
            f'[click] dax={dax} flow={flow_name} payload={json.dumps(payload, default=str)}'})

        result = self.pex.activate_flow({'flow_name': flow_name})
        artifact = self.world.latest_artifact()
        utterance = result.get('question') or artifact.thoughts or _FALLBACK_MESSAGE
        self.world.context.append_message({'role': 'assistant', 'content': utterance})
        return utterance

    def _run_loop(self) -> str:
        """The bounded orchestrator loop (changes.md §3.1 LOOP, §3.3 guardrails): call the
        LLM with the frozen system prompt + persistent message list + orchestrator tool
        catalog; dispatch tool calls through PEX; append results. A plain-text response
        with no tool calls ends the turn and IS the utterance, verbatim."""
        context = self.world.context
        tools = self.pex.get_tools_for_orchestrator()
        valid = {tool['name'] for tool in tools}
        model_id = self.config['models']['overrides']['orchestrator']['model_id']

        nudged = False
        errors = 0
        last_call = None
        for round_idx in range(_MAX_ROUNDS):
            response = self.engineer._call_claude(self.system_prompt, context.messages,
                                                  model_id, tools=tools, max_tokens=4096)
            self._track_usage(response)
            text_parts = [block.text for block in response.content if block.type == 'text']
            tool_uses = [block for block in response.content if block.type == 'tool_use']
            text = '\n'.join(part for part in text_parts if part).strip()

            if not tool_uses:
                if text:
                    context.append_message({'role': 'assistant', 'content': text})
                    return text
                if nudged:  # thinking-only twice → canned fallback (§3.3)
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
                # §3.3 pairing invariant: every appended tool_use MUST get a tool_result in
                # the next message, even if the dispatch path itself crashes — a dangling
                # tool_use poisons messages.jsonl for every later turn of the session.
                try:
                    result, last_call = self._guarded_call(tool_use, valid, last_call)
                except Exception as ecp:  # noqa: BLE001 — convert to a corrective tool error
                    log.exception('tool dispatch crashed: %s', ecp)
                    result = {'_success': False, '_error': 'server_error',
                              '_message': f'{type(ecp).__name__}: {ecp}'}
                    last_call = None
                errors = errors + 1 if not result['_success'] else 0
                log.info('  orch round=%d tool=%s ok=%s', round_idx + 1, tool_use.name,
                         result['_success'])
                results.append({'type': 'tool_result', 'tool_use_id': tool_use.id,
                                'content': json.dumps(result, default=str)})
            context.append_message({'role': 'user', 'content': results})
            if errors >= _MAX_CORRECTIVE:
                break  # the model keeps failing tool calls — stop burning rounds
        return self._final_emit(model_id)

    def _final_emit(self, model_id:str) -> str:
        """Round budget or corrective cap exhausted: one last no-tools call forces a
        plain-text wrap-up (the Hermes terminal emit), so completed work still gets a real
        reply instead of the canned fallback. Falls back only if even that produces
        nothing."""
        context = self.world.context
        context.append_message({'role': 'user', 'content': _WRAP_UP_MESSAGE})
        response = self.engineer._call_claude(self.system_prompt, context.messages,
                                              model_id, max_tokens=1024)
        self._track_usage(response)
        text_parts = [block.text for block in response.content if block.type == 'text']
        utterance = '\n'.join(part for part in text_parts if part).strip() or _FALLBACK_MESSAGE
        context.append_message({'role': 'assistant', 'content': utterance})
        return utterance

    def _guarded_call(self, tool_use, valid:set, last_call) -> tuple[dict, tuple]:
        """§3.3 guardrails around one tool call: hallucinated names and identical
        consecutive calls return corrective errors instead of dispatching. Everything else
        routes through PEX's dispatcher, which already converts bad args into corrective
        tool errors the model can retry on. These guards are the legitimate exception to
        the no-defensive-code rule — LLM output is genuinely unpredictable input.

        `last_call` is (name+args key, succeeded). Dedupe only fires when the previous
        identical call SUCCEEDED — retrying the same call after a transient tool error
        (server_error from an overloaded LLM, a flaky channel API) is legitimate recovery,
        not a loop."""
        call = (tool_use.name, json.dumps(dict(tool_use.input or {}), sort_keys=True, default=str))
        if tool_use.name not in valid:
            result = {'_success': False, '_error': 'invalid_input',
                      '_message': f'Unknown tool: {tool_use.name!r}. Use a tool from your tool list.'}
        elif last_call and call == last_call[0] and last_call[1]:
            result = {'_success': False, '_error': 'duplicate_call',
                      '_message': 'Identical consecutive tool call skipped — change the '
                                  'arguments or respond to the user.'}
        else:
            result = self.pex._dispatch_tool(tool_use.name, dict(tool_use.input or {}))
            if '_success' not in result:  # manage_memory keeps its old {'status': ...} contract
                result['_success'] = result.get('status') == 'success'
        return result, (call, result['_success'])

    def _epilogue(self, utterance:str) -> dict:
        """POST-HOOK (changes.md §3.1): record the agent turn, persist the state file,
        run the compression check (§5.6), build the unchanged frontend payload."""
        self.world.context.add_turn('Agent', utterance, turn_type='utterance')
        state = self.world.current_state()
        state.turn_count += 1
        state.save(self.world.state_file())  # _ensure_session guarantees a bound session
        self._compression_check()
        log.info('AGENT: %s', utterance[:256])
        return self._build_payload(utterance, self.world.latest_artifact())

    def _track_usage(self, response):
        """Record real prompt-token usage off an orchestrator API response (Hermes triggers
        on response.usage, never on estimates). Cache reads/writes count toward the window."""
        usage = response.usage
        if usage:
            self.last_prompt_tokens = (usage.input_tokens
                                       + (usage.cache_creation_input_tokens or 0)
                                       + (usage.cache_read_input_tokens or 0))

    def _compression_check(self):
        """Hermes compactor trigger (changes.md §5.6, decision 9): real prompt-token usage
        from the last API response against the configured threshold, checked in the post-hook
        epilogue, never mid-loop. A summarizer failure aborts the compaction — the message
        list stays unchanged and the turn's reply still goes out (Hermes abort semantics)."""
        compression = self.config['compression']
        if self.last_prompt_tokens < compression['threshold_tokens']:
            return
        try:
            self.world.context.compress_messages(self._summarize_middle,
                                                 compression['protect_tail'],
                                                 self.last_prompt_tokens)
        except Exception as ecp:  # noqa: BLE001 — aux-LLM failure must not eat the reply
            log.warning('compression aborted, messages unchanged: %s', ecp)

    def _summarize_middle(self, middle:list[dict], previous_summary:str|None, budget:int) -> str:
        """The auxiliary middle-summarizer — Hermes's cheap aux model is PromptEngineer's
        LOW tier. The prompt lives in backend/prompts/for_compressor.py."""
        prompt = build_compression_prompt(middle, previous_summary, budget)
        return self.engineer(prompt, task='compress', model='low', max_tokens=int(budget * 1.3))

    def _fallback_response(self, message: str) -> dict:
        self.world.context.add_turn('Agent', message, turn_type='agent_response')
        payload = {'message': message, 'actions': [], 'artifact': None, 'block': 'default'}
        return payload

    def _build_payload(self, utterance: str, artifact: TaskArtifact) -> dict:
        return {'message': utterance, 'actions': [], 'artifact': artifact.to_dict()}

    # ── Session management ────────────────────────────────────────────

    def reset(self):
        self.world.reset()
        self.ambiguity.resolve()
        self.memory.clear_scratchpad()
        self.conversation_id = None
        self.system_prompt = None  # next session rebuilds + refreezes (decision 8)
        self.last_prompt_tokens = 0

    def close(self):
        pass
