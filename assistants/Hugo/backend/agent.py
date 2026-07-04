from __future__ import annotations

import json
import logging
from datetime import datetime
from threading import Thread

from schemas.config import load_config
from backend.modules.nlu import NLU
from backend.modules.pex import PEX, _FALLBACK_MESSAGE, _NUDGE_MESSAGE, _WRAP_UP_MESSAGE
from backend.components.task_artifact import TaskArtifact
from backend.components.prompt_engineer import PromptEngineer
from backend.components.ambiguity_handler import AmbiguityHandler
from backend.components.memory_manager import MemoryManager
from backend.components.user_preferences import UserPreferences
from backend.components.business_context import BusinessContext
from backend.components.world import World
from backend.prompts.for_compressor import build_compression_prompt
from backend.prompts.for_orchestrator import build_orchestrator_prompt

log = logging.getLogger(__name__)

# _FALLBACK_MESSAGE / _NUDGE_MESSAGE / _WRAP_UP_MESSAGE are re-exported from PEX (the acting loop
# moved there) so callers importing them from backend.agent keep working.


class Agent:

    def __init__(self, username: str):
        self.username = username
        self.config = load_config()
        self.conversation_id: str | None = None
        # Orchestrator system prompt — built once per session, then frozen.
        self.system_prompt: str | None = None

        self.world = World(self.config)
        self.engineer = PromptEngineer(self.config)
        self.ambiguity = AmbiguityHandler(self.config, engineer=self.engineer)
        self.preferences = UserPreferences(self.config)
        self.business = BusinessContext(self.engineer)
        self.memory = MemoryManager(self.world.context, self.preferences, self.business)

        self.nlu = NLU(self.config, self.ambiguity, self.engineer, self.world)
        self.pex = PEX(self.config, self.ambiguity, self.engineer, self.memory, self.world)

    def take_turn(self, text:str, dax:str|None=None, payload:dict|None=None) -> dict:
        try:
            return self._orchestrate(text, dax, payload)
        except Exception as ecp:  # noqa: BLE001 — top-level safety net
            log.exception('take_turn crashed: %s', ecp)
            return self._fallback_response("Something went wrong on my end. Please try again.")

    # ── Orchestrator path ────────────────────────────────────────────────

    def _orchestrate(self, text:str, dax:str|None, payload:dict|None) -> dict:
        """One user turn as a Flow gate: deterministic PRE-HOOK, run NLU (which writes belief),
        then PEX.execute() (the acting loop), deterministic POST-HOOK. The Assistant touches the
        modules at exactly three points — NLU.understand(), PEX.execute(), and MEM (epilogue).
        A click awaits react; an utterance with no active entity awaits think; an utterance with
        an active entity runs think on a thread, truly in parallel with PEX.execute()."""
        self._ensure_session()
        turn_type = 'action' if dax else 'utterance'
        self.world.context.add_turn('User', text, turn_type=turn_type)
        log.info('USER (%s): %s', turn_type, text)
        # A new user turn answers or supersedes last turn's pending question — clear it so a
        # stale ambiguity can't leak into this turn's detection.
        if self.ambiguity.present():
            self.ambiguity.resolve()

        state = self.world.current_state()
        thread = None
        if dax:                          # click or action+text: react fills from the dax/payload
            self.nlu.understand(op='react', dax=dax, payload=payload)
        elif state.grounding['post']:    # utterance, active entity: think in parallel with PEX
            thread = Thread(target=self.nlu.understand,
                            kwargs={'op': 'think', 'user_text': text, 'payload': payload})
            thread.start()
        else:                            # utterance, no active entity: think, awaited
            self.nlu.understand(op='think', user_text=text, payload=payload)
            self.pex.prestage(state)     # fix 1 B: belief is fresh only on this awaited path

        utterance = self.pex.execute(state, self.world.context, self.system_prompt,
                                     dax=dax, payload=payload, text=text, nlu_thread=thread)
        if thread:
            thread.join()                # settle the parallel detection at the turn boundary
        return self._epilogue(utterance)

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
        state = self.world.current_state()
        state.conversation_id = self.world.conversation_id
        state.username = self.username
        self.system_prompt = build_orchestrator_prompt(
            self.engineer, self.memory, self.world.conversation_id, self.username,
            datetime.now().strftime('%Y-%m-%d'))

    def _epilogue(self, utterance:str) -> dict:
        """POST-HOOK: record the agent turn, persist the state file, run the compression
        check, build the frontend payload."""
        self.world.context.add_turn('Agent', utterance, turn_type='utterance')
        state = self.world.current_state()
        state.turn_count += 1
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
        self.ambiguity.resolve()
        self.conversation_id = None
        self.system_prompt = None  # next session rebuilds + refreezes

    def close(self):
        pass
