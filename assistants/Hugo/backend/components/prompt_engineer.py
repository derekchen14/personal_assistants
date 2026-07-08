import json
import os
import re
import time
from pathlib import Path

import anthropic
from google import genai
import openai

import logging
from pydantic import BaseModel

from backend.prompts.general import build_system
from backend.prompts.for_pex import build_flow_system, build_flow_messages

log = logging.getLogger(__name__)

_TASK_SUFFIXES = {
    'classify_intent': 'You are a precise NLU classifier. Respond with only valid JSON. No markdown fences, no explanation.',
    'detect_flow': 'You are a precise flow classifier. Respond with only valid JSON. No markdown fences.',
    'fill_slots': 'You are a slot extraction engine. Respond with only valid JSON.',
    'contemplate': 'You are re-evaluating a failed flow detection. Respond with only valid JSON.',
    'repair_slot': 'Reply with ONLY the best matching valid option, or "NONE" if no match is reasonable.',
    'skill': '',
    'quality_check': (
        'You are a quality checker. Given recent conversation history, '
        'the user\'s latest request, and the agent\'s output (which may '
        'include the agent\'s spoken reply, card content, and structured '
        'data like proposed options), decide whether the response addresses '
        'what the user asked. Treat persisted action (an outline saved, a '
        'section written) as success even if the spoken reply is brief. '
        'Reply with ONLY "pass" or "fail: <one-sentence reason>".'
    ),
    'clarify': '',
}

# Single-token provider swap. Callers pass abstract tiers (`low` / `med` / `high`) while the concrete model is
# resolved against ACTIVE_FAMILY. Provider-specific keys are retained for explicit overrides / testing only.
ACTIVE_FAMILY = 'gemini'
FAMILY_TIERS = {
    'claude':   ('claude-haiku-4-5-20251001', 'claude-sonnet-5', 'claude-opus-4-7'),
    'gemini':   ('gemini-3.1-flash-lite-preview', 'gemini-3.5-flash', 'gemini-3.1-pro-preview'),
    'gpt':      ('gpt-5.4-nano', 'gpt-5.4-mini', 'gpt-5.4'),
    'together': ('Qwen/Qwen3.6-35B-A3B-FP8', 'Qwen/Qwen3.5-397B-A17B', 'moonshotai/Kimi-K2.6'),
    'typesafe': ('noul', 'score', 'choice'),   # TypeSafe question types stand in for the tier ladder
}

_low, _med, _high = FAMILY_TIERS[ACTIVE_FAMILY]
_MODEL_IDS = {
    'low': _low, 'med': _med, 'high': _high,
    # Provider-specific overrides for explicit testing.
    'flash': 'gemini-3-flash-preview',
    'pro':   'gemini-3.1-pro-preview',
    'qwen':  'Qwen/Qwen3.5-397B-A17B',
    'kimi':  'moonshotai/Kimi-K2.6',
    'mini':  'gpt-5.4-mini',
    'gpt':   'gpt-5.4',
}

_CLAUDE_MODELS    = set()
_GEMINI_MODELS    = {'flash', 'pro'}
_TOGETHER_MODELS  = {'qwen', 'kimi'}
_GPT_MODELS       = {'mini', 'gpt'}
_TIER_KEYS        = {'low', 'med', 'high'}

class PromptEngineer:

    VERSION = 'v1'
    _FLOW_DIR  = Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'flows'
    _SKILL_DIR = Path(__file__).resolve().parents[1] / 'prompts' / 'pex' / 'skills'

    _CLIENT_ENVARS = {
        'anthropic': 'ANTHROPIC_API_KEY',
        'google':    'GOOGLE_API_KEY',
        'openai':    'OPENAI_API_KEY',
        'together':  ('TOGETHER_API_KEY', 'QWEN_API_KEY'),
    }

    def __init__(self, config):
        self.config = config
        self._models = config.get('models', {})
        self.persona = config.get('persona', {})
        self._limits = config['limits']
        self._clients: dict[str, object] = {}

    def _get_client(self, provider:str):
        if provider in self._clients:
            return self._clients[provider]
        envars = self._CLIENT_ENVARS[provider]
        if isinstance(envars, str):
            envars = (envars,)
        api_key = next((os.getenv(e) for e in envars if os.getenv(e)), None)
        if not api_key:
            raise RuntimeError(f'{envars[0]} not set. Set it in .env or environment.')
        if provider == 'anthropic':
            client = anthropic.Anthropic(api_key=api_key)
        elif provider == 'google':
            client = genai.Client(api_key=api_key)
        elif provider == 'openai':
            client = openai.OpenAI(api_key=api_key)
        elif provider == 'together':
            client = openai.OpenAI(api_key=api_key, base_url='https://api.together.xyz/v1')
        self._clients[provider] = client
        return client

    # ── Model resolution ─────────────────────────────────────────────

    @staticmethod
    def _resolve_model(model:str) -> str:
        if model not in _MODEL_IDS:
            raise ValueError(f'Unknown model: {model!r}')
        return _MODEL_IDS[model]

    @staticmethod
    def _model_family(model:str) -> str:
        if model in _TIER_KEYS:       return ACTIVE_FAMILY
        if model in _CLAUDE_MODELS:   return 'claude'
        if model in _GEMINI_MODELS:   return 'gemini'
        if model in _TOGETHER_MODELS: return 'together'
        if model in _GPT_MODELS:      return 'gpt'
        raise ValueError(f'Unknown model family for: {model!r}')

    def _get_temperature(self, task:str='skill') -> float:
        overrides = self._models.get('overrides', {})
        if task in overrides:
            val = overrides[task].get('temperature')
            if val is not None:
                return val
        return self._models.get('default', {}).get('temperature', 0.0)

    def _get_retry_config(self) -> tuple[int, float, float]:
        llm_cfg = self._limits.get('llm_retries', {})
        max_attempts = llm_cfg.get('max_attempts', 2)
        backoff_base = llm_cfg.get('backoff_base_ms', 500) / 1000
        backoff_max = llm_cfg.get('backoff_max_ms', 10000) / 1000
        return max_attempts, backoff_base, backoff_max

    # ── Public API ────────────────────────────────────────────────────

    def _system_for_task(self, task:str) -> str:
        base = build_system(self.persona)
        suffix = _TASK_SUFFIXES.get(task, '')
        return f'{base}\n\n{suffix}'.strip() if suffix else base

    def __call__(self, prompt:str, task:str='skill', model:str='med', max_tokens:int=1024, schema=None):
        messages = [{'role': 'user', 'content': prompt}]
        system = self._system_for_task(task)
        model_id = self._resolve_model(model)
        log.info('  task=%s  model=%s', task, model_id)
        schema_dict = self._to_json_schema(schema) if schema is not None else None
        match self._model_family(model):
            case 'claude':
                response = self._call_claude(system, messages, model_id, max_tokens=max_tokens, schema_dict=schema_dict)
                text = ''.join(block.text for block in response.content if block.type == 'text')
            case 'gemini':
                text = self._call_gemini(system, messages, model_id, max_tokens, schema_dict=schema_dict)
            case 'together':
                text = self._call_together(system, messages, model_id, max_tokens, schema_dict=schema_dict)
            case 'gpt':
                text = self._call_gpt(system, messages, model_id, max_tokens, schema_dict=schema_dict)
        if schema is None:
            return text
        parsed = self.apply_guardrails(text, format='json')
        if parsed is None:
            raise ValueError(f'schema-constrained call returned unparseable JSON: {text!r}')
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_validate(parsed)
        return parsed

    @staticmethod
    def _to_json_schema(schema) -> dict:
        if isinstance(schema, dict):
            return schema
        if isinstance(schema, type) and issubclass(schema, BaseModel):
            return schema.model_json_schema()
        raise TypeError(f'schema must be a dict or Pydantic BaseModel subclass, got {type(schema)!r}')

    def flow_reply(self, flow, convo_history:str, scratchpad:dict, skill_name:str|None=None,
                   flow_prompt:str|None=None, resolved:dict|None=None, max_tokens:int=1024,
                   user_text:str|None=None, model:str='med') -> str:
        """Flow sub-agent turn WITHOUT tool use. Sibling of flow_execute."""
        if flow_prompt is None:
            flow_prompt = self.load_flow_prompt(skill_name or flow.name())
        base_system = build_system(self.persona)
        system = build_flow_system(base_system, flow, flow_prompt)
        messages = list(build_flow_messages(flow, convo_history, user_text, resolved))
        model_id = self._resolve_model(model)
        match self._model_family(model):
            case 'claude':
                r = self._call_claude(system, messages, model_id, max_tokens=max_tokens)
                return ''.join(b.text for b in r.content if b.type == 'text')
            case 'gemini':   return self._call_gemini(system, messages, model_id, max_tokens)
            case 'together': return self._call_together(system, messages, model_id, max_tokens)
            case 'gpt':      return self._call_gpt(system, messages, model_id, max_tokens)

    def flow_execute(self, flow, convo_history:str, scratchpad:dict, tool_defs:list[dict], tool_dispatcher,
                  skill_name:str|None=None, flow_prompt:str|None=None, resolved:dict|None=None,
                  max_tokens:int=4096, user_text:str|None=None,
                  model:str='med', schema:dict|None=None) -> tuple[str, list[dict]]:
        """Flow sub-agent turn WITH tool use. Sibling of flow_reply.

        Pass `model='high'` for flows that need stronger reasoning (e.g. brainstorm). Pass
        `schema=<json-schema dict>` to force a schema-constrained final emit — applied as a
        no-tools follow-up call when the tool loop terminates with empty text."""
        if flow_prompt is None:
            flow_prompt = self.load_flow_prompt(skill_name or flow.name())
        base_system = build_system(self.persona)
        system = build_flow_system(base_system, flow, flow_prompt)
        msgs = list(build_flow_messages(flow, convo_history, user_text, resolved))
        model_id = self._resolve_model(model)

        extended = flow.name() in self._limits['extended_call_flows']
        max_num_calls = self._limits['extended_tool_calls' if extended else 'max_tool_calls']

        family = self._model_family(model)
        adapted = self._adapt_tool_defs(family, tool_defs)
        match family:
            case 'claude':   return self._call_claude_with_tools(system, msgs, model_id, adapted, tool_dispatcher, max_tokens, max_num_calls)
            case 'gemini':   return self._call_gemini_with_tools(system, msgs, model_id, adapted, tool_dispatcher, max_tokens, max_num_calls, schema_dict=schema)
            case 'gpt':      return self._call_gpt_with_tools(system, msgs, model_id, adapted, tool_dispatcher, max_tokens, max_num_calls)
            case 'together': return self._call_together_with_tools(system, msgs, model_id, adapted, tool_dispatcher, max_tokens, max_num_calls)

    def _call_claude_with_tools(self, system, msgs, model_id, tool_defs, tool_dispatcher, max_tokens, max_num_calls):
        msgs = list(msgs)
        tool_log: list[dict] = []
        text_parts: list[str] = []
        for _ in range(max_num_calls):
            response = self._call_claude(system, msgs, model_id, tools=tool_defs, max_tokens=max_tokens)
            text_parts = []
            tool_uses = []
            for block in response.content:
                if block.type == 'text':
                    text_parts.append(block.text)
                elif block.type == 'tool_use':
                    tool_uses.append(block)
            if not tool_uses:
                return '\n'.join(text_parts), tool_log
            msgs.append({'role': 'assistant', 'content': response.content})
            tool_results = []
            for tool_use in tool_uses:
                log.info('  skill tool=%s  input=%s', tool_use.name,
                         {key: val for key, val in tool_use.input.items()} if tool_use.input else {})
                result = tool_dispatcher(tool_use.name, tool_use.input)
                tool_log.append({'tool': tool_use.name, 'input': tool_use.input, 'result': result})
                tool_results.append({
                    'type': 'tool_result', 'tool_use_id': tool_use.id,
                    'content': json.dumps(result, default=str),
                })
            msgs.append({'role': 'user', 'content': tool_results})
        return '\n'.join(text_parts), tool_log

    async def stream(self, prompt:str, task:str='skill', model:str='med', max_tokens:int=4096):
        """Token streaming. Same routing as __call__, yields text chunks."""
        messages = [{'role': 'user', 'content': prompt}]
        system = self._system_for_task(task)
        model_id = self._resolve_model(model)
        log.info('  task=%s  model=%s  stream=true', task, model_id)
        match self._model_family(model):
            case 'claude':
                with self._get_client('anthropic').messages.stream(
                    model=model_id, max_tokens=max_tokens,
                    system=system, messages=messages,
                ) as stm:
                    for text in stm.text_stream:
                        yield text
            case _:
                text = self(prompt, task=task, model=model, max_tokens=max_tokens)
                yield text

    # ── Private provider methods ──────────────────────────────────────

    def _retry(self, fn, retryable):
        max_attempts, backoff_base, backoff_max = self._get_retry_config()
        last_error = None
        for attempt in range(max_attempts):
            try:
                return fn()
            except retryable as ecp:
                last_error = ecp
                if attempt < max_attempts - 1:
                    time.sleep(min(backoff_base * (2 ** attempt), backoff_max))
        raise last_error

    def _call_claude(self, system, messages, model_id, *, tools=None, max_tokens=4096, schema_dict=None):
        # Prompt caching: put a breakpoint at the end of the system prompt and at the end of tool
        # definitions. These are the stable prefix shared across turns within a flow; per-turn
        # content in `messages` sits after the cache boundary and is not cached.
        system_blocks = [{
            'type': 'text',
            'text': system,
            'cache_control': {'type': 'ephemeral'},
        }] if system else []
        kwargs = {
            'model': model_id, 'max_tokens': max_tokens,
            'system': system_blocks, 'messages': messages,
        }
        temp = self._get_temperature()
        if temp > 0:
            kwargs['temperature'] = temp
        if tools:
            tool_defs = [
                {key: val for key, val in tool.items() if key in ('name', 'description', 'input_schema')}
                for tool in tools
            ]
            if tool_defs:
                # Cache breakpoint on the last tool definition.
                tool_defs[-1] = {**tool_defs[-1], 'cache_control': {'type': 'ephemeral'}}
            kwargs['tools'] = tool_defs
        if schema_dict is not None:
            kwargs['output_config'] = {'format': {'type': 'json_schema', 'schema': schema_dict}}
        client = self._get_client('anthropic')
        try:
            return self._retry(lambda: client.messages.create(**kwargs),
                (anthropic.RateLimitError, anthropic.APITimeoutError, anthropic.InternalServerError))
        except anthropic.APIError:
            raise

    def _call_gemini(self, system, messages, model_id, max_tokens=4096, schema_dict=None):
        from google.genai import types
        temp = self._get_temperature()
        gemini_contents = [
            types.Content(role=('model' if msg['role'] == 'assistant' else 'user'),
                parts=[types.Part.from_text(text=msg['content'])])
            for msg in messages
        ]
        # Pro requires thinking mode (-1 = auto-budget, separate from max_output_tokens).
        # Flash / Flash-Lite suppress thinking (0) for latency + cost.
        thinking_budget = -1 if 'pro' in model_id else 0
        config = types.GenerateContentConfig(
            system_instruction=system, max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        )
        if temp > 0:
            config.temperature = temp
        if schema_dict is not None:
            config.response_mime_type = 'application/json'
            config.response_json_schema = schema_dict
        client = self._get_client('google')
        response = self._retry(
            lambda: client.models.generate_content(
                model=model_id, contents=gemini_contents, config=config),
            Exception,
        )
        return response.text

    def _call_gpt(self, system, messages, model_id, max_tokens=4096, schema_dict=None):
        temp = self._get_temperature()
        oai_messages = [{'role': 'system', 'content': system}]
        oai_messages.extend({'role': msg['role'], 'content': msg['content']} for msg in messages)
        kwargs = {
            'model': model_id, 'messages': oai_messages,
            'max_completion_tokens': max_tokens,
        }
        if temp > 0:
            kwargs['temperature'] = temp
        if schema_dict is not None:
            kwargs['response_format'] = {
                'type': 'json_schema',
                'json_schema': {'name': 'response', 'schema': schema_dict, 'strict': True},
            }
        client = self._get_client('openai')
        try:
            response = self._retry(lambda: client.chat.completions.create(**kwargs),
                (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError))
            return response.choices[0].message.content or ''
        except openai.APIError:
            raise

    def _call_together(self, system, messages, model_id, max_tokens=4096, schema_dict=None):
        temp = self._get_temperature()
        is_thinking = 'thinking' in model_id.lower()
        qwen_messages = [{'role': 'system', 'content': system}]
        qwen_messages.extend({'role': msg['role'], 'content': msg['content']} for msg in messages)
        kwargs = {
            'model': model_id, 'messages': qwen_messages,
            'max_completion_tokens': max_tokens if is_thinking else None,
        }
        if not is_thinking:
            kwargs['max_tokens'] = max_tokens
        if temp > 0 and not is_thinking:
            kwargs['temperature'] = temp
        if schema_dict is not None:
            kwargs['response_format'] = {
                'type': 'json_schema',
                'json_schema': {'name': 'response', 'schema': schema_dict, 'strict': True},
            }
        kwargs = {key: val for key, val in kwargs.items() if val is not None}
        client = self._get_client('together')
        try:
            response = self._retry(lambda: client.chat.completions.create(**kwargs),
                (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError))
        except openai.APIError:
            raise
        raw_text = response.choices[0].message.content or ''
        if is_thinking and '<think>' in raw_text:
            parts = raw_text.split('</think>')
            if len(parts) > 1:
                raw_text = parts[-1].strip()
            else:
                match = re.search(r'\{[^{}]*\}', raw_text)
                if match:
                    raw_text = match.group()
        return raw_text

    # ── Tool-use loops (per family) ──────────────────────────────────

    @staticmethod
    def _adapt_tool_defs(family, tool_defs):
        """Convert Anthropic-shaped tool defs to per-provider shape."""
        if family == 'claude':
            return [{'name': t['name'], 'description': t['description'],
                     'input_schema': t['input_schema']} for t in tool_defs]
        if family == 'gemini':
            return [{'name': t['name'], 'description': t['description'],
                     'parameters': PromptEngineer._sanitize_for_gemini(t['input_schema'])}
                    for t in tool_defs]
        if family in ('gpt', 'together'):
            return [{'type': 'function', 'function': {
                'name': t['name'], 'description': t['description'],
                'parameters': t['input_schema'],
            }} for t in tool_defs]
        raise ValueError(f'Unknown family for tool-def adapter: {family!r}')

    @staticmethod
    def _sanitize_for_gemini(schema):
        """Recursively trim JSON Schema features that Gemini's FunctionDeclaration rejects.
        Drops oneOf/anyOf/allOf (collapsing to the first option), additionalProperties,
        default, examples, $ref/definitions. Recurses through properties and items."""
        if not isinstance(schema, dict):
            return schema
        out = {}
        for key, val in schema.items():
            if key in ('oneOf', 'anyOf', 'allOf'):
                if val and isinstance(val, list) and isinstance(val[0], dict):
                    first = PromptEngineer._sanitize_for_gemini(val[0])
                    for k, v in first.items():
                        out.setdefault(k, v)
                continue
            if key in ('additionalProperties', 'default', 'examples', '$ref', 'definitions', '$schema'):
                continue
            if key == 'properties' and isinstance(val, dict):
                out[key] = {k: PromptEngineer._sanitize_for_gemini(v) for k, v in val.items()}
            elif key == 'items':
                out[key] = PromptEngineer._sanitize_for_gemini(val)
            else:
                out[key] = val
        return out

    def _call_gemini_with_tools(self, system, messages, model_id, tool_defs, tool_dispatcher,
                                max_tokens, max_num_calls, schema_dict=None):
        from google.genai import types
        contents = [
            types.Content(role=('model' if m['role'] == 'assistant' else 'user'),
                          parts=[types.Part.from_text(text=m['content'])])
            for m in messages
        ]
        fns = [types.FunctionDeclaration(**td) for td in tool_defs]
        thinking_budget = -1 if 'pro' in model_id else 0
        config = types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=fns)],
            max_output_tokens=max_tokens,
            thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        )
        client = self._get_client('google')
        tool_log: list[dict] = []
        text = ''
        for _ in range(max_num_calls):
            response = self._retry(
                lambda: client.models.generate_content(model=model_id, contents=contents, config=config),
                Exception,
            )
            candidate = response.candidates[0]
            parts = candidate.content.parts or []
            function_calls = [p.function_call for p in parts if getattr(p, 'function_call', None)]
            text = ''.join(p.text for p in parts if getattr(p, 'text', None))
            if not function_calls:
                break
            contents.append(candidate.content)
            response_parts = []
            for fc in function_calls:
                args = dict(fc.args) if fc.args else {}
                log.info('  skill tool=%s  input=%s', fc.name, args)
                result = tool_dispatcher(fc.name, args)
                tool_log.append({'tool': fc.name, 'input': args, 'result': result})
                response_parts.append(types.Part.from_function_response(
                    name=fc.name, response={'result': result},
                ))
            contents.append(types.Content(role='user', parts=response_parts))
        # Schema-enforced terminal emit: if the tool loop returned empty text and the caller
        # supplied a schema, do one more no-tools call so the model is forced to produce JSON.
        if schema_dict is not None and not text.strip():
            final_config = types.GenerateContentConfig(
                system_instruction=system, max_output_tokens=max_tokens,
                thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
                response_mime_type='application/json', response_json_schema=schema_dict,
            )
            response = self._retry(
                lambda: client.models.generate_content(model=model_id, contents=contents, config=final_config),
                Exception,
            )
            text = response.text or ''
        return text, tool_log

    def _call_gpt_with_tools(self, system, messages, model_id, tool_defs, tool_dispatcher, max_tokens, max_num_calls):
        return self._openai_tool_loop(
            client=self._get_client('openai'), system=system, messages=messages,
            model_id=model_id, tool_defs=tool_defs, tool_dispatcher=tool_dispatcher,
            max_tokens=max_tokens, max_num_calls=max_num_calls,
            completion_tokens_param=True, allow_streaming_fallback=False,
        )

    def _call_together_with_tools(self, system, messages, model_id, tool_defs, tool_dispatcher, max_tokens, max_num_calls):
        return self._openai_tool_loop(
            client=self._get_client('together'), system=system, messages=messages,
            model_id=model_id, tool_defs=tool_defs, tool_dispatcher=tool_dispatcher,
            max_tokens=max_tokens, max_num_calls=max_num_calls,
            completion_tokens_param=False, allow_streaming_fallback=True,
        )

    def _openai_tool_loop(self, *, client, system, messages, model_id, tool_defs, tool_dispatcher,
                          max_tokens, max_num_calls, completion_tokens_param, allow_streaming_fallback):
        msgs = [{'role': 'system', 'content': system}]
        msgs.extend({'role': m['role'], 'content': m['content']} for m in messages)
        tool_log: list[dict] = []
        text = ''
        for _ in range(max_num_calls):
            kwargs = {'model': model_id, 'messages': msgs, 'tools': tool_defs}
            kwargs['max_completion_tokens' if completion_tokens_param else 'max_tokens'] = max_tokens
            try:
                response = self._retry(
                    lambda: client.chat.completions.create(**kwargs),
                    (openai.RateLimitError, openai.APITimeoutError, openai.InternalServerError),
                )
            except openai.BadRequestError as ecp:
                if allow_streaming_fallback and 'streaming' in str(ecp).lower():
                    response = self._openai_streaming_tool_call(client, kwargs)
                else:
                    raise
            msg = response.choices[0].message
            text = msg.content or ''
            tool_calls = getattr(msg, 'tool_calls', None) or []
            if not tool_calls:
                return text, tool_log
            msgs.append({
                'role': 'assistant', 'content': text or None,
                'tool_calls': [{
                    'id': tc.id, 'type': 'function',
                    'function': {'name': tc.function.name, 'arguments': tc.function.arguments},
                } for tc in tool_calls],
            })
            for tc in tool_calls:
                args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                log.info('  skill tool=%s  input=%s', tc.function.name, args)
                result = tool_dispatcher(tc.function.name, args)
                tool_log.append({'tool': tc.function.name, 'input': args, 'result': result})
                msgs.append({
                    'role': 'tool', 'tool_call_id': tc.id,
                    'content': json.dumps(result, default=str),
                })
        return text, tool_log

    @staticmethod
    def _openai_streaming_tool_call(client, kwargs):
        """Streaming-fallback for Together models that reject non-streaming requests.
        Accumulates text + tool_call deltas and returns a non-streaming-shaped response."""
        kwargs = {**kwargs, 'stream': True, 'stream_options': {'include_usage': True}}
        text_parts: list[str] = []
        tool_acc: dict[int, dict] = {}
        for chunk in client.chat.completions.create(**kwargs):
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                text_parts.append(delta.content)
            for tc_delta in (delta.tool_calls or []):
                slot = tool_acc.setdefault(tc_delta.index, {'id': '', 'name': '', 'arguments': ''})
                if tc_delta.id:
                    slot['id'] = tc_delta.id
                if tc_delta.function and tc_delta.function.name:
                    slot['name'] = tc_delta.function.name
                if tc_delta.function and tc_delta.function.arguments:
                    slot['arguments'] += tc_delta.function.arguments
        # Re-shape to look like a non-streaming response (just the bits the loop reads).
        from types import SimpleNamespace
        tool_calls = [
            SimpleNamespace(id=s['id'], function=SimpleNamespace(name=s['name'], arguments=s['arguments']))
            for s in (tool_acc[i] for i in sorted(tool_acc))
        ]
        msg = SimpleNamespace(content=''.join(text_parts), tool_calls=tool_calls or None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    # ── Output parsers ───────────────────────────────────────────────

    @classmethod
    def apply_guardrails(cls, text:str, format:str='json', shape:str|None=None):
        """Strip fences, then dispatch to the right format parser. `format` is one of
        'json' | 'sql' | 'markdown'; `shape` is an optional hint passed to the format parser
        (e.g. 'outline', 'candidates')."""
        text = cls._strip_fences(text)
        match format:
            case 'json':     return cls._parse_json(text)
            case 'sql':      return cls._parse_sql(text)
            case 'markdown': return cls._parse_markdown(text, shape)

    def _strip_nulls(self, obj):
        """Recursively drop None values before handing slots to fill_slot_values, which is needed because the
        model prediction schema enforces emitting `null` for empty slots rather than a string sentinel."""
        if isinstance(obj, dict):
            return {k: self._strip_nulls(v) for k, v in obj.items() if v is not None}
        if isinstance(obj, list):
            return [self._strip_nulls(x) for x in obj if x is not None]
        return obj

    @staticmethod
    def _strip_fences(text:str) -> str:
        text = text.strip()
        if text.startswith('```'):
            lines = [line for line in text.split('\n') if not line.strip().startswith('```')]
            text = '\n'.join(lines)
        return text

    @staticmethod
    def _parse_json(text:str) -> dict | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    @staticmethod
    def _parse_sql(text:str) -> str:
        return text.strip()

    @staticmethod
    def _parse_markdown(text:str, shape:str|None=None):
        if not text:
            return [] if shape == 'candidates' else ''
        if shape == 'candidates':
            option_parts = re.split(r'(?m)^###\s+Option\s+\d+\s*\n', text)
            candidates = []
            for option_body in option_parts[1:]:
                sections = []
                for section_body in re.split(r'(?m)^##\s+', option_body)[1:]:
                    lines = section_body.strip().split('\n', 1)
                    name = lines[0].strip()
                    description = lines[1].strip() if len(lines) > 1 else ''
                    if name:
                        sections.append({'name': name, 'description': description, 'checked': False})
                if sections:
                    candidates.append(sections)
            return candidates
        # shape='outline' or default: extract ## sections
        lines = text.split('\n')
        outline_lines = []
        in_outline = False
        for line in lines:
            if line.startswith('## '):
                in_outline = True
            if in_outline:
                outline_lines.append(line)
        if outline_lines:
            return '\n'.join(outline_lines)
        sections = []
        for line in lines:
            stripped = line.strip()
            if stripped and stripped[0].isdigit() and '**' in stripped:
                match = re.search(r'\*\*(.+?)\*\*', stripped)
                if match:
                    title = match.group(1).strip().lstrip('#').strip()
                    desc = stripped.split('**')[-1].strip(' —-–:')
                    sections.append(f'## {title}')
                    if desc:
                        sections.append(f'\n- {desc}')
                    sections.append('')
        return '\n'.join(sections) if sections else ''

    @classmethod
    def load_flow_prompt(cls, flow_name:str) -> str:
        """Full markdown instruction prompt for a flow sub-agent (pex/flows/<flow>.md)."""
        return (cls._FLOW_DIR / f'{flow_name}.md').read_text(encoding='utf-8')

    @classmethod
    def load_skill(cls, skill_name:str) -> str:
        """An agent-level skill body (pex/skills/<skill>.md) — currently only the Workflow Planner."""
        return (cls._SKILL_DIR / f'{skill_name}.md').read_text(encoding='utf-8')

    @staticmethod
    def extract_tool_result(tool_log:list, tool_name:str) -> dict:
        for entry in tool_log:
            if entry['tool'] != tool_name:
                continue
            if entry['result']['_success']:
                return {k: v for k, v in entry['result'].items() if not k.startswith('_')}
        return {}

    @staticmethod
    def tool_succeeded(tool_log:list, tool_name:str) -> tuple[bool, dict]:
        """Check whether a named tool was called AND every call succeeded.

        Returns (True, last_result_dict) when the tool appears at least once in the log and every
        matching entry has _success=True; returns (False, {}) otherwise. The result dict strips
        underscore-prefixed control keys."""
        calls = [tc for tc in tool_log if tc['tool'] == tool_name]
        if not calls:
            return False, {}
        if not all(tc['result']['_success'] for tc in calls):
            return False, {}
        return True, {k: v for k, v in calls[-1]['result'].items() if not k.startswith('_')}

