"""
Parent flow classes for Dana (Data Analysis).

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
    for slot_name, value in values.items():
      slot = self.slots.get(slot_name)
      if not slot or not value:
        continue
      # Dict values → unpack as kwargs (e.g. SourceSlot entity dicts)
      if isinstance(value, dict) and hasattr(slot, 'add_one'):
        slot.add_one(**value)
      elif hasattr(slot, 'assign_one'):
        slot.assign_one(value)
      elif hasattr(slot, 'add_one'):
        st = getattr(slot, 'slot_type', '')
        if st == 'source':
          slot.add_one(tab=str(value), col='')
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

class CleanParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Clean'

  def fill_slots_by_label(self, labels):
    """Clean flows expect NLU to identify target table/column entities.
    Label format: {"prediction": {"action": "clear"|"peek"|"unsure", "target": [{"tab": ..., "col": ...}]}}
    """
    prediction = labels['prediction']
    if prediction['action'] == 'unsure':
      self.is_uncertain = True
      return self.is_filled()

    current_tab = labels.get('current_tab', '')
    for entity in prediction.get('target', []):
      if prediction['action'] == 'clear':
        entity['ver'] = True
      self.validate_entity(entity, current_tab)

    if prediction['action'] == 'peek':
      self.fall_back = 'peek'
    return self.is_filled()


class TransformParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Transform'

  def fill_slots_by_label(self, labels):
    """Transform flows expect NLU to identify source and target entities.
    Label format: {"prediction": {"result": [{"tab": ..., "col": ...}]}}
    """
    current_tab = labels.get('current_tab', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_tab)
    if self.entity_values(size=True) == 0:
      self.is_uncertain = True
    return self.is_filled()

  def needs_to_think(self):
    requires_thinking = self.is_uncertain
    self.is_uncertain = False
    for slot in self.slots.values():
      if slot.priority == 'required' and slot.criteria == 'multiple':
        if slot.filled:
          requires_thinking = any([not entity.get('ver', False) for entity in slot.values])
        else:
          requires_thinking = True
    return requires_thinking


class AnalyzeParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Analyze'

  def fill_slots_by_label(self, labels):
    """Analyze flows expect NLU to identify query entities.
    Label format: {"prediction": {"result": [{"tab": ..., "col": ..., "rel": "ambiguous"?}]}}
    """
    current_tab = labels.get('current_tab', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_tab)
      if entity.get('rel', '') == 'ambiguous':
        self.is_uncertain = True

    if 'operation' in self.slots:
      self.slots['operation'].extract(labels)
    return self.is_filled()


class ReportParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Report'

  def fill_slots_by_label(self, labels):
    """Report flows expect NLU to identify data entities for visualization."""
    current_tab = labels.get('current_tab', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_tab)
    if 'operation' in self.slots:
      self.slots['operation'].extract(labels)
    return self.is_filled()


class ConverseParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Converse'


class PlanParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Plan'
