import re

from backend.components.engineer import PromptEngineer
from backend.modules.flow.slots import *
from backend.modules.flow.parents import *
from backend.assets.ontology import common_abbreviations, valid_operations

# 6 Internal Flows
class ThinkFlow(InternalParentFlow):
  """ Generate a thought or call a stronger model to think deeper about a problem """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'think'    # {089}
    self.goal = 'think deeper about a problem'

    ops_phrases = valid_operations[self.flow_type]
    self.slots = {
      'source': SourceSlot(1, 'column'),          # name of table and columns to query
      'operation': FreeTextSlot(ops_phrases),     # operations to help determine filtering, grouping, and sorting
      'topics': FreeTextSlot([]) }                # topics to think about

class PeekFlow(InternalParentFlow):
  """ Allow the agent to peek at a few rows of the source or target columns before deciding what to do next """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'peek'    # {39B}
    self.goal = 'peek at a few rows of data to inform the next action'
    style_options = ['head', 'tail', 'sample']

    self.slots = {
      'source': SourceSlot(1, 'column'),          # entities to determine which columns to peek at
      'style': CategorySlot(style_options),       # which rows to peek at when pulling from the dataframe
      'size': PositionSlot('optional'),           # number of rows to peek at, defaults to 32 if not specified
      'task': FreeTextSlot([])                    # description of the task to improve based on the peek
    }

class ComputeFlow(InternalParentFlow):
  """ Perform arithmetic or data science computations that do not change the underlying data """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'compute'  # {129}
    self.goal = 'perform arithmetic calculations, solve word problems, or run data science tasks'
    task_options = ['correlation', 'calculator', 'comparison', 'classification']
    # correlation - input: question & table, output: number
    # calculator - input: question only, output: number
    # comparison - input: question & table, output: string
    # classification - input: question only, output: string

    self.slots = {
      'source': SourceSlot(0, 'column', 'optional'),  # name of table and columns to operate on
      'task': CategorySlot(task_options),             # the type of computation to perform
      'question': FreeTextSlot([])                    # description of the question to answer
    }

  def fill_slot_values(self, current_tab, prediction):
    """ Format of compute flow contemplation
    {
      "columns": [
        {"tab": "Bookings", "col": "PickupLocation"},
        {"tab": "Bookings", "col": "TotalAmount"}
      ],
      "output_type": "number"
    }
    """
    if len(prediction['columns']) == 0:  # table not needed
      if prediction['output_type'] == 'number':
        self.slots['task'].assign_one('calculator')
      elif prediction['output_type'] == 'string':
        self.slots['task'].assign_one('classification')

    else:
      for entity in prediction['columns']:
        self.slots['source'].add_one(**entity)
      if prediction['output_type'] == 'number':
        self.slots['task'].assign_one('correlation')
      elif prediction['output_type'] == 'string':
        self.slots['task'].assign_one('comparison')

    return self.is_filled()

class SearchFlow(InternalParentFlow):
  """ First search meta-data such as schema or issue information before moving forward """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'search'  # {149}
    self.goal = 'search meta-data such as schema or issue information before moving forward'
    meta_types = ['schema', 'problems', 'concerns', 'typos', 'blanks', 'convo', 'docs']

    self.slots = {
      'source': SourceSlot(1, 'column'),         # name of table and columns to query
      'target': CategorySlot(meta_types),        # the type of meta-data to search
    }

class StageFlow(InternalParentFlow):
  """ Combines query action and materialize view to stage a derived table for further analysis """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'stage'  # {19A}
    self.goal = 'create a temporary derived table for further analysis'

    self.slots = {
      'source': SourceSlot(2, 'column'),      # entities for filtering, grouping, and aggregation
      'target': TargetSlot(1, 'table'),       # name of the new table to create for staging
      'time': RangeSlot(options=[]) }         # optional time range for filtering the data

class ConsiderFlow(InternalParentFlow):
  """ First consider if any user preferences are relevant before taking the next action """
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'consider'   # {489}
    self.goal = 'look at user preferences before taking the next action'
    pref_options = ['goal', 'timing', 'caution', 'special', 'viz', 'metric', 'sig', 'search']

    self.slots = {
      'source': SourceSlot(1, 'column'),          # the table or column to describe
      'preference': CategorySlot(pref_options),   # the user preference to consider
      'task': FreeTextSlot([])                    # description of the task to improve based on the user preferences
    }
  
class UncertainFlow(InternalParentFlow):
  def __init__(self, valid):
    super().__init__(valid)
    self.flow_type = 'uncertain'     # {9DF}
    self.goal = 'clarify the user intent before taking the next action'

    self.slots = {
      'source': SourceSlot(2, 'column'),          # columns used to calculate the metric, notably not filled by the user
      'metric': CategorySlot([]),                 # the name of the metric the user wants to know more about
      'settings': DictionarySlot('optional') }    # any additional settings or parameters the user may have specified
