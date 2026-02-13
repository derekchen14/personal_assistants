from datetime import datetime as dt
from enum import Enum

from backend.prompts.general import system_prompt, persona_messages
from backend.assets.ontology import date_mappings
from backend.components.preferences import UserPreferences
from backend.components.engineer import PromptEngineer

class Context(object):

  def __init__(self, verbose):
    self.verbose = verbose
    self.look_back = 7
    self.preferences = UserPreferences()

    self.history = []      # list of all previous turns
    self.recent = []       # the most recent look_back turns that are utterance type
    self.num_utterances = 0
    self.bookmark = 0

    self.completed_flows = []
    self.last_actions = {'User': [], 'Agent': []}
    self.available_data = ['Shoe Store Sales', 'E-commerce Web Traffic', 'Customer Integration']

  def last_utt(self, speaker='', text_only=True):
    # returns the most recent utterance with specified speaker
    for turn in reversed(self.recent):
      if len(speaker) == 0 or speaker == turn.speaker:
        utterance = turn.utt(for_api=False, as_dict=True)
        return utterance['text'] if text_only else utterance
    # if none found
    return '' if text_only else {}

  def compile_history(self, look_back=5, keep_system=True):
    # given the number of turns back to look, returns a string of the recent conversation history
    if look_back <= 7:
      historic_utterances = []
      for turn in self.recent:
        utterance = turn.utt(for_api=False)
        historic_utterances.append(utterance)
    else:
      historic_utterances = self.full_conversation(keep_system=keep_system)

    recent_utterances = historic_utterances[-look_back:]
    convo_history = '\n'.join(recent_utterances)
    return convo_history

  def rewrite_history(self, revised_utterance):
    # rewrite the most recent utterance with the revised utterance
    self.recent[-1].add_revision(revised_utterance)

  def set_bookmark(self, speaker=''):
    if len(speaker) > 0:
      for turn in reversed(self.history):
        if turn.speaker == speaker:
          self.bookmark = turn.turn_id
    else:
      self.bookmark = self.recent[-1].turn_id

  def find_action_by_name(self, action_name):
    # return a Turn object
    for turn in reversed(self.history):
      if turn.type == 'action' and turn.action == action_name:
        return turn
    return {}

  def find_turn_by_id(self, turn_id=-1, clear_bookmark=False):
    if turn_id < 0:
      turn_id = self.bookmark if self.bookmark > 0 else self.num_utterances
    if clear_bookmark:
      self.bookmark = 0

    if turn_id > self.num_utterances:
      raise IndexError(f"ERROR: turn id {turn_id} is out of range")
    for turn in self.history:
      if turn.turn_id == turn_id:
        return turn

  def store_completed_flows(self, completed_flows):
    # we store the name of the completed flows, rather than the flow objects themselves
    self.completed_flows = [flow.name() for flow in completed_flows]

  def contains_keyword(self, keyword, look_back=3):
    # check if the keyword is mentioned in the most recent look_back turns
    if ' ' in keyword:
      tokens = keyword.split()
    elif '-' in keyword:
      tokens = keyword.split('-')
    elif '_' in keyword:
      tokens = keyword.split('_')
    else:
      tokens = [keyword]

    for turn in self.recent[-look_back:]:
      # check that all tokens are found in the turn
      if all([token.lower() in turn.text.lower() for token in tokens]):
        return True
    return False

  def full_conversation(self, for_api=False, keep_system=True, as_dict = False):
    """
    Returns all utterances
    :param for_api: if true, produces utterance as {'role': speaker.lower(), 'content': text}.
    if false, the output is determined by as_dict
    :param keep_system: including utterances produced by System
    :param as_dict: if true, produces utterance as {'speaker': speaker, 'text': text, 'turn_id': turn_id}
    if false, produces utterance as a String
    :return: a list of what's defined by the parameters above
    """
    # Convenience function for getting utterance-related turns, we can speed this
    # up from O(n) to O(1), but even for a 100 turn histories, it's not too bad
    utterances = []
    allowed_speakers = ['User', 'Agent']
    if keep_system:
      allowed_speakers.append('System')

    for turn_index, turn in enumerate(self.history):
      if turn.type == 'utterance' and turn.speaker in allowed_speakers:
        utterance = turn.utt(for_api, as_dict)
        if turn_index == 0 and turn.speaker == 'System' and for_api:
          persona = "\n".join(persona_messages)
          utterance['content'] = persona + "\n" + utterance['content']
        utterances.append(utterance)
    return utterances

  def actions_include(self, target_actions, speaker='Agent'):
    # check if the last actions by the speaker include any of the target actions
    for ta in target_actions:
      if ta in self.last_actions[speaker]:
        return True
    return False

  def add_actions(self, actions:list, actor:str):
    self.last_actions[actor] = []  # clear out previous actions

    for action in actions:
      new_turn = self.add_turn(actor, action, 'action')
      self.last_actions[actor].append(new_turn.action)

  def check_user_preferences(self, endorsed=False, filled=False, verified=False):
    # assumng a preference is relevant, check if the preference is endorsed, filled, or verified as needed
    # returns the preference object if it matches all the required criteria, otherwise returns None
    user_pref = self.find_relevant_preference()

    if not user_pref:
      return None
    if endorsed and not user_pref.endorsed:
      return None
    if filled and len(user_pref.entity) == 0:
      return None
    if verified and not user_pref.entity['ver']:
      return None
    return user_pref

  def find_relevant_preference(self):
    # check the existing preferences to see if any preferences relevant to the current conversation
    for speaker in ['User', 'Agent']:
      text = self.last_utt(speaker=speaker)
      pref_name = self.preferences.related_to_pref(text)
      if pref_name:
        return self.preferences.get_pref(pref_name, top_ranking=False)
    return None

  def write_pref_description(self):
    # write a description of the user preferences
    user_pref = self.find_relevant_preference()

    if user_pref and user_pref.top_rank(include_detail=True)['detail'] != '':
      pref_description = user_pref.make_prompt_fragment()
      pref_description += '\n'
    else:
      pref_description = ''
    return pref_description

  def revise_user_utterance(self, turns_back):
    back_index = turns_back + 1  # to include the agent turn, which was 0-indexed
    user_turn = self.recent[-back_index]
    if user_turn.speaker != 'User':
      return False

    # clear out all turns starting from the revised user turn
    self.num_utterances = user_turn.turn_id
    self.recent = self.recent[:-back_index]

    turn_index = self.history.index(user_turn)
    self.history = self.history[:turn_index]
    return True

  def add_turn(self, role, content, turn_type, revised=''):
    turn = Turn(role, content, turn_type, self.num_utterances)

    if self.verbose:
      if turn_type == 'action':
        print(f"  Added {content} action by {role}")
      elif role != 'System':
        print(f"  Added {role} utterance: {content}")
    if len(revised) > 0:
      turn.add_revision(revised)
    self.history.append(turn)

    if turn_type == 'utterance':
      self.num_utterances += 1
      if role != 'System':
        self.recent.append(turn)
        if len(self.recent) > self.look_back:
          self.recent.pop(0)

    return turn

  def update_turn(self, intents, gold_dacts=None, gold_action=None):
    # update the most recent utterance turn with the dact distribution
    turn = self.recent[-1]
    turn.intents = intents
    if gold_dacts is not None:
      turn.gold_dacts = gold_dacts
    if gold_action is not None:
      turn.gold_action = gold_action
    return turn

  def initialize_history(self, memory):
    sys_prompt = self.write_system_prompt(memory)
    self.add_turn('System', sys_prompt, 'utterance')
    memory.api.set_system_prompt(sys_prompt)

  def write_system_prompt(self, memory):
    date = dt.today()
    months = [m.title() for m in date_mappings['month']['%B'].keys()]
    self.date = { 'month': date.month, 'day': date.day, 'year': date.year }
    week_options = list(date_mappings['week']['%A'].keys())
    weekday = week_options[date.weekday()].title()
    time_desc = f"today is {weekday}, {months[date.month-1]} {date.day}, {date.year}"

    goal_str = memory.description.pop('goal', 'understand the data')
    task_desc = f"{memory.db_name}, where the user's goal is to {goal_str}"
    table_desc = "\n".join([desc for t_name, desc in memory.description.items()])

    user_preferences = self.preferences.get_pref('all')
    preference_desc = PromptEngineer.write_preference_desc(user_preferences)
    sys_prompt = system_prompt.format(
        db_meta=task_desc,
        table_meta=table_desc,
        time_meta=time_desc,
        year=date.year,
        pref_meta=preference_desc
    )
    return sys_prompt

class Turn(object):

  def __init__(self, role, content, turn_type, turn_id):
    self.type = turn_type
    self.turn_id = turn_id
    self.timestamp = dt.now().strftime("%m/%d/%Y, %H:%M:%S")
    self.intents = []  # list with predicted high level intents  (ignore low level intents for now)
    self.dact_distribution = []  # list with tuples of (dact, model, confidence score)

    if turn_type == 'utterance':
      self.speaker = role   # either User, Agent, or System
      self.text = content   # string
    elif turn_type == 'action':
      self.actor = role
      self.action_target(content)

    # turn is the result of rewriting a clarification question
    self.is_revised = False
    self.is_request = False
    # labels for training purposes
    self.gold_dacts = None    # just a list, since confidence scores are not needed
    self.gold_action = None   # string format

  def utt(self, for_api=True, as_dict=False):
    if self.type != 'utterance':
      if as_dict:
        return {'speaker': self.actor, 'action': self.action}
      else:
        return f"{self.actor}_Action: {self.action}"

    if for_api:
      if self.speaker == 'Agent':
        return {'role': 'assistant', 'content': self.text}
      else:     # GPT expects the speakers to be lowercase
        return {'role': self.speaker.lower(), 'content': self.text}
    else:
      if as_dict:
        return {'speaker': self.speaker, 'text': self.text, 'turn_id': self.turn_id}
      else:
        speaker, text = self.speaker.title(), self.text
        return f"{speaker}: {text}"

  def add_revision(self, revised):
    self.is_revised = True
    self.original = self.text
    self.text = revised

  def action_target(self, content):
    if "|" in content:
      action, target = content.split("|")
      self.action = action.strip()
      self.target = target.strip()
    else:
      self.action = content  # ANALYZE, VISUALIZE, TRANSFORM, CLEAN, CLARIFY, or RESOLVE
      self.target = 'table'


class Role(Enum):
  USER = 'User'
  # user utterances: "How much money did we make last month?", "Three weeks ago", "Yea, sure"
  # user actions: include selecting a column, filtering etc. by clicking on the web interface
  AGENT = 'Agent'
  # agent utterances: "We made $3,580 for Adidas shoes", "Here you go", "What is the time range?"
  # agent actions: filter a column, run sql query, display a visualization
  SYSTEM = 'System'
  # system utterances: "Sorry, your request cannot be completed at this time", "Sign up now!", alerts
  # system actions: Reset the cache, merge utterances through a rewrite, all others
