import re
import numpy as np
import pandas as pd
import math
import random

from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from collections import Counter, defaultdict

from backend.prompts.for_experts import *
from backend.prompts.grounding import grounding_prompts
from backend.prompts.general import find_col_prompt

from utils.help import dax2dact, dact2dax, dax2intent, flow2dax
from database.tables import Utterance, Conversation, DialogueAct
from backend.components.engineer import PromptEngineer
from backend.utilities.search import *

class BaseExpert(object):

  def __call__(self, utterance):
    """ given the user utterance, returns predicted intent and dialogue state
    This is very simple for now since there is only a single high level action to
    predict with choices of [query, manipulate, report, and converse]"""
    raise NotImplementedError("should return prediction and score")

  def validate_dacts(self, pred_intent, dact_list, pred_score, model_name):
    # input is a dact in list form, first we convert to dact_string for validation, then
    # output is dact in hex form, along with associated confidence score
    if len(dact_list) == 0:
      if pred_intent == 'Analyze':
        dact_string = 'query + retrieve + update'     # insight
      elif pred_intent == 'Visualize':
        dact_string = 'plot'
      elif pred_intent == 'Clean':
        dact_string = 'update'
      elif pred_intent == 'Transform':                # connect
        dact_string = 'retrieve + update + multiple'
      elif pred_intent == 'Detect':
        dact_string = 'retrieve + update + user'      # resolve
      elif pred_intent == 'Converse':
        dact_string = 'chat'
      pred_score = 0.1

    else:
      if len(dact_list) > 3:
        pred_score = 0.1
      dact_string = ' + '.join(dact_list[:3])

    pred_score = min(round(pred_score, 3), 1.0)
    pred_dax = dact2dax(dact_string)
    if self.verbose:
      print(f"  Predicted dact by {model_name}: {dact_string}, ({pred_score})")
    return pred_dax, pred_score

class InContextLearner(BaseExpert):

  def __init__(self, args, api):
    self.verbose = args.verbose
    self.api = api
    self.version = 'claude-sonnet'

  def __call__(self, context, pred_intent='', prior_intent='', prior_dialog_act=''):
    convo_history = context.compile_history()
    prompt_override = {'role': 'system', 'content': "Please do not include any text or explanations before or after the structured output."}

    if len(pred_intent) == 0:
      prompt = intent_prompt.format(history=convo_history, previous_intent=prior_intent)
      raw_output = self.api.execute(prompt, sys_override=prompt_override)
      prediction = PromptEngineer.apply_guardrails(raw_output, 'json')
      pred_intent = prediction['target']
    dact_mapping = dialog_act_mappings[pred_intent]

    if prior_intent == 'Analyze' and prior_dialog_act != '':
      continuation_msg = continuation_snippet.format(dialog_act=prior_dialog_act)
    else:
      prior_dialog_act = 'N/A'
      continuation_msg = ''
    if pred_intent == 'Detect':
      condition = self.draft_the_condition(context, prior_dialog_act)

    match pred_intent:
      case 'Analyze': prompt = analyze_prompt.format(history=convo_history, continuation=continuation_msg, prior_target=prior_dialog_act)
      case 'Visualize': prompt = visualize_prompt.format(history=convo_history)
      case 'Clean': prompt = clean_prompt.format(history=convo_history)
      case 'Transform': prompt = transform_prompt.format(history=convo_history)
      case 'Detect': prompt = detect_prompt.format(history=convo_history, condition=condition)
      case 'Converse': prompt = converse_prompt.format(history=convo_history)
      case _: return 'unknown', '000', 0.0

    raw_output = self.api.execute(prompt, version=self.version, sys_override=prompt_override)
    prediction = PromptEngineer.apply_guardrails(raw_output, 'json')
    try:
      dact_token = prediction['target']
    except TypeError: # Basically json processing error
      dact_token = 'query'

    if dact_token == 'unsure':
      pred_dax ='9DF'
    else:
      pred_dax = dact_mapping.get(dact_token, '9DF')
      if pred_dax == 'ABC':
        pred_dax = self.pay_more_attention(context)
      elif pred_dax == 'DEF':
        pred_dax = self.express_an_opinion(context)
    dact_list = dax2dact(pred_dax, form='list')

    pred_dax, pred_score = self.validate_dacts(pred_intent, dact_list, 0.8, 'ICL')
    return pred_intent, pred_dax, pred_score

  def draft_the_condition(self, context, prior_target):
    if prior_target == '':
      condition = "this is the first agent turn in the conversation."
    elif prior_target in context.completed_flows:
      prior_actions = context.completed_flows       # prior_actions is a list, whereas prior_target is a string
      if len(prior_actions) == 1:
        condition = f"we just completed a '{prior_target}' action in the previous turn.\n"
        condition += f"If the user wants to continue, but with a different table or column, then it is very likely to still be '{prior_target}'."
      elif len(prior_actions) > 1:
        condition = f"we just completed the {prior_actions} actions in the previous turn.\n"
        condition += f"If the user wants to continue, but with a different table or column, then you can choose from the subset of {prior_actions}, rather than the full set of twelve options."
    else:
      condition = f"we are still in the middle of a '{prior_target}' action, carried over from the previous turn.\n"
      condition += "As such, it is very likely that the user wants to continue with the same action."

    return condition

  def pay_more_attention(self, context):
    prompt = attention_entity_prompt.format(history=context.compile_history())
    raw_pred = self.api.execute(prompt)
    match raw_pred:
      case 'table': return '00A'
      case 'row': return '00B'
      case 'column': return '00C'
      case _: return '00C'

  def express_an_opinion(self, context):
    prompt = express_an_opinion_prompt.format(history=context.compile_history())
    raw_pred = self.api.execute(prompt)
    match raw_pred:
      case 'confirm': return '00E'
      case 'deny': return '00F'
      case 'approve': return '09E'
      case 'doubt': return '09F'
      case _: return '00F'

  def predict_tab_and_col(self, context, last_state, world):
    tab_col_str = PromptEngineer.tab_col_rep(world)
    prompt = entity_prompt.format(valid_entities=tab_col_str, history=context.compile_history(look_back=3))
    raw_output = self.api.execute(prompt)
    prediction = PromptEngineer.apply_guardrails(raw_output, 'json')

    pred_entities = []
    for pred in prediction:
      if pred['table'] == 'all':
        for tab_name in world.valid_tables:
          pred_entities.append({'tab': tab_name, 'col': '*'})
      else:
        pred_tab = pred['table']
        for pred_col in pred['columns']:
          pred_entities.append({'tab': pred_tab, 'col': pred_col})

    if len(pred_entities) == 0:
      pred_entities.append({'tab': last_state.current_tab, 'col': '*'})
    return pred_entities

  def predict_table(self, state, world, context):
    tasks = {
      'format': "'s columns are being formatted",
      'insert': " is most appropriate for inserting the new column",
      'clean': "'s columns are being updated",
      'remove': " the column is being removed from",
    }
    valid_tabs = world.valid_tables
    flow = state.get_flow(allow_interject=False)
    pred_table = ''

    if flow and flow.parent_type == 'Transform':
      flow_task = tasks[flow.flow_type]
      history = context.compile_history(look_back=3)
      prompt = table_prompt.format(goal=flow_task, history=history, valid_tabs=valid_tabs)
      pred_table = self.api.execute(prompt)

    if pred_table not in valid_tabs:
      pred_table = world.default_table
    return pred_table

  def stream_entity_prediction(self, labels, history):
    valid_cols, valid_tabs, current_tab, prior_entities = labels['table_info']
    tab_col_str = f"* Tables: {valid_tabs}\n* Columns: {valid_cols}"
    intent, dax = labels['intent'], labels['dax']
    flow_prompts = grounding_prompts[intent]
    text_only = dax in ['002', '02D']

    if dax == '58A':
      prompt = flow_prompts[dax].format(tables=valid_tabs, preview=labels['preview'], history=history)
    elif intent == 'Detect':
      prompt = flow_prompts['46X'].format(curr_tab=current_tab, history=history, columns=valid_cols)
    elif dax in ['001', '003', '005', '006']:
      prompt = flow_prompts[dax].format(history=history, valid_tab_col=tab_col_str, prior_state=prior_entities)
    else:
      prompt = flow_prompts[dax].format(valid_tab_col=tab_col_str, current=current_tab, history=history)
    return self.api.stream_response(prompt, text_only=text_only)

  def stream_row_prediction(self, labels, frame, context, state):
    resolve_row_prompts, status = grounding_prompts['Detect'], ''
    convo_history = context.compile_history(look_back=3)

    for candidate_flow in reversed(state.flow_stack):
      if candidate_flow.parent_type == 'Detect':
        flow = candidate_flow    # get the resolve flow, not the transform flow
        break

    displayed_rows = frame.get_data(form='md')
    dax = flow2dax(frame.issues_entity['flow'])
    prompt = resolve_row_prompts[dax].format(history=convo_history, status=status, row_desc=displayed_rows)
    return self.api.stream_response(prompt)

  def find_related_columns(self, column, tablename, valid_col_dict):
    # transform valid_col_dict from a dictionary with lists into a string description
    valid_str = ""
    for table, cols in valid_col_dict.items():
      valid_str += f"{', '.join(cols)} in {table} table.\n"

    prompt = find_col_prompt.format(given_col=column, given_tab=tablename, options=valid_str)
    raw_pred = self.api.execute(prompt)
    prediction = PromptEngineer.apply_guardrails(raw_pred, 'json')

    if prediction['match'].startswith('no'):
      return 'no', 'no_table', 'no_column'
    else:
      m_column = prediction['output']['col'].strip()
      m_table = prediction['output']['tab'].strip()
    return prediction['match'], m_column, m_table

class FineTunedLearner(BaseExpert):

  def __init__(self, args, internal_api):
    self.model = internal_api  # Mixtral 7B
    self.verbose = args.verbose

  def __call__(self, context, target='dact', dact=None, intent=None):
    history = context.compile_history()
    if target == 'dact':
      pred_intent, dact_list, pred_score = self.model.execute(history, target)
      pred_dax, pred_score = self.validate_dacts(pred_intent, dact_list, pred_score, "Peft")
      return pred_intent, pred_dax, pred_score

    elif target == 'ops':
      history += f"\nIntent: {intent}; {dact}"
      pred_operations, pred_score = self.model.execute(history, target)
      return pred_operations, pred_score

class LogisticRegression(BaseExpert):
  def __init__(self, args, internal_api):
    self.model = internal_api
    self.verbose = args.verbose

  def __call__(self, context, target='logreg'):
    history = context.compile_history()
    pred_intent, pred_dax, pred_score = self.model.execute(history, target)
    if self.verbose:
      print(f"  Predicted dact by {target}: {pred_dax}, ({pred_score})")
    return pred_intent, pred_dax, pred_score

class EmbeddingRetriever(BaseExpert):

  def __init__(self, args, intent_data, storage_db):
    self.verbose = args.verbose
    self.distance = 'cosine'
    # use approximate nearest neighbor search with HNSW, rather than exact search
    self.use_ann = True  # Storage(pgvector=True)
    self.database = storage_db
    self.model = SentenceTransformer('all-MiniLM-L12-v2')  # 'all-MiniLM-L12-v2'
    self.intent_ontology = [intent['intent_name'] for intent in intent_data]

  def __call__(self, context):
    recent_history = context.compile_history(look_back=3)
    vector = self.model.encode(recent_history)
    neighbors = self.database.find_nearest(vector, limit=5)

    intent_predictions, dact_predictions = [], []
    for utt_nb, dact_nb in neighbors:
      iid = dact_nb.intent_id - 1  # the database is not 0-indexed
      intent = self.intent_ontology[iid]
      intent_predictions.append(intent)
      dact_predictions.append(dact_nb.dact)

    pred_intent = self.majority_vote(intent_predictions)
    intent_score = self.uniformity_score(intent_predictions)
    if self.verbose:
      print(intent_predictions)
      print(f"  Predicted intent by Embed: {pred_intent} ({intent_score})")

    dact_string = self.majority_vote(dact_predictions)
    dact_score = self.uniformity_score(dact_predictions)
    dact_list = dact_string.split(" + ")

    pred_dax, pred_score = self.validate_dacts(pred_intent, dact_list, dact_score, "Embed")
    return pred_intent, pred_dax, pred_score

  @staticmethod
  def majority_vote(predictions):
    # given a list of predicted values, returns the value in the list with the most votes
    pred_count = Counter(predictions)
    max_count = max(pred_count.values())
    max_vote = [k for k, v in pred_count.items() if v == max_count]
    max_pred = random.choice(max_vote) if len(max_vote) > 1 else max_vote[0]
    return max_pred

  @staticmethod
  def uniformity_score(preds):
    # returns a score between 0 and 1, roughly equivalent to the inverse of the entropy
    probabilities = [preds.count(pred) / len(preds) for pred in set(preds)]
    entropy = -sum([prob * math.log(prob, 2) for prob in probabilities])

    score = 1 / (entropy + 1e-6)  # 1e-6 is just epsilon to avoid division by zero
    score /= len(set(preds))
    if score > 1:  # set a ceiling on the score to be 1
      score = 1
    return round(score, 3)

class RegularExpressionParser(BaseExpert):

  def __init__(self, threshold, verbose):
    self.threshold = threshold
    self.verbose = verbose
    self.command = "", ""

    self.select_keywords = ["who", "what", "when", "where", "how"]  # not 'why', that is analyze
    self.report_keywords = ["plot", "graph", "diagram", "figure", "chart"]
    self.clean_keywords = ["clean", "update", "change"]
    self.transform_keywords = ["delete", "remove", "insert"]
    self.integrate_keywords = ["merge", "integrate", "join"]
    self.converse_keywords = ["hello", "hey", "hi"]
    self.help_keywords = ["soleda", "kalli", "dana"]
    self.blank_keywords = ['null', 'blank row', 'empty row']
    self.concern_keywords = ['concern', 'outlier', 'anomal', 'date issue', 'location issue']
    self.typo_keywords = ['typo', 'spelling', 'misspell', 'misspelling']
    self.positive_keywords = ['yea', 'yes', 'sure']
    self.agree_to_look_phrases = ['show me', 'take a look', 'investigate']

  def __call__(self, context, previous_dax='000'):
    user_text = context.last_utt('User')

    pred_score = 0.2
    if len(user_text) <= 1:
      pred_intent, pred_dax = 'clarify', '000'
      pred_score += 0.8
    elif user_text.startswith("\\"):
      pred_intent, pred_dax, pred_score = self.handle_special_command(user_text, pred_score)

    if pred_score < 1.0:
      # if re.search(r'\bconnect\b', user_text):
      #   pred_intent, pred_dax, pred_score = 'Transform', '05B', 0.95
      # elif re.search(r'\bsave\b', user_text):
      #   pred_intent, pred_dax, pred_score = 'Transform', '58A', 0.95
      # else:
      #   pred_intent, pred_dax, pred_score = 'Analyze', '02D', 0.95
      if re.search(r'\bexactly\b', user_text):
        pred_intent, pred_dax, pred_score = 'Internal', '009', 0.95
      else:
        pred_intent, pred_dax, pred_score = self.regular_parsing(user_text, pred_score)

    pred_intent, pred_dax, pred_score = self.confusing_dacts(pred_intent, pred_dax, pred_score, previous_dax)
    pred_score = min(1.0, pred_score)
    if self.verbose:
      print(f"  Predicted intent by Regex: {pred_intent} ({pred_score})")
    return pred_intent, pred_dax, pred_score

  def handle_special_command(self, utterance, pred_score):
    pred_intent, pred_dax = "", ""
    raw_tokens = utterance.split()
    candidate_command = raw_tokens[0][1:]  # skip the first character, which we already know is '\'
    supported_commands = ['sql', 'python']

    if candidate_command in supported_commands:
      # Handle SQL code
      valid_query_start = utterance[5:11] == 'SELECT' or utterance[5:10] == 'WITH '
      if candidate_command == 'sql' and valid_query_start:
        self.command = 'sql', utterance[5:].strip()
        pred_intent = 'Analyze'
        pred_dax = 'FF1'  # fake query
        pred_score = 1.0
        return pred_intent, pred_dax, pred_score
      # Handle Python code
      if candidate_command == 'python' and utterance[5:7] == 'df':
        self.command = 'python', utterance[8:].strip()
        pred_intent = 'Clean'
        pred_dax = 'FF6'  # fake clean
        pred_score = 1.0
    elif re.match(r'^[0-9A-F]{3}$', candidate_command):
      # Handle Dev Mode by setting a golden dax
      self.command = 'dev_mode', utterance[5:].strip()
      pred_intent = 'unknown'
      pred_dax = candidate_command
      pred_score = 1.0

    return pred_intent, pred_dax, pred_score

  def confusing_dacts(self, pred_intent, current_dax, pred_score, previous_dax):
    if current_dax == '001' and previous_dax == '002':
      current_dax = '002'         # maintain the previous dax
    elif current_dax == '00E' and pred_intent == 'Detect':
      current_dax = previous_dax  # maintain the previous dax
    return pred_intent, current_dax, pred_score

  def regular_parsing(self, utterance, pred_score):
    tokens = utterance.lower().replace(".", " ").replace(",", " ").split()
    num_tokens = len(tokens)
    regex_preds = {'intent': 'Analyze', 'dacts': 'query', 'score': 0.2}

    for keyword in self.select_keywords:
      if keyword == tokens[0] and utterance.endswith("?"):
        regex_preds['score'] = self.threshold

    regex_preds = self.handle_keywords(regex_preds, self.clean_keywords, tokens, 'Clean', 'update')
    regex_preds = self.handle_keywords(regex_preds, self.transform_keywords, tokens, 'Transform', 'delete')
    regex_preds = self.handle_keywords(regex_preds, self.report_keywords, tokens, 'Visualize', 'plot')
    regex_preds = self.handle_keywords(regex_preds, self.blank_keywords, utterance, 'Detect', 'retrieve + update + row')
    regex_preds = self.handle_keywords(regex_preds, self.concern_keywords, utterance, 'Detect', 'retrieve + update + column')
    regex_preds = self.handle_keywords(regex_preds, self.typo_keywords, utterance, 'Detect', 'retrieve + update + multiple')

    for keyword in self.positive_keywords:
      if utterance.lower().startswith(keyword):
        for phrase in self.agree_to_look_phrases:
          if phrase in utterance.lower():
            return 'Converse', '00E', 0.9
    if 'duplicate' in tokens or 'duplicates' in tokens:
      regex_preds = {'intent': 'Clean', 'dacts': 'delete + row + multiple', 'score': 0.85}

    for keyword in self.integrate_keywords:
      if keyword in tokens:
        is_integration = False
        if 'columns' in tokens:
          is_integration = True
          regex_preds['dacts'] = 'insert + column'
        elif 'tables' in tokens:
          is_integration = True
          regex_preds['dacts'] = 'insert + table'
        if is_integration:
          regex_preds['intent'] = 'Transform'
          regex_preds['score'] = 0.85

    for keyword in self.help_keywords:
      if keyword in utterance.lower():
        regex_preds = {'intent': 'Converse', 'dacts': 'retrieve', 'score': 0.9}
    for keyword in self.converse_keywords:
      if keyword in tokens:
        regex_preds['intent'] = 'Converse'
        regex_preds['score'] += 0.1
        if num_tokens < 3:
          regex_preds['score'] += 0.1
        regex_preds['dacts'] = 'chat'

    pred_intent, pred_dacts, pred_score = regex_preds['intent'], regex_preds['dacts'], regex_preds['score']
    pred_dax = dact2dax(pred_dacts)
    return pred_intent, pred_dax, pred_score

  def handle_keywords(self, predictions, keywords, tokens, intent, dact_str):
    for keyword in keywords:
      if keyword in tokens:
        predictions['intent'] = intent
        predictions['dacts'] = dact_str
        predictions['score'] = 0.8
    return predictions