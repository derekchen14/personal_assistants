from __future__ import annotations

from types import MappingProxyType


class DialogueState:

    def __init__(self, config: MappingProxyType):
        self.config = config
        self.intent: str | None = None
        self.dax: str | None = None
        self.flow_name: str | None = None
        self.confidence: float = 0.0
        self.slots: dict = {}
        self.turn_count: int = 0
        self.top_predictions: list[dict] = []

        self.keep_going: bool = False
        self.has_issues: bool = False
        self.has_plan: bool = False
        self.natural_birth: bool = True

    def update(self, intent: str, dax: str, flow_name: str,
               confidence: float, slots: dict | None = None):
        self.intent = intent
        self.dax = dax
        self.flow_name = flow_name
        self.confidence = confidence
        self.slots = slots or {}
        self.turn_count += 1
        self.keep_going = False
        self.has_issues = False

    def update_flags(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def set_top_predictions(self, predictions: list[dict]):
        self.top_predictions = predictions[:3]

    def reset(self):
        self.intent = None
        self.dax = None
        self.flow_name = None
        self.confidence = 0.0
        self.slots = {}
        self.turn_count = 0
        self.top_predictions = []
        self.keep_going = False
        self.has_issues = False
        self.has_plan = False
        self.natural_birth = True

    def serialize(self) -> dict:
        return {
            'intent': self.intent,
            'dax': self.dax,
            'flow_name': self.flow_name,
            'confidence': self.confidence,
            'slots': self.slots,
            'turn_count': self.turn_count,
            'top_predictions': self.top_predictions,
            'keep_going': self.keep_going,
            'has_issues': self.has_issues,
            'has_plan': self.has_plan,
            'natural_birth': self.natural_birth,
        }

    @classmethod
    def from_dict(cls, data: dict, config: MappingProxyType) -> DialogueState:
        state = cls(config)
        state.intent = data.get('intent')
        state.dax = data.get('dax')
        state.flow_name = data.get('flow_name')
        state.confidence = data.get('confidence', 0.0)
        state.slots = data.get('slots', {})
        state.turn_count = data.get('turn_count', 0)
        state.top_predictions = data.get('top_predictions', [])
        state.keep_going = data.get('keep_going', False)
        state.has_issues = data.get('has_issues', False)
        state.has_plan = data.get('has_plan', False)
        state.natural_birth = data.get('natural_birth', True)
        return state
