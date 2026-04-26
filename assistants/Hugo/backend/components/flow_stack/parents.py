
class BaseFlow(object):"""
  Parent flow classes for Hugo (Blog Writing)."""
  def __init__(self):
    self.slots = {}
    self.tools = []
    self.interjected = False
    self.is_newborn = True
    self.is_uncertain = False

    self.fall_back = None
    self.stage = ''
    self.entity_slot = 'source'

    self.flow_id: str = ''
    self.plan_id: str | None = None
    self.turn_ids: list[str] = []
    # Plan flows might create a Flow and keep it pending
    self.status = 'Pending'  # Pending, Active, Completed, Invalid
    self.max_response_tokens = 4096

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

  def is_complete(self):
    return self.status == 'completed'

  def is_filled(self):
    for slot in self.slots.values():
      slot.check_if_filled()

    elective_slots = [s for s in self.slots.values() if s.priority == 'elective']
    at_least_one_elective = not elective_slots or any(s.filled for s in elective_slots)
    all_required = all(s.filled for s in self.slots.values() if s.priority == 'required')
    return all_required and at_least_one_elective

  def fill_slots_by_label(self, labels: dict):
    """System 1: Targeted single-slot fill from PEX label extraction.
    Labels format: {slot_name: extracted_value}
    Routes entity-slot values through validate_entity so domain parents
    can override for early validation (e.g. checking post existence)."""
    for slot_name, value in labels.items():
      if slot_name not in self.slots or value is None:
        continue
      if slot_name == self.entity_slot:
        entity = value if isinstance(value, dict) else {'post': str(value)}
        self.validate_entity(entity)
      else:
        self.fill_slot_values({slot_name: value})
    return self.is_filled()

  def fill_slot_values(self, values: dict):
    """Transfer prediction values onto slot objects."""
    if not values:
      return
    # Alias mapping: LLM may use common names that differ from slot names
    _ALIASES = {'title': 'target', 'post': 'source', 'post_id': 'source'}
    for slot_name, value in values.items():
      slot = self.slots.get(slot_name)
      if not slot:
        # Try alias
        alias = _ALIASES.get(slot_name)
        if alias:
          slot = self.slots.get(alias)
      if not slot or not value:
        continue
      # Dispatch based on value type and slot type
      st = getattr(slot, 'slot_type', '')
      if isinstance(value, list) and st in ('source', 'target', 'removal'):
        for item in value:
          if not item:
            continue
          if isinstance(item, dict):
            if not item.get('post'):
              continue
            slot.add_one(**item)
          else:
            slot.add_one(post=str(item))
      elif isinstance(value, list) and hasattr(slot, 'add_one') and st not in ('dictionary', 'range'):
        for item in value:
          slot.add_one(item)
      elif isinstance(value, dict) and st == 'dictionary':
        predefined = set(slot.value.keys()) if hasattr(slot, 'value') and isinstance(slot.value, dict) else set()
        if predefined == {'key', 'value'} and not any(k in predefined for k in value):
          # LLM returned {actual_key: actual_value} instead of {key: ..., value: ...}
          for k, v in value.items():
            slot.add_one(key='key', val=str(k))
            slot.add_one(key='value', val=str(v))
            break  # only first entry
        else:
          for k, v in value.items():
            slot.add_one(key=str(k), val=str(v))
      elif isinstance(value, dict) and hasattr(slot, 'add_one'):
        try:
          slot.add_one(**value)
        except TypeError:
          # Unknown keys in dict — extract post/sec if possible
          post = value.get('post', value.get('title', str(value)))
          sec = value.get('sec', value.get('section', ''))
          if st in ('source', 'target', 'removal'):
            slot.add_one(post=str(post), sec=str(sec))
          else:
            slot.add_one(str(post))
      elif hasattr(slot, 'assign_one'):
        slot.assign_one(value)
      elif hasattr(slot, 'add_one'):
        if st in ('source', 'target', 'removal'):
          slot.add_one(post=str(value))
        elif st == 'dictionary':
          slot.add_one(key=str(value), val='')
        elif st == 'range' and isinstance(value, str):
          slot.add_one(start=value)
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

  def validate_entity(self, entity):
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

class ResearchParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Research'


class DraftParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Draft'


class ReviseParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Revise'


class PublishParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Publish'


class ConverseParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Converse'


class PlanParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Plan'
