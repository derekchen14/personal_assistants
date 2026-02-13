import copy
from collections import defaultdict
from datetime import datetime as dt
from utils.help import dax2dact, dact2dax, dax2flow, dax2intent, flow2dax
from backend.components.engineer import PromptEngineer
from backend.components.ambiguity import Ambiguity
from backend.modules.flow.parents import BaseFlow

class DialogueState(object):

  def __init__(self, entities:list, intent:str='', dact:str='', dax:str='', thought='', score=0):
    # required elements
    self.entities = entities        # list of entities, where each entity is a dict with {tab, col, ver}
    self.current_tab = None         # current table name

    # optional elements
    self.intent = intent            # intent: Analyze, Visualize, Clean, Transform, Detect or Converse
    self.store_dacts(dact, dax)     # string of final dax or dact
    self.ambiguity = Ambiguity()    # object describing the level of uncertainty in the dialogue state

    # additional elements
    self.score = score
    self.thought = thought
    self.slices = {'metrics': {}, 'operations': [], 'preferences': []}
    self.flow_stack = []
    self.errors = []

    self.command_type = ''
    self.keep_going = True
    self.natural_birth = True
    self.has_staging = False
    self.has_issues = False     # issues entity stored in frame and unresolved rows in issue_df is > 0
    self.has_plan = False       # user needs to pick a plan of action
    self.timestamp = dt.now().strftime("%m/%d/%Y, %H:%M:%S")

  def __str__(self):
    entity_line = self.tab_col_rep()
    flow_lines = [str(flow) for flow in self.flow_stack]
    return "\n".join([entity_line, "* Flows:", *flow_lines])

  @staticmethod
  def entity_to_dict(entity_list, needs_verification=False):
    if needs_verification:
      entity_list = [entity for entity in entity_list if entity['ver']]

    entity_dict = defaultdict(list)
    for entity in entity_list:
      entity_dict[entity['tab']].append(entity['col'])
    return entity_dict

  @staticmethod
  def dict_to_entity(column_dict:dict) -> list:
    entities = []
    for tab_name, columns in column_dict.items():
      for col_name in columns:
        entities.append({'tab': tab_name, 'col': col_name, 'ver': False})
    return entities

  def tab_col_rep(self, with_break=False):
    tab_list = set([entity['tab'] for entity in self.entities])
    pred_tables = "; ".join(list(tab_list))

    column_dict = self.entity_to_dict(self.entities)
    pred_columns = PromptEngineer.column_rep(column_dict, with_break)
    return f"* Tables: {pred_tables}\n* Columns: {pred_columns}"

  def has_active_flow(self, size=0):
    return len(self.flow_stack) > size

  def get_flow(self, flow_type='', allow_interject=True, return_name=False):
    # find the first flow that meets all criteria, going in reverse since is it a stack
    if self.has_active_flow():
      if allow_interject and not flow_type:
        matched_flow = self.flow_stack[-1]
      else:
        matched_flow = next((
          flow for flow in reversed(self.flow_stack)
          if (not flow_type or flow.name() == flow_type) and
             (allow_interject or not flow.interjected)
        ), None)    # defaults to None if no flow matches the requirements

      if matched_flow:
        return matched_flow.name(full=True) if return_name else matched_flow
    return 'none' if return_name else None

  def get_dialog_act(self, form='hex'):
    if not hasattr(self, 'dax'):
      return None

    if form == 'list':
      return dax2dact(self.dax, form='list')
    elif form == 'string':
      return dax2flow(self.dax)
    elif form == 'hex':
      return self.dax
    return None  

  def store_dacts(self, dact='', dax=''):
    if len(dax) == 3:
      self.dax = dax
    elif len(dact) > 0:
      candidate_dax = flow2dax(dact)
      if candidate_dax != 'none':
        self.dax = candidate_dax
      else:
        self.dax = dact2dax(dact)
    else:
      raise ValueError("Dact and Dax cannot both be empty")

    self.intent = dax2intent(self.dax)

  @classmethod
  def from_dict(cls, labels:dict, active_table:str):
    label_parts = ['intent', 'dax', 'entities', 'thought', 'score']
    label_dict = {key: copy.deepcopy(labels[key]) for key in label_parts if key in labels}
    # limit to unique entities by storing the string versions as dictionary keys
    label_dict['entities'] = list({str(ent): ent for ent in label_dict['entities']}.values())

    state = cls(**label_dict)
    state.natural_birth = labels.get('natural_birth', True)
    state.current_tab = labels['entities'][0]['tab'] if len(labels['entities']) > 0 else active_table
    return state

  def serialize(self):
    """Serialize dialogue state object into a JSON-serializable format for database storage"""
    return {
      'intent': self.intent,
      'dax': self.dax,
      'flow_stack': BaseFlow.serialize_flow_stack(self.flow_stack)
    }