from __future__ import annotations

from types import MappingProxyType

from backend.components.dialogue_state import DialogueState
from backend.components.display_frame import DisplayFrame
from backend.components.flow_stack import FlowStack, flow_classes
from backend.components.context_coordinator import ContextCoordinator


class World:

    def __init__(self, config: MappingProxyType):
        self.config = config
        self.states: list[DialogueState] = []
        self.frames: list[DisplayFrame] = []
        self.flow_stack = FlowStack(config, flow_classes=flow_classes)
        self.context = ContextCoordinator(config)
        self._seed_session()

    def _seed_session(self):
        """Every session starts with an initial state, a default frame, and a
        system kickoff turn so the first user turn has turn_count = 1 and every
        downstream component can assume current_state() is non-None."""
        self.states.append(DialogueState(self.config))
        self.frames.append(DisplayFrame())
        self.context.add_turn('System', 'Session started.', 'system')

    def current_state(self) -> DialogueState:
        return self.states[-1]

    def latest_frame(self) -> DisplayFrame:
        return self.frames[-1]

    def insert_state(self, state: DialogueState) -> DialogueState:
        self.states.append(state)
        return state

    def insert_frame(self, frame: DisplayFrame) -> DisplayFrame:
        self.frames.append(frame)
        return frame

    def reset(self):
        self.states.clear()
        self.frames.clear()
        self.flow_stack._stack.clear()
        self.context.reset()
        self._seed_session()
