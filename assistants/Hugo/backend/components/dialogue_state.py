import json
from pathlib import Path

from backend.components.flow_stack import flow_classes
from utils.helper import dax2flow

ENTITY_PARTS = ('post', 'sec', 'snip', 'chl', 'ver')
GROUNDING_PARTS = ('choices', 'notes', 'entities', *ENTITY_PARTS)
_BELIEF_FIELDS = ('username', 'goal', 'confirmed', 'rejected', 'workflow_step',
                  'turn_count', 'has_issues')
_GROUNDED_SLOT_TYPES = ('source', 'target', 'removal', 'channel')


def normalize_slot_values(flow, slots:dict) -> dict:
    """Coerce LLM-authored write_state slot values into the flow's fill_slot_values
    vocabulary (tool arguments are unpredictable input).
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
    round-trip vocabulary. Used at session load (World.open_session) and in serialization
    round-trip tests."""
    flow = flow_classes[entry['flow_name']]()
    flow.flow_id = entry['flow_id']
    flow.status = entry['status']
    flow.stage = entry['stage']
    flow.turn_ids = list(entry['turn_ids'])
    flow.fill_slot_values(entry['slots'])
    flow.is_filled()  # recompute every slot's .filled after the refill
    return flow

class DialogueState:
    """The ONE belief object, owned by NLU and shared through the World. It lives for the
    Assistant's lifetime and is never rebound — a new session calls reset(); the history of past
    predictions is MEM's record on disk, not a list of state objects."""

    def __init__(self, config):
        self.config = config
        self.reset()

    def reset(self):
        self.pred_intent = None
        self.pred_flow = None
        self.confidence: float = 0.0
        self.pred_flows: list[dict] = []
        self.pred_slots: dict = {}
        self.turn_count: int = 0

        self.keep_going: bool = False
        self.has_issues: bool = False
        self.natural_birth: bool = True

        # each entity for the blog domain is {post, sec, snip, chl, ver}
        # in most cases, there is only on active entity in the list
        self.grounding = {'choices': [], 'notes': [], 'entities': []}

        self.conversation_id: str = ''
        self.username: str = ''
        self.goal: str = ''
        self.confirmed: list = []
        self.rejected: list = []
        self.workflow_step: int = 0
        self.flow_stack: list[dict] = []  # saved copy of the FlowStack component (see write_state)

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
        }

    def save(self, path):
        """Rewrite state.json — the single document form, one write per write_state."""
        Path(path).write_text(json.dumps(self.read_state(), indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path):
        """Rehydrate a past session's state from its state.json — a MEM read of the disk record
        (a throwaway view object), never a rebind of the live world.state."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        session, beliefs = data['session'], data['user_beliefs']
        state = cls(config={})
        state.pred_intent = beliefs['intent']
        state.turn_count = session['turn_count']
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

    def get_active_post(self) -> str:
        return self.get_active_entity().get('post', '')

    def get_active_entity(self) -> dict:
        entities = self.grounding.get('entities') or []
        if not entities:
            return {}
        return {part: entities[0].get(part, False if part == 'ver' else '') for part in ENTITY_PARTS}

    def set_active_entity(self, **parts) -> dict:
        entity = self.get_active_entity() or {part: False if part == 'ver' else '' for part in ENTITY_PARTS}
        for part, value in parts.items():
            if part not in ENTITY_PARTS:
                raise KeyError(f'Unknown entity part: {part!r}')
            entity[part] = value
        entities = self.grounding.setdefault('entities', [])
        if entities:
            entities[0] = entity
        else:
            entities.append(entity)
        return entity

    def read_state(self) -> dict:
        """The read_state tool surface and the per-session state.json document: user beliefs,
        grounding, flow stack, and flags. Extends the serialize() vocabulary — intent, turn_count,
        and has_issues keep their meanings."""
        session = {'conversation_id': self.conversation_id, 'username': self.username,
                   'turn_count': self.turn_count}
        beliefs = {'intent': self.pred_intent, 'pred_flows': self.pred_flows,
                   'confidence': self.confidence, 'pred_slots': self.pred_slots,
                   'goal': self.goal, 'confirmed': self.confirmed,
                   'rejected': self.rejected, 'workflow_step': self.workflow_step}
        flags = {'has_issues': self.has_issues}
        return {'session': session, 'user_beliefs': beliefs, 'grounding': dict(self.grounding),
                'flow_stack': self.flow_stack, 'flags': flags}

    def write_state(self, path, op, stack=None, **kwargs) -> dict:
        """The write_state tool surface — the ONLY writer of state.json. Ops:
        'update'        change user-belief / grounding / flag fields (kwargs = fields),
        'update_flow'   change a flow in place at any depth (slots= / stage= / status=; flow_name=
                        targets a buried flow, blank means the top flow; completion is
                        grounding-validated),
        'stackon'       push flow_name= with FlowStack semantics (transfer= gates slot hand-over),
        'fallback'      replace the top flow with flow_name=,
        'pop'           remove Completed/Invalid flows, activating the next Pending one.
        `stack` is the FlowStack component — the one flow stack. Stack ops write to it directly;
        self.flow_stack is only a saved copy, refreshed from stack.to_list() before the save."""
        if op == 'update':
            self._apply_update(kwargs)
        elif op == 'update_flow':
            self._update_flow(stack, kwargs)
        elif op == 'stackon':
            stack.stackon(kwargs['flow_name'], transfer=kwargs.get('transfer', True))
        elif op == 'fallback':
            stack.fallback(kwargs['flow_name'])
        elif op == 'pop':
            stack.pop()
        else:
            raise ValueError(f'Unknown write_state op: {op!r}')
        if stack is not None:
            self.flow_stack = stack.to_list()
        self.save(path)
        return self.read_state()

    def _apply_update(self, fields:dict):
        for key, value in fields.items():
            if key == 'intent':
                self.pred_intent = value
            elif key == 'grounding':
                for part, val in value.items():
                    if part not in GROUNDING_PARTS:
                        raise KeyError(f'Unknown grounding part: {part!r}')
                    if part in ENTITY_PARTS:
                        self.set_active_entity(**{part: val})
                    else:
                        self.grounding[part] = val
            elif key in _BELIEF_FIELDS:
                setattr(self, key, value)
            else:
                raise KeyError(f'write_state update does not accept field {key!r}')

    def _update_flow(self, stack, fields:dict):
        """Normalize + validate, then delegate the write to FlowStack.update_flow — which reaches
        any depth via `flow_name` (blank = the top flow), unlike the top-only stack ops."""
        flow_name = fields.get('flow_name', '')
        flow = stack.find_by_name(flow_name) if flow_name else stack.get_flow()
        if not flow:  # LLM-authored flow_name — corrective error, not a crash
            raise ValueError(f'no live flow named {flow_name!r} on the stack')
        if 'status' in fields:  # validate first — a rejected write must not touch the live flow
            self._check_grounding(flow, fields['status'])
        slots = normalize_slot_values(flow, fields['slots']) if 'slots' in fields else None
        stack.update_flow(flow_name, slots=slots,
                          stage=fields.get('stage', ''), status=fields.get('status', ''))

    def _check_grounding(self, flow, status:str):
        """An entity-grounded flow cannot reach Completed while grounding.post is
        empty — write_state validates, it does not patch."""
        if status != 'Completed' or flow.intent == 'Converse':
            return
        if flow.slots[flow.entity_slot].slot_type in _GROUNDED_SLOT_TYPES and not self.get_active_post():
            raise ValueError(f'write_state: entity-grounded flow {flow.name()!r} cannot '
                             f'reach Completed while grounding.post is empty')
