import logging
import threading
from datetime import datetime

from schemas.config import load_config
from backend.modules.nlu import NaturalLanguageUnderstanding
from backend.modules.pex import PolicyExecutor
from backend.modules.mem import MemoryExtensionModule
from backend.components.task_artifact import TaskArtifact
from backend.components.prompt_engineer import PromptEngineer
from backend.components.world import World
from backend.prompts.for_orchestrator import build_orchestrator_prompt

log = logging.getLogger(__name__)

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

    def take_turn(self, text:str, dax:str|None=None, payload:dict={}) -> dict:
        """Run one turn with three async modules:
        * NLU's think (check → detect_flows → fill_slots → validate) runs on a worker thread.
        * The PEX Agent runs on main: prepare(), then one orchestrate() call while state.keep_going.
          Hook 3/5 reads force convergence, and the terminal round's return value is the reply.
        * MEM stores the turn at the end, including Completed flows only."""
        def understand_user():
            try:
                self.nlu.think(text, payload)
            except Exception as ecp:  # noqa: BLE001 — stored, re-raised at the join
                nlu_error.append(ecp)
            finally:
                self.world.nlu_done.set()  # PEX's waits always wake, even on a crash
        try:
            self._init_session()
            turn_type = 'action' if dax else 'utterance'
            content = {'text': text, 'dax': dax, 'payload': payload} if dax else {'text': text}
            self.world.context.add_turn('user', content, turn_type=turn_type)

            nlu_thread, nlu_error = None, []
            if turn_type == 'action':
                self.nlu.react(dax, payload)
                self.world.nlu_done.set()
            else:
                prev_flow = self.world.flows.get_flow()
                self.nlu.dialogue_state.classify_intent(self.engineer, self.world.context, prev_flow)
                self.world.nlu_done.clear()
                nlu_thread = threading.Thread(target=understand_user, daemon=True)
                nlu_thread.start()

            self.pex.prepare()
            reply = ''
            while self.world.state.keep_going:
                if self.contemplation_requested():  # A policy requested re-routing.
                    self.nlu.contemplate(text)      # The agent runs the replacement next round.
                reply = self.pex.orchestrate(self.system_prompt)
            if nlu_thread:
                nlu_thread.join()          # a turn never ends with NLU mid-write
                if nlu_error: raise nlu_error[0]

            self.mem.recap(reply, self.pex.last_prompt_tokens, self.pex.recently_finished)
            return self._build_payload(reply, self.world.artifacts[-1])
        except Exception as ecp:  # noqa: BLE001 — top-level safety net
            log.exception('take_turn failed: %s', ecp)
            return self._fallback_response("Something went wrong on my end. Please try again.")

    def contemplation_requested(self):
        requests = self.world.scratchpad.read(origin='orchestrator', keys=['request'])
        turn_start = self.world.context.num_utterances

        triggered = False
        for entry in requests:
            req_type, turn_num, used = entry['request'], entry['turn_number'], entry['used_count']
            if req_type == 'contemplate' and turn_num >= turn_start and used == 0:
                triggered = True
                break
        return triggered

    def _init_session(self):
        """Initialize once per session: open its directory, bind the scratchpad, and freeze the system prompt."""
        if self.system_prompt is not None:
            return
        if self.world.conversation_id is None:
            self.world.open_session(datetime.now().strftime(f'{self.username}_%Y%m%d_%H%M%S'))

        self.world.scratchpad._pathway = self.world.session_dir() / 'scratchpad.jsonl'
        state = self.world.state
        state.conversation_id = self.world.conversation_id
        state.username = self.username
        self.system_prompt = build_orchestrator_prompt(
            self.engineer, self.mem, self.world.conversation_id, self.username,
            datetime.now().strftime('%Y-%m-%d'))

    def _fallback_response(self, message: str) -> dict:
        self.world.context.add_turn('agent', {'text': message})
        payload = {'message': message, 'actions': [], 'artifact': None, 'block': 'default'}
        return payload

    def _build_payload(self, utterance: str, artifact: TaskArtifact) -> dict:
        return {'message': utterance, 'actions': [], 'artifact': artifact.to_dict()}

    # ── Session management ────────────────────────────────────────────

    def reset(self):
        self.world.reset()
        self.world.ambiguity.resolve()
        self.conversation_id = None
        self.system_prompt = None  # Rebuild and refreeze for the next session.

    def close(self):
        pass
