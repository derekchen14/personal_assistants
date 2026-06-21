import json
from pathlib import Path

from backend.components.flow_stack import FlowStack, flow_classes
from utils.helper import dax2flow

GROUNDING_PARTS = ('post', 'sec', 'snip', 'chl', 'ver')
_BELIEF_FIELDS = ('username', 'goal', 'confirmed', 'rejected', 'workflow_step',
                  'turn_count', 'has_issues', 'has_plan')
_GROUNDED_SLOT_TYPES = ('source', 'target', 'removal', 'channel')


def normalize_slot_values(flow, slots:dict) -> dict:
    """Coerce LLM-authored write_state slot values into the flow's fill_slot_values
    vocabulary (changes.md §3.3 — tool arguments are genuinely unpredictable input).
    Multi-value slots accept a bare item in place of a list; checklist items may arrive as
    plain step names; source-family items may arrive as bare post references. Unknown slot
    names pass through untouched (fill_slot_values ignores them, matching the in-memory
    stack); PEX rejects them with a corrective tool error before write_state runs."""
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
    """Rebuild a BaseFlow from one flow_stack entry of the state file (changes.md §5.2):
    instantiate from flow_classes, restore the lifecycle fields, then refill slots through
    the flow's own fill_slot_values so BaseFlow.to_dict / Slot.to_dict stays the single
    round-trip vocabulary."""
    flow = flow_classes[entry['flow_name']]()
    flow.flow_id = entry['flow_id']
    flow.status = entry['status']
    flow.stage = entry['stage']
    flow.plan_id = entry['plan_id']
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
        self.turn_count: int = turn_count

        self.keep_going: bool = False
        self.has_issues: bool = False
        self.has_plan: bool = False
        self.natural_birth: bool = True
        self.active_post: str | None = None

        self.slices = {'choices': [], 'channels': [], 'campaigns': []}

        # Per-session, file-backed form (changes.md §5.2) — orchestrator path only. The
        # per-turn fields above keep serving the old NLU→PEX→RES pipeline until cutover.
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

    def serialize_session(self) -> dict:
        """The per-session state.json document (changes.md §5.2). Extends the serialize()
        vocabulary: intent, turn_count, has_issues, and has_plan keep their meanings."""
        session = {'conversation_id': self.conversation_id, 'username': self.username,
                   'turn_count': self.turn_count}
        beliefs = {'intent': self.pred_intent, 'goal': self.goal, 'confirmed': self.confirmed,
                   'rejected': self.rejected, 'workflow_step': self.workflow_step}
        flags = {'has_issues': self.has_issues, 'has_plan': self.has_plan}
        return {'session': session, 'user_beliefs': beliefs, 'grounding': dict(self.grounding),
                'flow_stack': self.flow_stack, 'flags': flags}

    def save(self, path):
        """Rewrite state.json — the single document form, one write per write_state."""
        Path(path).write_text(json.dumps(self.serialize_session(), indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path):
        """Rehydrate a per-session state from its state.json (decision 11)."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        session, beliefs = data['session'], data['user_beliefs']
        state = cls(intent=beliefs['intent'], dax=None, turn_count=session['turn_count'])
        state.conversation_id = session['conversation_id']
        state.username = session['username']
        state.goal = beliefs['goal']
        state.confirmed = beliefs['confirmed']
        state.rejected = beliefs['rejected']
        state.workflow_step = beliefs['workflow_step']
        state.grounding = data['grounding']
        state.flow_stack = data['flow_stack']
        state.has_issues = data['flags']['has_issues']
        state.has_plan = data['flags']['has_plan']
        return state

    # ── read_state / write_state tool surfaces (changes.md §4.1, §6) ─────────
    # Tool-catalog wiring happens in Phase 2; these methods are the callable surface.

    def read_state(self) -> dict:
        """The read_state tool surface: user beliefs, grounding, flow stack, and flags."""
        return self.serialize_session()

    def write_state(self, path, op, **kwargs) -> dict:
        """The write_state tool surface — the ONLY writer of state.json. Ops:
        'update'        mutate user-belief / grounding / flag fields (kwargs = fields),
        'update_flow'   mutate the top stack flow (slots= / stage= / status=; completion
                        is grounding-validated per changes.md §6),
        'stackon'       push flow_name= (plan_id= optional) with FlowStack semantics,
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
            stack.stackon(kwargs['flow_name'], plan_id=kwargs.get('plan_id'))
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
        """changes.md §6: an entity-grounded flow cannot reach Completed while
        grounding.post is empty. Replaces the PEX post-hook has_issues flip on the
        orchestrator path — write_state validates, it does not patch."""
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
        state.keep_going = data.get('keep_going', False)
        state.has_issues = data.get('has_issues', False)
        state.has_plan = data.get('has_plan', False)
        state.natural_birth = data.get('natural_birth', True)
        state.active_post = data.get('active_post')
        return state
