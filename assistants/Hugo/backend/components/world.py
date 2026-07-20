import shutil
import threading
from pathlib import Path

from backend.components.task_artifact import TaskArtifact

_SESSIONS_DIR = Path(__file__).resolve().parents[2] / 'database' / 'sessions'


class World:
    """The shared component registry. Each module constructs and owns its components; the World
    holds one reference to each under its canonical name, so every module reaches foreign
    components the same way (world.state, world.flows, ...) rather than making copies. """
    def __init__(self, config, nlu, pex, mem):
        self.config = config
        self.artifacts: list[TaskArtifact] = []

        # Shared Components
        self.state = nlu.dialogue_state
        self.ambiguity = nlu.ambiguity_handler
        self.flows = pex.flow_stack
        self.scratchpad = pex.session_scratchpad
        self.context = mem.context_coordinator
        self.prefs = mem.user_preferences
        self.knowledge = mem.business_knowledge

        # The threaded-turn wait primitive: PEX's hook reads block on NLU's thinking settling.
        # TODO(round 3.4, revisit once the loop works): Event chosen over the alternative — PEX
        # polling the scratchpad between loop rounds — because waits wake exactly when NLU settles
        self.nlu_done = threading.Event()
        self.nlu_done.set()

        self.conversation_id: str | None = None
        self._seed_session()

    def _seed_session(self):
        """Every session starts with a default artifact and a system kickoff turn (an action turn,
        so it doesn't advance num_utterances) — every downstream component can assume world.state
        and world.artifacts[-1] are usable."""
        self.artifacts.append(TaskArtifact())
        initial_content = {'text': 'Session started.', 'activity': 'session_start', 'result': {}}
        self.context.add_turn('system', initial_content, turn_type='action')

    # ── Session-dir lifecycle ─────

    def open_session(self, conversation_id:str):
        """Bind this World to a session dir. The components keep their live objects — looking at
        a PREVIOUS session's contents is MEM's job (read from disk), never a rebind here."""
        self.conversation_id = conversation_id
        session_path = _SESSIONS_DIR / conversation_id
        self.context.load_history(session_path / 'history.jsonl')
        self.scratchpad._pathway = Path(session_path / 'scratchpad.jsonl')

    def session_dir(self) -> Path:
        """database/sessions/<conversation_id>/ — created lazily on first access."""
        path = _SESSIONS_DIR / self.conversation_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def reset(self):
        """New session: every component resets IN PLACE (the no-rebind rule) and the session dir
        starts over."""
        self.state.reset()
        self.flows.reset()
        self.context.reset()
        self.scratchpad.clear()
        self.artifacts.clear()
        self._seed_session()
        if self.conversation_id:
            path = _SESSIONS_DIR / self.conversation_id
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True)
