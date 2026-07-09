import shutil
from pathlib import Path

from backend.components.task_artifact import TaskArtifact

_SESSIONS_DIR = Path(__file__).resolve().parents[2] / 'database' / 'sessions'


class World:
    """The shared component registry. Each module constructs and owns its components; the World
    holds one reference to each under its canonical name, so every module reaches foreign
    components the same way (world.state, world.flows, ...). NEVER REBIND these attributes — the
    single DialogueState and FlowStack live for the Assistant's lifetime and reset in place; the
    history of past sessions lives on disk (MEM's records), not in the World."""

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

        self.conversation_id: str | None = None
        self._seed_session()

    def _seed_session(self):
        """Every session starts with a default artifact and a system kickoff turn so the first
        user turn has turn_count = 1 and every downstream component can assume world.state and
        latest_artifact() are usable."""
        self.artifacts.append(TaskArtifact())
        self.context.add_turn('System', 'Session started.', 'system')

    def latest_artifact(self):
        return self.artifacts[-1]

    def insert_artifact(self, artifact):
        self.artifacts.append(artifact)
        return artifact

    # ── Session-dir lifecycle ─────

    def open_session(self, conversation_id:str):
        """Bind this World to a session dir. The components keep their live objects — looking at
        a PREVIOUS session's contents is MEM's job (read from disk), never a rebind here."""
        self.conversation_id = conversation_id
        session_path = _SESSIONS_DIR / conversation_id
        self.context.attach_messages(session_path / 'messages.jsonl')
        self.scratchpad.attach(session_path / 'scratchpad.jsonl')

    def session_dir(self) -> Path:
        """database/sessions/<conversation_id>/ — created lazily on first access."""
        path = _SESSIONS_DIR / self.conversation_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def state_file(self) -> Path:
        return self.session_dir() / 'state.json'

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

    def close(self):
        """Prune database/sessions/ to the most recent N sessions."""
        if not _SESSIONS_DIR.exists():
            return
        keep = self.config['session']['persistence']['max_sessions']
        sessions = sorted((path for path in _SESSIONS_DIR.iterdir() if path.is_dir()),
                          key=lambda path: path.stat().st_mtime, reverse=True)
        for stale in sessions[keep:]:
            shutil.rmtree(stale)
