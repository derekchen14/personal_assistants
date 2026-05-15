from __future__ import annotations

from types import MappingProxyType

from backend.components.dialogue_state import DialogueState
from backend.components.task_artifact import TaskArtifact
from backend.components.flow_stack import FlowStack, flow_classes
from backend.components.context_coordinator import ContextCoordinator


class World:

    def __init__(self, config: MappingProxyType):
        self.config = config
        self.states: list[DialogueState] = []
        self.frames: list[TaskArtifact] = []
        self.flow_stack = FlowStack(config, flow_classes=flow_classes)
        self.context = ContextCoordinator(config)

    def current_state(self) -> DialogueState | None:
        return self.states[-1] if self.states else None

    def latest_artifact(self) -> TaskArtifact | None:
        return self.frames[-1] if self.frames else None

    def insert_state(self, state: DialogueState) -> DialogueState:
        self.states.append(state)
        return state

    def insert_artifact(self, artifact: TaskArtifact) -> TaskArtifact:
        self.frames.append(artifact)
        return artifact

    def reset(self):
        self.states.clear()
        self.frames.clear()
        self.flow_stack.clear()
        self.context.reset()
