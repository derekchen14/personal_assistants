import shutil
import threading
from pathlib import Path

from backend.components.task_artifact import TaskArtifact

_SESSIONS_DIR = Path(__file__).resolve().parents[2] / 'database' / 'sessions'


class World:
    """Hold one canonical reference to each module-owned component for shared access through the World."""
    def __init__(self, config, nlu, pex, mem):
        self.config = config
        self.artifacts: list[TaskArtifact] = []

        # Shared components
        self.state = nlu.dialogue_state
        self.ambiguity = nlu.ambiguity_handler
        self.flows = pex.flow_stack
        self.scratchpad = pex.session_scratchpad
        self.context = mem.context_coordinator
        self.prefs = mem.user_preferences
        self.knowledge = mem.business_knowledge

        # Let PEX wait for NLU to finish without polling the scratchpad.
        self.nlu_done = threading.Event()
        self.nlu_done.set()

        self.conversation_id: str | None = None
        self._seed_session()

    def _seed_session(self):
        """Seed a default artifact and system action so downstream components have usable initial values."""
        self.artifacts.append(TaskArtifact())
        initial_content = {'text': 'Session started.', 'activity': 'session_start', 'result': {}}
        self.context.add_turn('system', initial_content, turn_type='action')

    # ── Session-dir lifecycle ─────

    def open_session(self, conversation_id:str):
        """Bind the World to a session directory while preserving each component's live object."""
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
        """Reset every component in place and recreate the current session directory."""
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
