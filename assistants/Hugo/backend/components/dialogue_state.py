import json
from pathlib import Path

from backend.components.flow_stack import FlowStack, flow_classes
from utils.helper import dax2flow

GROUNDING_PARTS = ('post', 'sec', 'snip', 'chl', 'ver')
_BELIEF_FIELDS = ('username', 'goal', 'confirmed', 'rejected', 'workflow_step',
                  'turn_count', 'has_issues')
_GROUNDED_SLOT_TYPES = ('source', 'target', 'removal', 'channel')


def normalize_slot_values(flow, slots:dict) -> dict:
    """Coerce LLM-authored write_state slot values into the flow's fill_slot_values
    vocabulary (tool arguments are genuinely unpredictable input).
    Multi-value slots accept a bare item in place of a list; checklist items may arrive as
    plain step names; source-family items may arrive as bare post references. Unknown slot
    names pass through untouched (fill_slot_values ignores them); PEX rejects them with a
    corrective tool error before write_state runs."""
    normalized = {}
    for slot_name, value in slots.items():
        slot = flow.slots.get(slot_name)
        if slot is None or slot.criteria != 'multiple':
            normalized[slot_name] = value
            continue
        items = value if isinstance(value, list) else [value]
        if slot.slot_type == 'checklist':
            items = [item if isinstance(item, dict) else {'name': item} for item in items]
        elif slot.slot_type in ('source', 'target', 'removal'):  # entity dicts, not strings
            items = [item if isinstance(item, dict) else {'post': item} for item in items]
        normalized[slot_name] = items
    return normalized


def rehydrate_flow(entry:dict):
    """Rebuild a BaseFlow from one flow_stack entry of the state file:
    instantiate from flow_classes, restore the lifecycle fields, then refill slots through
    the flow's own fill_slot_values so BaseFlow.to_dict / Slot.to_dict stays the single
    round-trip vocabulary."""
    flow = flow_classes[entry['flow_name']]()
    flow.flow_id = entry['flow_id']
    flow.status = entry['status']
    flow.stage = entry['stage']
    flow.turn_ids = list(entry['turn_ids'])
    flow.fill_slot_values(entry['slots'])
    flow.is_filled()  # recompute every slot's .filled after the refill
    return flow

class DialogueState:

    def __init__(self, intent, dax, turn_count, confidence=0.5):
        self.pred_intent = intent
        self.pred_flow = dax
        self.confidence: float = confidence
        self.pred_flows: list[dict] = []
        self.pred_slots: dict = {}
        self.turn_count: int = turn_count

        self.keep_going: bool = False
        self.has_issues: bool = False
        self.natural_birth: bool = True
        self.active_post: str | None = None

        self.slices = {'choices': [], 'channels': [], 'campaigns': []}

        # Per-session, file-backed form.
        self.conversation_id: str = ''
        self.username: str = ''
        self.goal: str = ''
        self.confirmed: list = []
        self.rejected: list = []
        self.workflow_step: int = 0
        self.grounding: dict = {'post': '', 'sec': '', 'snip': '', 'chl': '', 'ver': False}
        self.flow_stack: list[dict] = []

    def flow_name(self, string=False):
        if string:
            return self.top_pred_flow()
        return self.pred_flow

    def top_pred_flow(self):
        """The top-ranked predicted flow NAME — the singular accessor over the canonical
        `pred_flows` list (each entry carries its `votes` count). Falls back to the scalar
        pred_flow seed when there is no ensemble ranking yet (e.g. a freshly loaded state)."""
        if self.pred_flows:
            return self.pred_flows[0]['flow_name']
        return dax2flow(self.pred_flow) if self.pred_flow else None

    def reset(self):
        self.pred_intent = None
        self.pred_flow = None
        self.confidence = 0.0
        self.pred_flows = []
        self.pred_slots = {}
        self.turn_count = 0
        self.keep_going = False
        self.has_issues = False
        self.natural_birth = True
        self.active_post = None
        self.slices = {'choices': [], 'channels': [], 'campaigns': []}

    def serialize(self) -> dict:
        return {
            'pred_intent': self.pred_intent,
            'flow_name': self.pred_flow,
            'confidence': self.confidence,
            'pred_flows': self.pred_flows,
            'pred_slots': self.pred_slots,
            'turn_count': self.turn_count,
            'keep_going': self.keep_going,
            'has_issues': self.has_issues,
            'natural_birth': self.natural_birth,
            'active_post': self.active_post,
        }

    def serialize_session(self) -> dict:
        """The per-session state.json document. Extends the serialize()
        vocabulary: intent, turn_count, and has_issues keep their meanings."""
        session = {'conversation_id': self.conversation_id, 'username': self.username,
                   'turn_count': self.turn_count}
        beliefs = {'intent': self.pred_intent, 'pred_flows': self.pred_flows,
                   'confidence': self.confidence, 'pred_slots': self.pred_slots,
                   'goal': self.goal, 'confirmed': self.confirmed,
                   'rejected': self.rejected, 'workflow_step': self.workflow_step}
        flags = {'has_issues': self.has_issues}
        return {'session': session, 'user_beliefs': beliefs, 'grounding': dict(self.grounding),
                'flow_stack': self.flow_stack, 'flags': flags}

    def save(self, path):
        """Rewrite state.json — the single document form, one write per write_state."""
        Path(path).write_text(json.dumps(self.serialize_session(), indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path):
        """Rehydrate a per-session state from its state.json."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        session, beliefs = data['session'], data['user_beliefs']
        state = cls(intent=beliefs['intent'], dax=None, turn_count=session['turn_count'])
        state.pred_flows = beliefs['pred_flows']
        state.confidence = beliefs['confidence']
        state.pred_slots = beliefs['pred_slots']
        state.conversation_id = session['conversation_id']
        state.username = session['username']
        state.goal = beliefs['goal']
        state.confirmed = beliefs['confirmed']
        state.rejected = beliefs['rejected']
        state.workflow_step = beliefs['workflow_step']
        state.grounding = data['grounding']
        state.flow_stack = data['flow_stack']
        state.has_issues = data['flags']['has_issues']
        return state

    # ── read_state / write_state tool surfaces ─────────
    # These methods are the callable surface for the tool catalog.

    def read_state(self) -> dict:
        """The read_state tool surface: user beliefs, grounding, flow stack, and flags."""
        return self.serialize_session()

    def write_state(self, path, op, **kwargs) -> dict:
        """The write_state tool surface — the ONLY writer of state.json. Ops:
        'update'        mutate user-belief / grounding / flag fields (kwargs = fields),
        'update_flow'   mutate the top stack flow (slots= / stage= / status=; completion
                        is grounding-validated),
        'stackon'       push flow_name= with FlowStack semantics,
        'fallback'      replace the top flow with flow_name=,
        'pop_completed' remove Completed/Invalid flows, activating the next Pending one.
        Every op mutates the rehydrated stack or the state fields, then saves exactly once."""
        if op == 'update':
            self._apply_update(kwargs)
        elif op == 'update_flow':
            self._update_flow(kwargs)
        elif op in ('stackon', 'fallback', 'pop_completed'):
            self._run_stack_op(op, kwargs)
        else:
            raise ValueError(f'Unknown write_state op: {op!r}')
        self.save(path)
        return self.serialize_session()

    def _apply_update(self, fields:dict):
        for key, value in fields.items():
            if key == 'intent':
                self.pred_intent = value
            elif key == 'grounding':
                for part, val in value.items():
                    if part not in GROUNDING_PARTS:
                        raise KeyError(f'Unknown grounding part: {part!r}')
                    self.grounding[part] = val
            elif key in _BELIEF_FIELDS:
                setattr(self, key, value)
            else:
                raise KeyError(f'write_state update does not accept field {key!r}')

    def _update_flow(self, fields:dict):
        stack = self._rehydrate_stack()
        flow = stack.peek()
        if 'slots' in fields:
            flow.fill_slot_values(normalize_slot_values(flow, fields['slots']))
            flow.is_filled()
        if 'stage' in fields:
            flow.stage = fields['stage']
        if 'status' in fields:
            self._check_grounding(flow, fields['status'])
            flow.status = fields['status']
        self.flow_stack = stack.to_list()

    def _run_stack_op(self, op:str, kwargs:dict):
        stack = self._rehydrate_stack()
        if op == 'stackon':
            stack.stackon(kwargs['flow_name'])
        elif op == 'fallback':
            stack.fallback(kwargs['flow_name'])
        else:
            stack.pop_completed()
        self.flow_stack = stack.to_list()

    def _rehydrate_stack(self) -> FlowStack:
        """Load the flow_stack block into a live FlowStack (load → mutate → save)."""
        stack = FlowStack({}, flow_classes=flow_classes)
        stack._stack = [rehydrate_flow(entry) for entry in self.flow_stack]
        return stack

    def _check_grounding(self, flow, status:str):
        """An entity-grounded flow cannot reach Completed while grounding.post is
        empty — write_state validates, it does not patch."""
        if status != 'Completed' or flow.intent == 'Converse':
            return
        if flow.slots[flow.entity_slot].slot_type in _GROUNDED_SLOT_TYPES and not self.grounding['post']:
            raise ValueError(f'write_state: entity-grounded flow {flow.name()!r} cannot '
                             f'reach Completed while grounding.post is empty')

    @classmethod
    def from_dict(cls, data: dict):
        state = cls(
            intent=data.get('pred_intent'),
            dax=data.get('flow_name'),
            turn_count=data.get('turn_count', 0),
            confidence=data.get('confidence', 0.5),
        )
        state.pred_flows = data.get('pred_flows', [])
        state.pred_slots = data.get('pred_slots', {})
        state.keep_going = data.get('keep_going', False)
        state.has_issues = data.get('has_issues', False)
        state.natural_birth = data.get('natural_birth', True)
        state.active_post = data.get('active_post')
        return state
