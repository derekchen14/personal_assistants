from __future__ import annotations

import json
import logging
from datetime import datetime
from threading import Thread

from schemas.config import load_config
from backend.modules.nlu import NaturalLanguageUnderstanding
from backend.modules.pex import PolicyExecutor, _FALLBACK_MESSAGE, _NUDGE_MESSAGE, _WRAP_UP_MESSAGE
from backend.components.memory_manager import MemoryExtensionModule
from backend.components.task_artifact import TaskArtifact
from backend.components.prompt_engineer import PromptEngineer
from backend.components.world import World
from backend.prompts.for_compressor import build_compression_prompt
from backend.prompts.for_orchestrator import build_orchestrator_prompt

log = logging.getLogger(__name__)

# _FALLBACK_MESSAGE / _NUDGE_MESSAGE / _WRAP_UP_MESSAGE are re-exported from PEX (the acting loop
# moved there) so callers importing them from backend.assistant keep working.


class Assistant:

    def __init__(self, username: str):
        self.username = username
        self.config = load_config()
        self.conversation_id: str | None = None
        self.system_prompt: str | None = None

        self.engineer = PromptEngineer(self.config)
        self.nlu = NaturalLanguageUnderstanding(self.config, self.engineer)
        self.pex = PolicyExecutor(self.config, self.engineer)
        self.mem = MemoryExtensionModule(self.config, self.engineer)

        self.world = World(self.config, self.nlu, self.pex, self.mem)
        self.nlu.world = self.world
        self.pex.world = self.world
        self.mem.world = self.world

    def take_turn(self, text:str, dax:str|None=None, payload:dict|None=None) -> dict:
        """ Process
        0. Resolve any lingering ambguity, go straight to nlu.react() if user action was taken, then straight to step 3.
        1. PEX takes System 1 attempt at classifying intent.
        2a. If the intent is clear (Research, Draft, Revise, Publish), PEX proceeds.
            NLU runs in parallel to detects the flow and derives the intent from the detected flow.
            If the intents match, we just let PEX proceed. Otherwise, we must intervene at next hook point.
        2b. If the intent is potentially complex (Plan, Clarify, Converse), then PEX awaits nlu.understand(op='read')
        3. PEX agent decides the complexity of the request:
            - basic: just call tools itself, or even skip tools and just respond
            - intermediate: execute the policy corresponding to the detected flow
                * continue to the next stage of an already active flow
                * stackon a new flow, activated immediately, and start policy execution
            - advanced: lean on the Workflow Planner to breakdown a complex task or kick-off a Pending flow
        4. Pass the agent response back to the user
        5. Store results into memory, MEM agent decides if it wants to promote any thoughts to L2 or L3
        """
        
        try:
            self._ensure_session()
            turn_type = 'action' if dax else 'utterance'
            self.world.context.add_turn('User', text, turn_type=turn_type)
            log.info('USER (%s): %s', turn_type, text)

            if self.world.ambiguity.present:
                self.world.ambiguity.resolve()

            state = self.world.state
            thread = None
            if dax:                          # click or action+text: react fills from the dax/payload
                self.nlu.understand(op='react', dax=dax, payload=payload)
            elif state.grounding['post']:    # utterance, active entity: think in parallel with PEX
                thread = Thread(target=self.nlu.understand,
                                kwargs={'op': 'think', 'user_text': text, 'payload': payload})
                thread.start()
            else:                            # utterance, no active entity: think, awaited
                self.nlu.understand(op='think', user_text=text, payload=payload)

            utterance = self.pex.execute(state, self.world.context, self.system_prompt,
                                            dax=dax, payload=payload, text=text, nlu_thread=thread)
            if thread:
                thread.join()                # join the parallel detection at the turn boundary
            return self._epilogue(utterance)
        except Exception as ecp:  # noqa: BLE001 — top-level safety net
            log.exception('take_turn crashed: %s', ecp)
            return self._fallback_response("Something went wrong on my end. Please try again.")

    def _ensure_session(self):
        """Orchestrator session start. Runs once per session: bind a session dir when
        none is open (the dir IS the persistence format), bind the shared scratchpad to the
        session's scratchpad.jsonl so completion records land on disk, then build
        and FREEZE the three-tier system prompt."""
        if self.system_prompt is not None:
            return
        if self.world.conversation_id is None:
            self.world.open_session(datetime.now().strftime(f'{self.username}_%Y%m%d_%H%M%S'))
        # The shared scratchpad (owned by the World; seen by NLU/PEX/policies) is bound to the
        # session's file so completion records land on disk.
        self.world.scratchpad._scratchpad_path = self.world.session_dir() / 'scratchpad.jsonl'
        state = self.world.state
        state.conversation_id = self.world.conversation_id
        state.username = self.username
        self.system_prompt = build_orchestrator_prompt(
            self.engineer, self.mem, self.world.conversation_id, self.username,
            datetime.now().strftime('%Y-%m-%d'))

    def _epilogue(self, utterance:str) -> dict:
        """POST-HOOK: record the agent turn, persist the state file, run the compression
        check, build the frontend payload."""
        self.world.context.add_turn('Agent', utterance, turn_type='utterance')
        state = self.world.state
        state.turn_count += 1
        state.flow_stack = self.pex.flow_stack.to_list()  # refresh the saved copy, then save
        state.save(self.world.state_file())  # _ensure_session guarantees a bound session
        self._compression_check()
        log.info('AGENT: %s', utterance[:256])
        return self._build_payload(utterance, self.world.latest_artifact())

    def _compression_check(self):
        """Compactor trigger: real prompt-token usage from PEX's last acting-loop API response
        against the configured threshold, checked in the post-hook epilogue, never mid-loop. A
        summarizer failure aborts the compaction — the message list stays unchanged and the
        turn's reply still goes out."""
        compression = self.config['compression']
        if self.pex.last_prompt_tokens < compression['threshold_tokens']:
            return
        try:
            self.world.context.compress_messages(self._summarize_middle,
                                                 compression['protect_tail'],
                                                 self.pex.last_prompt_tokens)
        except Exception as ecp:  # noqa: BLE001 — aux-LLM failure must not eat the reply
            log.warning('compression aborted, messages unchanged: %s', ecp)

    def _summarize_middle(self, middle:list[dict], previous_summary:str|None, budget:int) -> str:
        """The auxiliary middle-summarizer — the cheap aux model is PromptEngineer's
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
        self.world.ambiguity.resolve()
        self.conversation_id = None
        self.system_prompt = None  # next session rebuilds + refreezes

    def close(self):
        pass
