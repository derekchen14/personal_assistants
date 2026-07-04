import shutil
from pathlib import Path

from backend.components.dialogue_state import DialogueState, rehydrate_flow
from backend.components.task_artifact import TaskArtifact
from backend.components.flow_stack import FlowStack, flow_classes
from backend.components.context_coordinator import ContextCoordinator
from backend.components.session_scratchpad import SessionScratchpad

_SESSIONS_DIR = Path(__file__).resolve().parents[2] / 'database' / 'sessions'


class World:

    def __init__(self, config):
        self.config = config
        self.states: list[DialogueState] = []
        self.frames: list[TaskArtifact] = []
        self.flow_stack = FlowStack(config, flow_classes=flow_classes)
        self.context = ContextCoordinator(config)
        self.scratchpad = SessionScratchpad(config)
        self.conversation_id: str | None = None
        self._seed_session()

    def _seed_session(self):
        """Every session starts with an initial state, a default artifact, and a
        system kickoff turn so the first user turn has turn_count = 1 and every
        downstream component can assume current_state() is non-None."""
        self.states.append(DialogueState(intent=None, dax=None, turn_count=0))
        self.frames.append(TaskArtifact())
        self.context.add_turn('System', 'Session started.', 'system')

    def current_state(self):
        return self.states[-1]

    def latest_artifact(self):
        return self.frames[-1]

    def insert_state(self, state):
        self.states.append(state)
        return state

    def insert_artifact(self, artifact):
        self.frames.append(artifact)
        return artifact

    # ── Session-dir lifecycle ─────

    def open_session(self, conversation_id:str) -> DialogueState | None:
        """Bind this World to a session. An existing dir reloads its state.json as the current
        state and rebuilds the flow stack from it; messages.jsonl is attached as the persistent
        message list; a fresh id defers dir creation to session_dir() (lazy, first turn)."""
        self.conversation_id = conversation_id
        session_path = _SESSIONS_DIR / conversation_id
        self.context.attach_messages(session_path / 'messages.jsonl')
        state_file = session_path / 'state.json'
        if state_file.exists():
            state = self.insert_state(DialogueState.load(state_file))
            self.flow_stack._stack = [rehydrate_flow(entry) for entry in state.flow_stack]
            return state
        return None

    def session_dir(self) -> Path:
        """database/sessions/<conversation_id>/ — created lazily on first access."""
        path = _SESSIONS_DIR / self.conversation_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def state_file(self) -> Path:
        return self.session_dir() / 'state.json'

    def reset(self):
        self.states.clear()
        self.frames.clear()
        self.flow_stack._stack.clear()
        self.context.reset()
        self.scratchpad.clear()
        self._seed_session()
        if self.conversation_id:
            path = _SESSIONS_DIR / self.conversation_id
            if path.exists():
                shutil.rmtree(path)
            path.mkdir(parents=True)

    def close(self):
        """Prune database/sessions/ to the most recent N sessions."""
        if not _SESSIONS_DIR.exists():
            return
        keep = self.config['session']['persistence']['max_sessions']
        sessions = sorted((path for path in _SESSIONS_DIR.iterdir() if path.is_dir()),
                          key=lambda path: path.stat().st_mtime, reverse=True)
        for stale in sessions[keep:]:
            shutil.rmtree(stale)
