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
        """ Three modules run asynchronously
        1. NLU's think: (check → detect_flows → fill_slots → validate) runs on a worker thread
        2. PEX's acting loop runs on main. Convergence is forced by hook point 3 or 5 based on PEX reading the scratchpad
        3. MEM stores the turn at the end."""
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
                self.nlu.dialogue_state.classify_intent(self.engineer, self.world.context, text)
                self.world.nlu_done.clear()
                nlu_thread = threading.Thread(target=understand_user, daemon=True)
                nlu_thread.start()

            # turn_start scopes the contemplate read below (>= — tool-log turns advance
            # turn_id mid-loop, so equality would never match).
            turn_start = self.world.context.num_utterances
            utterance = self.pex.execute(self.system_prompt, dax=dax, payload=payload, text=text)

            if nlu_thread:
                nlu_thread.join()          # a turn never ends with NLU mid-write
                if nlu_error:
                    raise nlu_error[0]

            # 3.4.7: PEX queued a re-route request — the Assistant calls NLU (modules never
            # reach each other), then re-enters PEX once. The re-detected flow is on the stack.
            requests = self.world.scratchpad.read(origin='orchestrator', keys=['request'])
            if any(entry['request'] == 'contemplate' and entry['turn_number'] >= turn_start
                   for entry in requests):
                self.nlu.contemplate(text)
                # The superseded reply is loop output, not the final reply — a text-only kind 4.
                self.world.context.add_turn('agent', {'text': utterance, 'tool_uses': [],
                    'tool_results': []}, turn_type='action')
                self.world.context.add_turn('system', {'text': '[contemplate] '
                    'NLU re-routed the flow; act on the stack as it stands.'})
                completed = self.pex.completed_this_turn  # prepare() resets it on re-entry
                utterance = self.pex.execute(self.system_prompt, text='[contemplate] NLU '
                    're-routed the flow; act on the stack as it stands.')
                self.pex.completed_this_turn = completed + self.pex.completed_this_turn

            # MEM's recap writes the final reply as the single agent-utterance turn.
            self.mem.recap(utterance, self.pex.last_prompt_tokens, self.pex.completed_this_turn)
            return self._build_payload(utterance, self.world.latest_artifact())
        except Exception as ecp:  # noqa: BLE001 — top-level safety net
            return self._fallback_response("Something went wrong on my end. Please try again.")

    def _init_session(self):
        """Orchestrator session start. Runs once per session: bind a session dir when none is open,
        bind the shared session scratchpad so entries land on disk, then build and FREEZE the system prompt."""
        if self.system_prompt is not None:
            return
        if self.world.conversation_id is None:
            self.world.open_session(datetime.now().strftime(f'{self.username}_%Y%m%d_%H%M%S'))

        self.world.scratchpad._scratchpad_path = self.world.session_dir() / 'scratchpad.jsonl'
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
        self.system_prompt = None  # next session rebuilds + refreezes

    def close(self):
        pass
