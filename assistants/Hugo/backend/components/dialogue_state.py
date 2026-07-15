import json
from pathlib import Path

ENTITY_PARTS = ('post', 'sec', 'snip', 'chl', 'ver')

class DialogueState:
    """The main object holding the assistant's belief, owned by NLU and shared through the World.
    It lives for the session lifetime and is not re-created per turn."""
    def __init__(self, config):
        self.config = config
        self.entity_parts = config['entity_parts']
        self.reset()

    def reset(self):
        """ each predicted flow is of the form: {
            'name': str,
            'dax': 3-digit str, 
            'confidence': float from 0.0 to 1.0
            'rationale' (optional): 'str'
        }  """
        self.pred_intent = ''  # from PEX
        self.pred_flows: list[dict] = []

        """ each entity for the blog domain is {post, sec, snip, chl, ver}
        In most cases, there is only on active entity in the list """
        self.grounding = {'choices': [], 'notes': [], 'entities': []}
        self.conversation_id: str = ''
        self.username = ''
        self.has_plan = False # signals that multiple flows are valid
        self.has_issues = False  # signals need for contemplation

    def flow_name(self, string=True, threshold=0.0):
        if (self.pred_flows) > 0:
            candidates = [flow for flow in self.pred_flows if flow['confidence'] > threshold]
            if string:
                return candidates[0]['name']
            else:
                return candidates[0]['dax']
        else:
            return None

    def save(self, path):
        """Rewrite state.json — the single document form, one write per write_state."""
        Path(path).write_text(json.dumps(self.read_state(), indent=2), encoding='utf-8')

    @classmethod
    def load(cls, path):
        """Rehydrate a past session's state from its state.json — a MEM read of the disk record
        (a throwaway view object), never a rebind of the live world.state."""
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        session, beliefs = data['session'], data['beliefs']
        state = cls(config={})
        state.pred_intent = beliefs['intent']
        state.pred_flows = beliefs['flows']
        state.conversation_id = session['conversation_id']
        state.username = session['username']
        state.has_plan = session['has_plan']
        state.has_issues = session['has_issues']
        state.grounding = data['grounding']
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
        # serialize and return the dialogue state
        beliefs = {'intent': self.pred_intent, 'flows': self.pred_flows}
        session = {'convo_id': self.conversation_id, 'username': self.username,
                    'has_plan': self.has_plan, 'has_issues': self.has_issues}
        state = {'session': session, 'beliefs': beliefs, 'grounding': self.grounding}
        return state