import re
from collections import defaultdict
from backend.modules.flow.formulas import Formula

class BaseSlot(object):
  def __init__(self, priority):
    self.filled = False
    self.uncertain = False
    self.criteria = 'single'
    self.priority = priority
    self.value = ''

  def __str__(self):
    if self.criteria == 'single':
      return f"{self.name}: {self.value}"
    elif self.criteria == 'multiple':
      return f"{self.name}: {self.values}"
    elif self.criteria == 'numeric':
      return f"{self.name}: {self.level}"

  def name(self):
    return self.slot_type

  def check_if_filled(self):
    self.filled = len(self.value) > 0
    return self.filled

  def reset(self):
    self.value = ''
    self.filled = False

class GroupSlot(BaseSlot):
  """ Slot values are a multiple items in list rather than a single string """
  def __init__(self, min_size, priority):
    super().__init__(priority)
    self.criteria = 'multiple'
    self.values = []
    self.size = min_size

  def __str__(self):
    return f"{self.name}: {self.values}"

  def check_if_filled(self):
    self.filled = len(self.values) >= self.size
    return self.filled

  def reset(self):
    self.values = []
    self.filled = False

    if hasattr(self, 'tab_cols'):
      self.tab_cols = []
    if hasattr(self, 'steps'):
      self.steps = []
    if hasattr(self, 'options'):
      self.options = []

class LevelSlot(BaseSlot):
  """ Slot values are a single number rather than a string """
  def __init__(self, priority, threshold, epsilon=0):
    super().__init__(priority)
    self.criteria = 'numeric'
    self.threshold = threshold if epsilon == 0 else threshold - epsilon
    self.level = 0.0
    self.inverse = False

  def check_if_filled(self):
    self.filled = self.level >= self.threshold
    return self.filled

  def reset(self, level=0.0):
    self.level = level
    self.filled = False

class SourceSlot(GroupSlot):
  """ Entities made up of existing tables and columns """
  def __init__(self, min_size, entity_part, priority='required'):
    super().__init__(min_size, priority)
    self.slot_type = 'source'
    self.tab_cols = []    # shortcut to avoid having to look up the table and columns in the values list
    self.active_tab = ''

    if min_size == 1:
      self.purpose = f"at least {min_size} {entity_part}"
    else:
      self.purpose = f"at least {min_size} {entity_part}s"

  def add_one(self, tab, col, row=-1, ver=False, rel=''):
    tab_name, column_name, row_name, verified, relation = tab, col, row, ver, rel
    tab_col = f"{tab_name}-{column_name}"
    alt_col = f"{self.active_tab}-{column_name}"

    if tab_col in self.tab_cols:
      tc_index = self.tab_cols.index(tab_col)
      self.values[tc_index]['row'] = row_name
      self.values[tc_index]['ver'] = verified
    elif alt_col in self.tab_cols:
      # if the new column is in the tab_cols list but with a different table, then we ignore the new column
      pass      # because the earlier table is the active one, which is more likely to be correct
    else:
      entity = {'tab': tab_name, 'col': column_name, 'row': row_name, 'ver': verified, 'rel': relation}
      self.values.append(entity)
      self.tab_cols.append(tab_col)
    self.check_if_filled()

  def replace_entity(self, old_tab, old_col, new_tab='', new_col=''):
    for index, entity in enumerate(self.values):
      if entity['tab'] == old_tab and entity['col'] == old_col:
        if len(new_tab) > 0:
          self.values[index]['tab'] = new_tab
        if len(new_col) > 0:
          self.values[index]['col'] = new_col
    self.tab_cols = [f"{ent['tab']}-{ent['col']}" for ent in self.values]

  def drop_unverified(self, conditional=False):
    # the conditional flag insures we only drop entities when at least one is verified
    verified = [ent for ent in self.values if ent['ver']]

    if conditional:
      if len(verified) > 0:
        self.values = verified
    else:
      self.values = verified  # which could be an empty list
    self.tab_cols = [f"{ent['tab']}-{ent['col']}" for ent in self.values]
    self.check_if_filled()

  def drop_ambiguous(self):
    self.values = [ent for ent in self.values if ent['rel'] != 'ambiguous']
    self.tab_cols = [f"{ent['tab']}-{ent['col']}" for ent in self.values]
    self.check_if_filled()

  def check_if_filled(self):
    self.filled = len(self.values) >= self.size
    return self.filled

  def is_verified(self):
    verified_entities = [ent for ent in self.values if ent['ver']]
    passes_verification = len(verified_entities) >= self.size
    return passes_verification

  def table_name(self):
    if len(self.values) > 0:
      return self.values[0]['tab']
    else:
      return 'N/A'

class TargetSlot(SourceSlot):
  """ Entities made up of new tables and columns, likely user-provided """
  def __init__(self, min_size, slot_type, priority='required'):
    super().__init__(min_size, slot_type, priority)
    self.slot_type = 'target'

class RemovalSlot(SourceSlot):
  """ For identifying which entities to remove from the data """
  def __init__(self, removal_type, priority='required'):
    super().__init__(1, removal_type, priority)
    self.slot_type = 'removal'
    self.rtype = "columns or cells" if removal_type == 'cells' else "rows or columns"
    self.purpose = f"target {self.rtype} to remove"

class FreeTextSlot(GroupSlot):
  """ List storage, often manifested as a Series of operations that can be applied to the data """
  def __init__(self, origins=None, priority='required'):
    super().__init__(1, priority)
    self.slot_type = 'freetext'
    self.purpose = 'SQL operations such filtering or grouping'
    self.verified = False
    self.origins = origins or []

  def extract(self, labels):
    if 'operations' in labels:
      for operation in labels['operations']:
        first_token = operation.split()[0]
        if first_token in self.origins:
          self.add_one(operation)

  def add_one(self, operation):
    if operation not in self.values:
      self.values.append(operation)

class ChecklistSlot(GroupSlot):
  """ Series of steps to take, where every step must be checked off in order to consider the slot verified
  Each step is a dict, where the keys within each step are 'name' indicating the dact, 'description' with actual details,
  and 'checked' indicating whether the step has been completed """
  def __init__(self, steps=None, priority='required'):
    super().__init__(1, priority)
    self.slot_type = 'checklist'
    self.purpose = 'a series of steps to check off in order to complete a task'
    self.steps = steps or []
    self.approved = False

  def check_if_filled(self):
    self.filled = self.size > 0 and len(self.steps) >= self.size
    return self.filled

  def is_verified(self):
    if self.filled:
      verified = all([step['checked'] for step in self.steps])
    else:
      verified = False
    return verified

  def mark_as_complete(self, step_name):
    for index, step in enumerate(self.steps):
      incomplete = step['checked'] == False
      if step['name'] == step_name and incomplete:
        self.steps[index]['checked'] = True
        break

  def current_step(self, detail=''):
    for step in self.steps:
      if not step['checked']:
        if len(detail) > 0:
          return step[detail]
        else:
          return step
    return ''

class ProposalSlot(GroupSlot):
  """ A list of possible options to select from, where at least 'min_size' must be selected to fill the slot
  Each option is a string, which is marked as selected by adding it to the values list """
  def __init__(self, options=None, priority='required'):
    super().__init__(1, priority)
    self.slot_type = 'proposal'
    self.purpose = 'keep track of which recommendations the user has selected'
    self.options = options or []

  def check_if_filled(self):
    enough_options = len(self.options) >= 2  # at least two options are available
    enough_selected = len(self.values) >= self.size
    self.filled = enough_options and enough_selected
    return self.filled

  def add_one(self, option):
    if option in self.options and option not in self.values:
      self.values.append(option)
    self.check_if_filled()

class RangeSlot(BaseSlot):
  """ Start and stop points for filtering data, often representing a date range """
  def __init__(self, options, priority='optional'):
    super().__init__(priority)
    self.slot_type = 'range'
    self.verified = False
    self.purpose = 'a time range to query over'

    self.time_len = 0  # Number of days back to look. If value is 0.5, then it is means so far (ie. month-to-date)
    self.unit = ''     # Unit of time, such as day, week, month or year
    self.range = {'start': None, 'stop': None}   # holds start and end points for any sort of interval
    self.entities = []
    self.recurrence = False

    if len(options) == 0:
      self.keywords = ['minute', 'hour', 'day', 'week', 'month', 'quarter', 'year']
      self.options = self.keywords + ['all']
    else:
      self.keywords = []
      self.options = options

  def add_one(self, start=None, stop=None, time_len=0, unit='', recurrence=False):
    if start:
      self.range['start'] = start
    if stop:
      self.range['stop'] = stop
    if time_len:
      self.time_len = time_len
    if unit in self.options:
      self.unit = unit
    if recurrence:
      self.recurrence = True
    return self.check_if_filled()

  def check_if_filled(self):
    contains_duration = bool(self.unit) and (self.time_len != 0)
    custom_range = bool(self.range['start']) and bool(self.range['stop'])
    self.filled = contains_duration or custom_range
    return self.filled

  def get_details(self):
    details = {
      'start': self.range['start'], 'stop': self.range['stop'],
      'time_len': self.time_len, 'unit': self.unit,
      'recurrence': self.recurrence
    }
    return details

  def get_description(self, message):
    if not self.filled: return message
    message += f" We have confirmed with the user that " if self.verified else f" We believe that "

    if self.unit == 'all':
      message += "we should query the entire dataset without filtering for any time range."
    else:
      message += f"the time range should be {self.range_to_nl()}"
      columns = [entity['col'] for entity in self.entities]
      message += f" according to the {' and '.join(columns)} columns." if len(columns) > 0 else "."

    return message

  def range_to_nl(self, time_range=None):
    if time_range:
      length, unit = time_range.split('-')
    else:
      length, unit = self.time_len, self.unit

    if length == -1 or unit == 'all':
      return "all time"
    elif length == 0.5:
      if unit in ['month', 'year']:
        return f"{unit}-to-date"
      else:
        return f"the current {unit}"
    elif length == 1:
      return f"the last {unit}"
    elif len(self.range) > 0:
      return f"from {self.range['start']} to {self.range['stop']}"
    else:
      return f"the last {length} {unit}s"

class ChartSlot(BaseSlot):
  """ Identifies a specific chart within the dashboard or interaction panel """
  def __init__(self, priority='required'):
    super().__init__(priority)
    self.slot_type = 'chart'
    self.purpose = 'a specific chart to interact with'
    self.chart_name = ''

  def assign_id(self, location, height=0, width=0, chart_name=''):
    if location in ['dashboard', 'panel']:
      identifier = f"{location}-{height}-{width}"
      self.value = identifier
    if len(chart_name) > 0:
      self.chart_name = chart_name
    self.check_if_filled()

class ExactSlot(BaseSlot):
  # Specific tokens, likely user-provided
  def __init__(self, priority='required'):
    super().__init__(priority)
    self.slot_type = 'exact'
    self.term = ''

    self.purpose = 'a specific term or phrase'

  def add_one(self, term):
    self.value = term
    self.term = term
    self.check_if_filled()

class FunctionSlot(BaseSlot):
  """ Contains a code related string, often written as Python """
  def __init__(self, priority='required'):
    super().__init__(priority)
    self.slot_type = 'function'
    self.purpose = 'a code function that processes or manipulates some data'
    self.str_rep = ''
    self.fuzzy = False

  def assign_one(self, function, str_rep='', fuzzy=False):
    self.value = function
    if len(str_rep) > 0:
      self.str_rep = str_rep

    self.fuzzy = fuzzy
    self.check_if_filled()

  def reset(self):
    self.value = None
    self.filled = False

  def check_if_filled(self):
    self.filled = self.value is not None and callable(self.value)
    return self.filled

class FormulaSlot(BaseSlot):
  """ Holds Formula objects which contain Expression and Clause attributes, used for queries """
  def __init__(self, priority='required'):
    super().__init__(priority)
    self.slot_type = 'formula'
    self.purpose = "a formula that calculates a marketing metric"
    self.formula = None

  def assign_metric(self, acronym, expanded):
    # metric names are acronyms such as Churn, LTV, CPA, or ROAS
    if len(acronym) > 0  and len(acronym) < 8 and len(expanded) > len(acronym):
      self.value = acronym
      self.formula = Formula(acronym, expanded)
    return self.check_if_filled()

  def is_initialized(self):
    return self.formula and len(self.value) > 0

  def check_if_filled(self):
    if self.is_initialized():
      if self.formula.expression is None:
        self.filled = False
      else:
        self.filled = len(self.formula.expression.relation) > 0 and len(self.formula.expression.variables) > 0
    else:
      self.filled = False
    return self.filled

  def is_populated(self, parent_var=None):
    if self.check_if_filled():
      if parent_var is None:
        parent_var = self.formula.expression
    else:
      return False

    # Base case: a clause is a valid leaf node
    if parent_var.pytype == 'Clause':
      return True
    # Base case: an expression without any children is not populated
    elif len(parent_var.variables) == 0:
      return False

    # Recursive case: check each child variable
    for child_var in parent_var.variables:
      if not self.is_populated(child_var):
        return False
    # If we reach this point, all children are populated
    return True

  def is_verified(self):
    passes_verification = True
    if self.is_populated():
      if not self.formula.verified:
        passes_verification = self.formula.expression.check_if_verified()
    else:
      passes_verification = False
    return passes_verification

class DictionarySlot(BaseSlot):
  """ Holds onto key value pairs, such as primary method and settings for resolving merge conflicts """
  def __init__(self, keys=[], priority='required'):
    super().__init__(priority)
    self.slot_type = 'dictionary'
    self.value = {key: '' for key in keys}
    self.purpose = "a method of comparison to resolve merge conflicts"

  def add_one(self, key, val):
    self.value[key] = val
    self.check_if_filled()

  def check_if_filled(self):
    if len(self.value) > 0:      # at least one key-value pair is available
      self.filled = True

      for key, val in self.value.items():   # and all values are non-empty
        if isinstance(val, str) and len(val) == 0:
          self.filled = False
    return self.filled

class CategorySlot(BaseSlot):
  """ Choose exactly one item from a predefined list of options """
  def __init__(self, options, priority='required'):
    super().__init__(priority)
    self.slot_type = 'category'
    self.options = options
    self.purpose = f"choose exactly one option from the set of: {options}"
    self.detail = ''

  def assign_multiple(self, options: list) -> bool:
    candidates = []
    for option in options:
      if option in self.options:
        candidates.append(option)
    if len(candidates) == 1:
      self.assign_one(candidates.pop())
    elif len(candidates) > 1:
      self.detail = candidates
      self.is_uncertain = True

    return self.check_if_filled()

  def assign_one(self, option: str) -> bool:
    if option in self.options:
      self.value = option
    return self.check_if_filled()

class ProbabilitySlot(LevelSlot):
  """ A numeric slot ranging from 0 to 1 """
  def __init__(self, priority='required', threshold=0.95):
    super().__init__(priority, threshold, epsilon=1e-4)
    self.slot_type = 'probability'
    self.purpose = 'a confidence score for moving forward automatically'

  def assign_one(self, probability):
    if probability >= 0 and probability <= 1:
      self.level = probability
    self.check_if_filled()

class ScoreSlot(LevelSlot):
  """ A numeric slot ranging that can hold negative values """
  def __init__(self, priority='required', threshold=1):
    super().__init__(priority, threshold)
    self.slot_type = 'score'
    self.purpose = 'a score for ranking or sorting'

  def assign_one(self, score):
    self.level = score
    self.check_if_filled()

class PositionSlot(LevelSlot):
  """ A numeric slots holding that holds non-negative integers """
  def __init__(self, priority='required', threshold=1, inverse=False):
    super().__init__(priority, threshold)
    self.slot_type = 'position'
    self.purpose = 'a position in a sequence'
    self.inverse = inverse

  def check_if_filled(self):
    activated = self.level >= 0
    if self.inverse:
      below = self.level < self.threshold
      self.filled = activated and below
    else:
      above = self.level >= self.threshold
      self.filled = activated and above
    return self.filled

  def assign_one(self, position):
    if position >= 0:
      self.level = position
    self.check_if_filled()
