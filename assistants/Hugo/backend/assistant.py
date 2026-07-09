from __future__ import annotations

import json
import logging
from datetime import datetime

from schemas.config import load_config
from backend.modules.nlu import NaturalLanguageUnderstanding
from backend.modules.pex import PolicyExecutor, _FALLBACK_MESSAGE, _NUDGE_MESSAGE, _WRAP_UP_MESSAGE
from backend.modules.mem import MemoryExtensionModule
from backend.components.task_artifact import TaskArtifact
from backend.components.prompt_engineer import PromptEngineer
from backend.components.world import World
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
        self.mem = MemoryExtensionModule(self.config, self.engineer, username)

        self.world = World(self.config, self.nlu, self.pex, self.mem)
        self.nlu.world = self.world
        self.pex.world = self.world
        self.mem.world = self.world

    def take_turn(self, text:str, dax:str|None=None, payload:dict|None=None) -> dict:
        """ Process
        0. Resolve any lingering ambguity, go straight to nlu.react() if user action was taken, then straight to step 3.
        1. PEX takes System 1 attempt at classifying intent — the first move of its agent loop,
           per the orchestrator prompt. Never a separate call.
        2a. If the intent is clear (Research, Draft, Revise, Publish), PEX proceeds.
            NLU detects the flow and derives the intent from the detected flow.
            If the intents match, we just let PEX proceed. Otherwise, we must intervene at next hook point.
        2b. If the intent is potentially complex (Plan, Clarify, Converse), then PEX awaits nlu.understand(op='read')
        3. PEX agent decides the complexity of the request:
            - basic: just call tools itself, or even skip tools and just respond
            - intermediate: execute the policy corresponding to the detected flow
                * continue to the next stage of an already active flow
                * stackon a new flow, activated immediately, and start policy execution
            - advanced: lean on the Workflow Planner to breakdown a complex task or kick-off a Pending flow
        4. Pass the agent response back to the user
        5. Store results into memory, MEM decides if it wants to promote any thoughts to L2 or L3
        """

        try:
            self._ensure_session()
            turn_type = 'action' if dax else 'utterance'
            self.world.context.add_turn('User', text, turn_type=turn_type)
            log.info('USER (%s): %s', turn_type, text)

            # 0. Round 3.3: an open ambiguity persists across turns (and task detours) until
            # grounding completes — NLU's bind pass resolves it. Only the per-turn ask counts
            # reset on a new user turn.
            self.world.ambiguity.counts = dict.fromkeys(self.world.ambiguity.counts, 0)

            if dax:      # click or action+text: react fills belief from the dax/payload
                self.nlu.understand(op='react', dax=dax, payload=payload)
            else:        # utterance: detection writes belief before PEX's loop runs
                self.nlu.understand(op='think', user_text=text, payload=payload)

            # 1-4. PEX's agent loop: System-1 intent attempt first, then act, then reply.
            utterance = self.pex.execute(self.system_prompt, dax=dax, payload=payload, text=text)

            # 5. Store the turn into memory.
            self.mem.store_turn(utterance, self.pex.last_prompt_tokens, self.pex.completed_this_turn)
            log.info('AGENT: %s', utterance[:256])
            return self._build_payload(utterance, self.world.latest_artifact())
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
