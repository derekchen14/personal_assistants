"""
Parent flow classes for Kalli (Onboarding).

BaseFlow and InternalParentFlow are defined here (self-contained, no phantom imports).
Domain parents inherit from BaseFlow and override fill_slots_by_label for intent-specific
entity extraction patterns.
"""


class BaseFlow(object):
  def __init__(self):
    self.slots = {}
    self.tools = []
    self.completed = False
    self.interjected = False
    self.is_newborn = True
    self.is_uncertain = False

    self.fall_back = None
    self.stage = ''
    self.entity_slot = 'source'

    self.flow_id: str = ''
    self.status: str = ''
    self.plan_id: str | None = None
    self.turn_ids: list[str] = []
    self.result: dict | None = None

  @property
  def intent(self):
    return self.parent_type

  @property
  def flow_name(self):
    return self.flow_type

  def get(self, key, default=None):
    return getattr(self, key, default)

  def name(self, full=False):
    if full:
      return f'{self.parent_type}({self.flow_type})'
    return self.flow_type

  def __str__(self):
    parts = [f"{self.name(full=True)} >"]
    for slot_name, slot in self.slots.items():
      if slot.criteria == 'multiple':
        parts.append(f"{slot_name}: {slot.values}")
      elif slot.criteria == 'numeric':
        parts.append(f"{slot_name}: {slot.level}")
      elif slot.filled:
        parts.append(f"{slot_name}: {slot.value}")
    return ' '.join(parts)

  def is_filled(self):
    for slot in self.slots.values():
      slot.check_if_filled()

    elective_slots = [s for s in self.slots.values() if s.priority == 'elective']
    at_least_one_elective = not elective_slots or any(s.filled for s in elective_slots)
    all_required = all(s.filled for s in self.slots.values() if s.priority == 'required')
    return all_required and at_least_one_elective

  def fill_slots_by_label(self, labels):
    """System 1: Fast entity extraction from NLU prediction labels."""
    raise NotImplementedError

  def fill_slot_values(self, values: dict):
    """Transfer prediction values onto slot objects."""
    if not values:
      return
    _ALIASES = {'assistant': 'source', 'assistant_id': 'source'}
    for slot_name, value in values.items():
      slot = self.slots.get(slot_name)
      if not slot:
        alias = _ALIASES.get(slot_name)
        if alias:
          slot = self.slots.get(alias)
      if not slot or not value:
        continue
      st = getattr(slot, 'slot_type', '')
      if isinstance(value, list) and st in ('source', 'target', 'removal'):
        for item in value:
          if isinstance(item, dict):
            slot.add_one(**item)
          else:
            slot.add_one(ast=str(item))
      elif isinstance(value, dict) and st == 'dictionary':
        predefined = set(slot.value.keys()) if hasattr(slot, 'value') and isinstance(slot.value, dict) else set()
        if predefined == {'key', 'value'} and not any(k in predefined for k in value):
          for k, v in value.items():
            slot.add_one(key='key', val=str(k))
            slot.add_one(key='value', val=str(v))
            break
        else:
          for k, v in value.items():
            slot.add_one(key=str(k), val=str(v))
      elif isinstance(value, dict) and hasattr(slot, 'add_one'):
        try:
          slot.add_one(**value)
        except TypeError:
          ast = value.get('ast', value.get('assistant', str(value)))
          req = value.get('req', value.get('requirement', ''))
          if st in ('source', 'target', 'removal'):
            slot.add_one(ast=str(ast), req=str(req))
          else:
            slot.add_one(str(ast))
      elif hasattr(slot, 'assign_one'):
        slot.assign_one(value)
      elif hasattr(slot, 'add_one'):
        if st in ('source', 'target', 'removal'):
          slot.add_one(ast=str(value))
        elif st == 'dictionary':
          slot.add_one(key=str(value), val='')
        else:
          slot.add_one(value)
      else:
        slot.value = str(value)

  def slot_values_dict(self) -> dict:
    """Read filled slot values as a flat dict (for prompt serialization)."""
    return {
      sn: slot.to_dict() for sn, slot in self.slots.items()
      if slot.filled or (slot.criteria == 'multiple' and slot.to_dict())
         or (slot.criteria == 'numeric' and slot.to_dict())
    }

  def to_dict(self) -> dict:
    return {
      'flow_id': self.flow_id, 'flow_name': self.flow_type,
      'dax': self.dax, 'intent': self.parent_type,
      'status': self.status, 'slots': self.slot_values_dict(),
      'plan_id': self.plan_id, 'turn_ids': self.turn_ids,
    }

  def validate_entity(self, entity, current_context):
    """Add entity to the primary grounding slot. Override in domain parents for validation."""
    if self.entity_slot in self.slots:
      self.slots[self.entity_slot].add_one(**entity)

  def entity_values(self, size=False):
    values = self.slots[self.entity_slot].values
    return len(values) if size else values

  def needs_to_think(self):
    if self.is_uncertain or self.is_filled():
      return False
    return True

  def match_action(self, action_name):
    return action_name.startswith(self.parent_type.upper())


class InternalParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Internal'
    self.interjected = True
    self.origin = ''


# ── Domain Parents ───────────────────────────────────────────────────────

class ExploreParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Explore'

  def fill_slots_by_label(self, labels):
    """Explore flows expect NLU to identify assistant/spec entities."""
    current_context = labels.get('current_assistant', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_context)
    return self.is_filled()


class GatherParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Gather'

  def fill_slots_by_label(self, labels):
    """Gather flows expect NLU to identify scope/requirement entities."""
    current_context = labels.get('current_assistant', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_context)
    return self.is_filled()


class PersonalizeParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Personalize'

  def fill_slots_by_label(self, labels):
    """Personalize flows expect NLU to identify the assistant section to modify."""
    current_context = labels.get('current_assistant', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_context)
    return self.is_filled()


class DeliverParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Deliver'

  def fill_slots_by_label(self, labels):
    """Deliver flows expect NLU to identify the assistant and output format."""
    current_context = labels.get('current_assistant', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_context)
    return self.is_filled()


class ConverseParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Converse'


class PlanParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Plan'
