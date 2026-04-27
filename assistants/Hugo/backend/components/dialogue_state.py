from utils.helper import dax2flow

class DialogueState:

    def __init__(self, intent, dax, turn_count, confidence=0.5):
        self.pred_intent = intent
        self.pred_flow = dax
        self.confidence: float = confidence
        self.pred_flows: list[dict] = []
        self.turn_count: int = turn_count

        self.keep_going: bool = False
        self.has_issues: bool = False
        self.has_plan: bool = False
        self.natural_birth: bool = True
        self.active_post: str | None = None

        self.slices = {'choices': [], 'channels': [], 'campaigns': []}

    def flow_name(self, string=False):
        if string:
            return dax2flow(self.pred_flow)
        else:
            return self.pred_flow

    def reset(self):
        self.pred_intent = None
        self.pred_flow = None
        self.confidence = 0.0
        self.pred_flows = []
        self.turn_count = 0
        self.keep_going = False
        self.has_issues = False
        self.has_plan = False
        self.natural_birth = True
        self.active_post = None
        self.slices = {'choices': [], 'channels': [], 'campaigns': []}

    def serialize(self) -> dict:
        return {
            'pred_intent': self.pred_intent,
            'flow_name': self.pred_flow,
            'confidence': self.confidence,
            'pred_flows': self.pred_flows,
            'turn_count': self.turn_count,
            'keep_going': self.keep_going,
            'has_issues': self.has_issues,
            'has_plan': self.has_plan,
            'natural_birth': self.natural_birth,
            'active_post': self.active_post,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DialogueState':
        state = cls(
            intent=data.get('pred_intent'),
            dax=data.get('flow_name'),
            turn_count=data.get('turn_count', 0),
            confidence=data.get('confidence', 0.5),
        )
        state.pred_flows = data.get('pred_flows', [])
        state.keep_going = data.get('keep_going', False)
        state.has_issues = data.get('has_issues', False)
        state.has_plan = data.get('has_plan', False)
        state.natural_birth = data.get('natural_birth', True)
        state.active_post = data.get('active_post')
        return state
