from __future__ import annotations

from types import MappingProxyType


class DialogueState:

    def __init__(self, config: MappingProxyType):
        self.config = config
        self.pred_intent: str | None = None
        self.flow_name: str | None = None
        self.confidence: float = 0.0
        self.pred_flows: list[dict] = []
        self.turn_count: int = 0

        self.keep_going: bool = False
        self.has_issues: bool = False
        self.has_plan: bool = False
        self.structured_plan: dict = {}
        self.natural_birth: bool = True
        self.active_post: str | None = None

    def update(self, pred_intent:str, flow_name:str, confidence:float):
        self.pred_intent = pred_intent
        self.flow_name = flow_name
        self.confidence = confidence
        self.turn_count += 1
        self.keep_going = False
        self.has_issues = False

    def update_flags(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)

    def reset(self):
        self.pred_intent = None
        self.flow_name = None
        self.confidence = 0.0
        self.pred_flows = []
        self.turn_count = 0
        self.keep_going = False
        self.has_issues = False
        self.has_plan = False
        self.structured_plan = {}
        self.natural_birth = True
        self.active_post = None

    def serialize(self) -> dict:
        return {
            'pred_intent': self.pred_intent,
            'flow_name': self.flow_name,
            'confidence': self.confidence,
            'pred_flows': self.pred_flows,
            'turn_count': self.turn_count,
            'keep_going': self.keep_going,
            'has_issues': self.has_issues,
            'has_plan': self.has_plan,
            'structured_plan': self.structured_plan,
            'natural_birth': self.natural_birth,
            'active_post': self.active_post,
        }

    @classmethod
    def from_dict(cls, data: dict, config: MappingProxyType) -> DialogueState:
        state = cls(config)
        state.pred_intent = data.get('pred_intent')
        state.flow_name = data.get('flow_name')
        state.confidence = data.get('confidence', 0.0)
        state.pred_flows = data.get('pred_flows', [])
        state.turn_count = data.get('turn_count', 0)
        state.keep_going = data.get('keep_going', False)
        state.has_issues = data.get('has_issues', False)
        state.has_plan = data.get('has_plan', False)
        state.structured_plan = data.get('structured_plan', {})
        state.natural_birth = data.get('natural_birth', True)
        state.active_post = data.get('active_post')
        return state
