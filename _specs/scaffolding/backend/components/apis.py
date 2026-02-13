import os
import openai
import anthropic
import backoff
import time as tm
import torch

import requests
from dotenv import load_dotenv
from backend.constants import PROJECT_DIR

load_dotenv(os.path.join(PROJECT_DIR, 'backend', '.env'))  # take environment variables from .env.
openai.api_key = os.getenv("OPENAI_API_KEY")
anthropic.api_key = os.getenv("ANTHROPIC_API_KEY")

class ExternalAPI(object):

  def __init__(self, args):
    self.verbose = args.verbose
    self.default_version = args.api_version
    self.temp = args.temperature
    self.sys_prompt = {'role': 'system', 'content': ''}
    self.oai_client = openai.OpenAI()
    self.claude_client = anthropic.Anthropic()

  def completions_with_backoff(self, model_type, messages, max_tok, prefix):
    self.attempts += 1
    if model_type.startswith('gpt'):
      raw_generation = self.gpt_completions(model_type, messages, max_tok)
      completion = raw_generation.choices[0].message.content
    elif model_type.startswith('reasoning'):
      # raw_generation = self.o4_completions(model_type, messages, max_tok)
      # completion = raw_generation.choices[0].message.content
      raw_generation = self.reasoning_completions(messages, max_tok)
      completion = raw_generation.text
    elif model_type.startswith('claude'):
      raw_generation = self.claude_completions(model_type, messages, max_tok, prefix)
      completion = prefix + raw_generation.content[0].text
    return completion

  @backoff.on_exception(backoff.expo, openai.RateLimitError)
  def gpt_completions(self, model_type, messages, max_tok):
    raw_generation = self.oai_client.chat.completions.create(
      model=model_type,
      messages=messages,
      max_tokens=max_tok,
      temperature=self.temp
    )
    return raw_generation

  @backoff.on_exception(backoff.expo, anthropic.RateLimitError)
  def claude_completions(self, model_type, messages, max_tok, prefix):
    system_message = "Please do not include any text or explanations before or after the structured output."
    user_messages = []
    for message in messages:
      if message['role'] == 'system':
        system_message = message['content']
      else:
        user_messages.append(message)
    user_messages.append({'role': 'assistant', 'content': prefix})

    if 'sonnet' in model_type:
      model_version = 'claude-sonnet-4-0'
    else:
      model_version = 'claude-3-5-haiku-latest'

    raw_generation = self.claude_client.messages.create(
        model=model_version,
        system=system_message,
        messages=user_messages,
        max_tokens=max_tok,
        temperature=self.temp
    )

    if self.verbose:
      usage = raw_generation.usage
      print(f"Tokens used: {usage.output_tokens}/{max_tok} (input: {usage.input_tokens})")
    return raw_generation

  @backoff.on_exception(backoff.expo, anthropic.RateLimitError)
  def reasoning_completions(self, messages, max_tok):
    raw_generation = self.claude_client.messages.create(
        model='claude-sonnet-4-0',
        system="Please do not include any text or explanations before or after the JSON output.",
        thinking={"type": "enabled", "budget_tokens": 2048},
        messages=[message for message in messages if message['role'] == 'user'],
        max_tokens=max_tok+2048
    )

    for block in raw_generation.content:
      if block.type == 'thinking':
        print(block.thinking)
      if block.type == 'text':
        return block
    return raw_generation

  @backoff.on_exception(backoff.expo, openai.RateLimitError)
  def o4_completions(self, model_type, messages, max_tok):
    raw_generation = self.oai_client.chat.completions.create(
      model='o4-mini',
      reasoning_effort='low' if 'low' in model_type else 'medium',
      messages=[msg for msg in messages if msg['role'] != 'system'],
      max_completion_tokens=max_tok*2
    )
    return raw_generation

  def execute(self, prompt:str, prev_messages:list=[], max_tok:int=512, prefix="```", version='', sys_override=None):
    self.attempts = 0
    model_type = version if len(version) > 0 else self.default_version

    if len(prev_messages) > 0:
      if len(prompt) > 0:
        messages = [*prev_messages, {'role': 'assistant', 'content': prompt}]
      else:
        messages = prev_messages
    else:
      system_msg = sys_override if sys_override is not None else self.sys_prompt
      messages = [system_msg, {'role': 'user', 'content': prompt}]

    completion = self.completions_with_backoff(model_type, messages, max_tok, prefix)
    result = completion.strip()

    if self.verbose and self.attempts > 1:
      print(f"  API call attempts: {self.attempts}")
    return result

  def stream_response(self, prompt:str, prev_messages:list=[], text_only:bool=False, max_tok:int=512):
    if text_only:
      return self.stream_text_only(prompt, max_tok)
    elif self.default_version.startswith('gpt'):
      return self.stream_gpt(prompt, prev_messages, max_tok)
    elif self.default_version.startswith('claude'):
      return self.stream_claude(prompt, prev_messages, max_tok)

  def stream_gpt(self, prompt:str, prev_messages:list=[], max_tok:int=512):
    if len(prev_messages) > 0:
      messages = [*prev_messages, {'role': 'user', 'content': prompt}]
    else:
      messages = [self.sys_prompt, {'role': 'user', 'content': prompt}]

    stream = self.oai_client.chat.completions.create(
      model=self.default_version,
      messages=messages,
      max_tokens=max_tok,
      temperature=self.temp,
      stream=True
    )
    return stream

  def stream_claude(self, prompt:str, prev_messages:list=[], max_tok:int=512):
    prefill = {"role": "assistant", "content": '```json\n{\n  "'}
    if len(prev_messages) > 0:
      system_message = None
      convo_messages = [*prev_messages, {'role': 'user', 'content': prompt}, prefill]
    else:
      system_message = self.sys_prompt['content']
      convo_messages = [{'role': 'user', 'content': prompt}, prefill]

    stream = self.claude_client.messages.create(
      model=self.default_version,
      system=system_message,
      messages=convo_messages,
      temperature=self.temp,
      max_tokens=max_tok,
      stream=True
    )
    return stream

  def stream_text_only(self, prompt:str, max_tok:int=512):
    stream = self.claude_client.messages.create(
      model=self.default_version,
      system=self.sys_prompt['content'],
      messages=[{'role': 'user', 'content': prompt}],
      temperature=self.temp,
      max_tokens=max_tok,
      stream=True
    )
    return stream

  def set_system_prompt(self, prompt:str):
    self.sys_prompt["content"] = prompt

class InternalAPI(object):

  def __init__(self, args):
    remote_address = os.getenv('REMOTE_MODEL_SERVER')
    self.url_dact = f'http://{remote_address}/predict/intent_dact'
    self.url_core = f'http://{remote_address}/predict/core_ops'
    self.url_logreg = f'http://{remote_address}/predict/logreg'
    self.max_len = args.max_length
    self.verbose = args.verbose

  def execute(self, context_history, target='dact'):
    if target == 'dact':
      return self.execute_dact(context_history)
    elif target == 'core':
      return self.execute_core(context_history)
    elif target == 'logreg':
      return self.execute_logreg(context_history)

  def execute_logreg(self, context_history):
    start = tm.time()
    response = requests.post(self.url_logreg, json={'utt': context_history})

    if response.status_code == 200:
      results = response.json()
      pred_intent = results['intent']
      pred_dax = results['dax']
      pred_score = results['score']
    else:
      pred_intent = 'Analyze'
      pred_dax = '001'
      pred_score = 0.4
      print('Remote Server Error when predicting with LogReg')

    if self.verbose:
      interval = round(tm.time() - start, 2)
      print(f"  Internal API call took {interval} seconds.")
    return pred_intent, pred_dax, pred_score

  def execute_dact(self, context_history):
    start = tm.time()
    response = requests.post(self.url_dact, json={'utt': context_history})

    if response.status_code == 200:
      results = response.json()
      pred_intent = results['intent']
      dact_list = results['dact']
      pred_score = results['score']
    else:
      pred_intent, dact_list = 'Analyze', ['query']
      pred_score = 0.4
      print('Remote Server Error when predicting with PEFT')

    if self.verbose:
      interval = round(tm.time() - start, 2)
      print(f"  Internal API call took {interval} seconds.")
    return pred_intent, dact_list, pred_score

  def execute_core(self, context_history):
    start = tm.time()
    response = requests.post(self.url_core, json={'utt': context_history})

    if response.status_code == 200:
      results = response.json()
      pred_ent_list = results['ent']
      pred_ops_list = results['ops']
      pred_score = results['score']
    else:
      pred_ent_list, pred_ops_list = ['abstain'], ['abstain']
      pred_score = 0.4
      print('Remote Server Error when predicting with PEFT')

    if self.verbose:
      interval = round(tm.time() - start, 2)
      print(f"  Internal API call took {interval} seconds.")
    return pred_ent_list, pred_ops_list, pred_score
