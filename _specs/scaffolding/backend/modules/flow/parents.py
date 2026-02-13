import re
import random
from collections import Counter, defaultdict
from utils.help import dax2dact, dact2dax

from backend.components.engineer import PromptEngineer
from backend.modules.flow.slots import *
from backend.modules.experts.tracker import IssueTracker
from backend.utilities.search import find_nearest_valid_option

class BaseFlow(object):
  def __init__(self, valid):
    self.slots = {}
    self.completed = False
    self.interjected = False
    self.is_newborn = True
    self.is_uncertain = False

    self.fall_back = None
    self.verify_to_transfer = False
    self.stage = ''
    self.entity_slot = 'source'

    self.table_lookup = {col: tab for tab, cols in valid.items() for col in cols}
    self.valid_col_dict = valid

  @staticmethod
  def serialize_flow_stack(flow_stack):
    """Serialize flow stack objects into a JSON-serializable format"""
    serialized_flows = []
    for flow in flow_stack:
      flow_dict = {
        'name': flow.name(full=True),
        'completed': flow.completed,
        'interjected': flow.interjected,
        'entity_slot': flow.entity_slot,
        'valid_col_dict': flow.valid_col_dict,
        'slots': {}
      }
      
      # Serialize each slot using its own serialize method
      for slot_name, slot in flow.slots.items():
        flow_dict['slots'][slot_name] = slot.serialize()
      
      serialized_flows.append(flow_dict)
    return serialized_flows

  def name(self, full=False):
    if full:
      return f'{self.parent_type}({self.flow_type})'
    else:
      return self.flow_type

  def __str__(self):
    description = f"{self.name(full=True)} > "
    for slot_name, slot in self.slots.items():
      if slot_name == 'metric':
        if slot.formula:
          description += f"{slot_name} - {slot.formula.get_name(size='full')}; "
        else:
          description += f"{slot_name} - None; "
      elif slot_name == 'source':
        description += self.compile_source_description(slot)
      elif slot.criteria == 'multiple':
        description += f"{slot_name} - {self.values_string(slot.values)}; "
      elif slot.criteria == 'numeric':
        description += f"{slot_name} - {slot.level}; "
      elif slot.filled:               # criteria is 'single'
        description += f"{slot_name} - {slot.value}; "
    description = description[:-2]    # remove trailing comma
    return description

  def compile_source_description(self, slot):
    description = 'source - '
    if len(slot.values) == 0:
      description += 'None'
    else:
      unique_tables = set([entity['tab'] for entity in slot.values])
      for table_name in unique_tables:

        matching_columns = [entity['col'] for entity in slot.values if entity['tab'] == table_name]
        valid_columns = self.valid_col_dict.get(table_name, matching_columns)
        if len(matching_columns) == len(valid_columns):
          description += f"{table_name}: * columns, "
        else:
          description += f"{table_name}: {matching_columns}, "
      description = description[:-2]    # remove trailing comma

    description += '; '
    return description

  def values_string(self, values):
    simplified = []
    for value in values:
      sv = ''
      if isinstance(value, dict):
        if 'tab' in value.keys():
          table = value['tab']
          sv += f'tab: {table}, '
        if 'col' in value.keys():
          column = value['col']
          sv += f'col: {column}, '
        if 'row' in value.keys():
          row = value['row']
          if (isinstance(row, int) and row >= 0) or (isinstance(row, str) and len(row) > 0):
            sv += f'row: {row}, '
        if 'rel' in value.keys() and len(value['rel']) > 0:
          relation = value['rel']
          sv += f'rel: {relation}, '

        if len(sv) > 3:
          sv = sv[:-2]
        if 'ver' in value.keys() and value['ver']:
          verified = value['ver']
          sv += ' (verified)'

      if len(sv) == 0:
        sv = value
      simplified.append(sv)
    return simplified

  def is_filled(self):
    for slot in self.slots.values():
      slot.check_if_filled()

    elective_slots = [slot for slot in self.slots.values() if slot.priority == 'elective']
    if len(elective_slots) == 0:
      at_least_one_elective_filled = True
    else:
      at_least_one_elective_filled = any([slot.filled for slot in elective_slots])
    all_required_are_filled = all([slot.filled for slot in self.slots.values() if slot.priority == 'required'])

    return all_required_are_filled and at_least_one_elective_filled

  def fill_slots_by_label(self, current_tab, labels):
    """ System 1 thinking to ground the flow to the table and column entities """
    raise NotImplementedError

  def fill_slot_values(self, current_tab, raw_pred):
    """ System 2 contemplation with custom prompt predictions to fill slots """
    raise NotImplementedError

  def validate_entity(self, entity, current_tab, slot_name=''):
    """ entity is a dict of potential unconfirmed tabs and cols """
    # Get table name, either from entity or derive from column
    tab_name = entity.get('tab', '')
    if tab_name and tab_name != 'unsure':
      valid_tables = list(self.valid_col_dict.keys())
      tab_name = find_nearest_valid_option(tab_name, valid_tables)
    else:
      tab_name = self.column_to_table(entity['col'], current_tab)
    entity['tab'] = tab_name

    # Process columns if we have a valid table
    if tab_name and tab_name in self.valid_col_dict:
      slot_name = self.entity_slot if not slot_name else slot_name
      valid_columns = self.valid_col_dict[tab_name] + ['*']
      entity['col'] = find_nearest_valid_option(entity['col'], valid_columns)
      if len(entity['col']) > 0:
        if entity['col'] in valid_columns or slot_name == 'target':
          self.slots[slot_name].add_one(**entity)
        elif entity.get('rel', '') == 'ambiguous':
          ambiguous_entity = {'tab': tab_name, 'col': '*', 'rel': 'ambiguous'}
          self.slots[slot_name].add_one(**ambiguous_entity)

  def entity_values(self, size=False):
    stored_entities = self.slots[self.entity_slot].values
    if size:
      return len(stored_entities)
    else:
      return stored_entities

  def column_to_table(self, col_name, current_tab):
    # Safely get the valid column list for the current tab
    valid_col_list = self.valid_col_dict.get(current_tab, [])
    if col_name in valid_col_list:
      # prefer a match to the current table over any other
      tab_name = current_tab
    else:
      tab_name = self.table_lookup.get(col_name, '')
    return tab_name

  def match_action(self, action_name):
    flow_action = self.parent_type.upper()
    return action_name.startswith(flow_action)

  def needs_to_think(self):
    requires_thinking = True
    # When the flow is uncertain, then filling more slots is the least of our concerns
    # Separately, if the flow is already filled, then we don't need to think more
    if self.is_uncertain or self.is_filled():
      requires_thinking = False
    return requires_thinking

  def table_labels(self, first_only=False):
    # returns a string if first_only is True, otherwise a list of table names
    slot_name = self.entity_slot
    tabs = [entity['tab'] for entity in self.slots[slot_name].values]
    return tabs[0] if first_only else tabs

  def column_labels(self, with_tab=False, to_dict=False):
    cols = defaultdict(list) if to_dict else []
    slot_name = self.entity_slot

    for entity in self.slots[slot_name].values:
      col_name = f"{entity['tab']}.{entity['col']}" if with_tab else entity['col']

      if to_dict:
        cols[entity['tab']].append(col_name)
      else:
        cols.append(col_name)
    return cols

class AnalyzeParentFlow(BaseFlow):
  def __init__(self, valid):
    """ Defined by the appearance of a metric slot """
    super().__init__(valid)
    self.parent_type = 'Analyze'
    self.clarify_attempts = 0

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of Analyze flow output streams
    {"result": [
      {"tab": "Bookings", "col": "PickupLocation"},
      {"tab": "Bookings", "col": "TotalAmount"},
      {"tab": <table_name>, "col": <column_name>, "rel": "ambiguous"}
    ]}
    """
    for entity in labels['prediction']['result']:
      self.validate_entity(entity, current_tab)
      relation = entity.get('rel', '')
      if relation == 'ambiguous':
        self.is_uncertain = True

    if 'operation' in self.slots:
      self.slots['operation'].extract(labels)
    return self.is_filled()
  
  def fill_slot_values(self, current_tab, raw_pred):
    """ Format of flow contemplation is a list of operations
      [
        "filter month is March",
        "aggregate by count of shoes sold",
        "sort by date"
      ]
    """
    for pred_op in raw_pred:
      if pred_op == 'none' or pred_op == 'unsure':
        self.is_uncertain = True
        return False
      self.slots['operation'].add_one(pred_op)

    if not self.slots['operation'].check_if_filled():
      self.is_uncertain = True
    return self.is_filled()

  def generate_aliases(self, column_name):
    base_options = []
    base_options.append(column_name)
    if '_' in column_name:
      base_options.append(column_name.replace('_', ' '))
      base_options.append(column_name.replace('_', ''))
    # Split the string into words, where every capital letter starts a new word
    # this will over-split words like "CVR" or "LTV", but that's fine since we optimize for recall
    words = re.findall('[A-Z][^A-Z]*', column_name)
    base_options.append(' '.join(words))

    aliases = set()
    for base_opt in base_options:
      aliases.add(base_opt.upper())
      aliases.add(base_opt.lower())
      aliases.add(base_opt.title())
    return list(aliases)

class VisualizeParentFlow(BaseFlow):
  def __init__(self, valid):
    """ Defined by the visualization and dashboards """
    super().__init__(valid)
    self.parent_type = 'Visualize'
    self.entity_slot = 'chart'  

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of default Report flow output streams
    {"result": [
      {"tab": "CustOrders", "col": "OrderID"},
      {"tab": "CustOrders", "col": "CustomerID"},
      {"tab": "MarketingOffers", "col": "OrderKey"},
      {"tab": <table_name>, "col": <column_name>}
    ]}
    """
    for output in labels['prediction']['result']:
      self.validate_entity(output, current_tab)

    if 'operation' in self.slots:
      self.slots['operation'].extract(labels)
    return self.is_filled()

class CleanParentFlow(BaseFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.parent_type = 'Clean'
    self.code_generation = False
    self.tracker = IssueTracker()

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of format flow and validate flow outputs
    {
      "action": "clear",
      "target": [ {{"tab": "Subscriptions", "col": "PlanType"}} ]  # or
      "target": [ {{"tab": "CustomerOrders", "col": "OrderDate"}} ]
    }
    """
    prediction = labels['prediction']

    if prediction['action'] == 'clear':
      for entity in prediction['target']:
        entity['ver'] = True
        self.validate_entity(entity, current_tab)

    elif prediction['action'] == 'peek':
      for entity in prediction['target']:
        self.validate_entity(entity, current_tab)
      self.fall_back = '39B'

    elif prediction['action'] == 'unsure':
      self.is_uncertain = True
    return self.is_filled()

class TransformParentFlow(BaseFlow):
  def __init__(self, valid):
    """ Stages: pick-tab-col, merge-style, combine-cards, or combine-progress """
    super().__init__(valid)
    self.parent_type = 'Transform'
    self.code_generation = False

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of Merge flow output streams
    {"result": [
      {"tab": "CustomerContact", "col": "CustomerName"}
      {"tab": "CustomerContact", "col": "ContactNumber"}
    ]}
    """
    for entity in labels['prediction']['result']:
      self.validate_entity(entity, current_tab)
    if self.entity_values(size=True) == 0:
      self.is_uncertain = True
    return self.is_filled()

  def needs_to_think(self):
    requires_thinking = self.is_uncertain  # initialize based on uncertainty
    self.is_uncertain = False

    for slot in self.slots.values():
      if slot.priority == 'required' and slot.criteria == 'multiple':
        if slot.filled:
          # we should do more thinking if any of the entities are unverified
          requires_thinking = any([not entity['ver'] for entity in slot.values])
        else:
          requires_thinking = True
    return requires_thinking

class DetectParentFlow(BaseFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.parent_type = 'Detect'
    self.turns_taken = 0
    self.clarify_attempts = 0

    self.follow_up = {}
    self.scratchpad = []

  def needs_to_think(self):
    # Detection flows do not require contemplation
    return False

class IssueParentFlow(DetectParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.parent_type = 'Issue'

  def fill_slots_by_label(self, current_tab, labels):
    """ Format of Issue flow output streams
    {
      "table": "Promotions",
      "columns": ["DiscountAmount"]
    }
    """
    for col_name in labels['prediction']['columns']:
      self.validate_entity({'tab': labels['prediction']['table'], 'col': col_name}, current_tab)

    # default to the entire current table since Resolve Flow is non-destructive
    if self.entity_values(size=True) == 0:
      self.slots['source'].add_one(current_tab, '*')
    return self.is_filled()

  def fill_slot_values(self, raw_pred):
    """ Format of Typo flow to create a plan
    "plan": [
      "update - fix typos on city names (eg. Berkley -> Berkeley, Seatle -> Seattle), and convert abbreviations to full names (eg. SF -> San Francisco, LA -> Los Angeles)",
      "format - standardize city names to be properly capitalized with appropriate spacing (eg. SanJose -> San Jose)"
    ]
    """
    has_description = True
    for step in raw_pred['plan']:
      try:
        step_name, step_description = step.split(' - ')
        if step_description == 'unsure':
          has_description = False
        step_dict = {'name': step_name, 'description': step_description, 'checked': False}
      except ValueError:
        self.is_uncertain = True
        return False

      if step_name in self.plan_options:
        self.slots['plan'].steps.append(step_dict)
    return self.is_filled() and has_description

  def clear_all_issues(self):
    self.completed = True
    no_issues_step = {'name': 'ignore', 'description': 'No issues were detected', 'checked': True}
    self.slots['plan'].steps.append(no_issues_step)
    self.slots['plan'].check_if_filled()

  def suggest_replies(self):
    """ Replies are a list of dictionaries with keys 'dax', 'text', and 'action' """
    positive_reply = {'dax': '00E', 'text': f"Please show me the {self.flow_type}s", 'action': None}
    negative_reply = {'dax': '00F', 'text': "Let's ignore them", 'action': None}
    suggested_replies = [positive_reply, negative_reply]
    return suggested_replies

  def clarify_issue_resolution(self, issue_df, frame):
    """ Generate the clarification question to get user feedback on how to resolve the issues """
    col_name, issue_type = frame.issues_entity['col'], frame.issues_entity['flow']
    issue_count = self.MetaIssue.num_issue_rows(issue_df, col_name, issue_type)

    # default the description based on the issue type
    match issue_type:
      case 'concern': adjective = 'concerning'
      case 'blank': adjective = 'missing'
      case 'problem': adjective = 'problematic'
      case 'typo': adjective = 'misspelled'
    issue_desc = f"{adjective} value"

    # drill deeper if it's a concern
    if issue_type == 'concern':
      concern_rows = issue_df[(issue_df['column_name'] == col_name) & (issue_df['issue_type'] == 'concern')]
      unique_subtypes = concern_rows['issue_subtype'].unique().tolist()
      issue_desc = PromptEngineer.array_to_nl(unique_subtypes, connector='and')

    outcome = 'it' if issue_count == 1 else 'them'
    question = f"I found some {issue_desc}s in the {col_name} column. How would you like to fix {outcome}?"
    return question

  def describe_issues(self, issue_df, frame):
    """Generate string describing the number of each type of issue, separated by newlines"""
    col_name, issue_type = frame.issues_entity['col'], frame.issues_entity['flow']

    desc_lines = []
    for issue_subtype in self.issue_types:
      subtype_count = self.MetaIssue.num_issue_rows(issue_df, col_name, issue_type, issue_subtype)
      if subtype_count > 0:
        desc_lines.append(self.MetaIssue.type_to_nl(issue_subtype, subtype_count, 'digit'))
    description = PromptEngineer.array_to_nl(desc_lines, connector='and')
    return description

class InternalParentFlow(BaseFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.parent_type = 'Internal'
    self.interjected = True
    self.code_generation = False
    self.origin = ''    # dax of the flow that triggered this internal flow
