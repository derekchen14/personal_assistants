"""
Parent flow classes for Hugo (Blog Writing).

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

  def fill_slot_values(self, context, memory):
    """System 2: Deeper contemplation to fill remaining slots."""
    raise NotImplementedError

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

class ResearchParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Research'

  def fill_slots_by_label(self, labels):
    """Research flows expect NLU to identify post/section entities.
    Label format: {"prediction": {"result": [{"tab": <post>, "col": <section>}]}}
    """
    current_context = labels.get('current_post', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_context)
    return self.is_filled()


class DraftParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Draft'

  def fill_slots_by_label(self, labels):
    """Draft flows expect NLU to identify the target post and section context."""
    current_context = labels.get('current_post', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_context)
    return self.is_filled()


class ReviseParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Revise'

  def fill_slots_by_label(self, labels):
    """Revise flows expect NLU to identify the post/section to revise."""
    current_context = labels.get('current_post', '')
    for entity in labels['prediction'].get('result', []):
      self.validate_entity(entity, current_context)
    return self.is_filled()


class PublishParentFlow(BaseFlow):
  def __init__(self):
    super().__init__()
    self.parent_type = 'Publish'

  def fill_slots_by_label(self, labels):
    """Publish flows expect NLU to identify the post and platform."""
    current_context = labels.get('current_post', '')
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
