from backend.components.dialogue_state import DialogueState
from backend.components.task_artifact import TaskArtifact
from backend.components.flow_stack import FlowStack, flow_classes
from backend.components.context_coordinator import ContextCoordinator


class World:

    def __init__(self, config):
        self.config = config
        self.states: list[DialogueState] = []
        self.frames: list[TaskArtifact] = []
        self.flow_stack = FlowStack(config, flow_classes=flow_classes)
        self.context = ContextCoordinator(config)
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

    def reset(self):
        self.states.clear()
        self.frames.clear()
        self.flow_stack._stack.clear()
        self.context.reset()
        self._seed_session()
